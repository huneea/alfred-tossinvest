#!/usr/bin/python3
"""Script Filter: 코스피·코스닥 지수와 미국 지수 대용 ETF.

지수도 현재가만 오므로 등락률은 일봉의 전일 종가로 계산한다. 전일 종가는 종목과
같은 캐시를 쓰기 때문에 추가 호출은 그날 처음 한 번뿐이다.

**미국 지수는 토스 Open API 에 없다.** 시장 지표 심볼 카탈로그는 8종이고 전부
국내다 — 코스피·코스닥과 국고채 금리 6종(2·3·5·10·20·30년). `SPX`·`DJI`·`VIX` 는
400 `unsupported-symbol` 이고, 선물(`NQ`·`NQZ5`·`MNQ`)은 빈 응답이다. API 의 GET
엔드포인트 27개 중 파생 관련이 하나도 없다.

그래서 미국 쪽은 **지수를 추종하는 ETF** 로 대신 보여준다. 지수가 아니므로 화면에
그렇게 적는다 — 등락률은 지수를 거의 따라가지만 추적오차가 있고, 가격 수준은
지수값과 아예 다르다(S&P 500 은 6,800 대인데 SPY 는 770 대다).

선물도 마찬가지로 국내 상장 선물 추종 ETF 로 대신한다. 미국 상장 ETF 가 한국 낮에
멈춰 있는 것과 달리 이쪽은 한국장 시간에 거래되므로, 낮에 미국 방향을 보려면 이
행을 봐야 한다.
"""

from __future__ import annotations

from tossinvest import alfred, api, auth, fmt, icons, store, view

# 지수는 원화 금액이 아니라 지수값이다. 통화 기호 없이 소수 둘째 자리까지 쓴다.
DECIMALS = 2

INDEX_LABELS = {"KOSPI": "코스피", "KOSDAQ": "코스닥"}

# (심볼, 표시 이름, 성격). 지수와 그 선물을 나란히 둔다.
#
# 미국 상장 ETF 는 한국 낮에 미국장이 닫혀 있어 거의 움직이지 않는다. 선물 행은
# 국내 상장이라 한국장 시간에 야간 선물 흐름을 반영한다 — 실측에서 같은 시각
# QQQ 가 -0.10% 일 때 나스닥 선물 ETF 는 +0.88% 였다. 한국 낮에 미국 방향을
# 보려면 선물 행을 봐야 하는 이유다.
#
# 선물 쪽은 KODEX 로 통일했다. 같은 지수에 TIGER 도 있지만(143850) 운용사가 다르면
# 추적오차가 달라 두 행의 등락률을 나란히 읽을 때 혼란스럽다.
#
# 다우는 1배수 선물 ETF 가 국내에 없다. 레버리지·인버스 ETN 뿐이라 넣지 않았다.
PROXIES = (
    ("SPY", "S&P 500", "지수 추종 ETF · 미국 상장"),
    ("219480", "S&P 500 선물", "선물 추종 ETF(환헤지) · 국내 상장이라 한국장 시간에 움직입니다"),
    ("QQQ", "나스닥 100", "지수 추종 ETF · 미국 상장"),
    ("304940", "나스닥 100 선물", "선물 추종 ETF(환헤지) · 국내 상장이라 한국장 시간에 움직입니다"),
    ("DIA", "다우 30", "지수 추종 ETF · 미국 상장"),
)


def _index_items(token):
    quotes = api.index_prices(token)
    previous = api.index_prev_closes(token)

    items = []
    for symbol in api.INDEX_SYMBOLS:
        label = INDEX_LABELS.get(symbol, symbol)
        last = (quotes.get(symbol) or {}).get("lastPrice")
        if last is None:
            items.append(alfred.item(label, "시세를 받지 못했습니다", valid=False, icon=icons.WARN))
            continue

        _, rate = api.change_against(last, previous.get(symbol))
        title = "{0}  {1}".format(label, fmt.number(last, DECIMALS))
        if rate is not None:
            title += "  {0}".format(fmt.colored_rate(rate))

        items.append(
            alfred.item(
                title=title,
                subtitle="전일 {0} · ↩ 지수값 복사".format(
                    fmt.number(previous.get(symbol), DECIMALS)
                ),
                arg=fmt.number(last, DECIMALS),
                uid=symbol,
                copy=fmt.number(last, DECIMALS),
                icon=icons.STOCK,
            )
        )
    return items


def _proxy_items(token):
    """지수 대용 ETF. 실제 거래되는 종목이라 종목 행과 같은 동작을 준다."""
    symbols = [symbol for symbol, _, _ in PROXIES]
    quotes = api.prices(token, symbols)
    rates = view.change_rates(token, symbols, quotes)
    saved = set(store.watchlist())

    items = []
    for symbol, label, note in PROXIES:
        quote = quotes.get(symbol) or {}
        last = quote.get("lastPrice")
        if last is None:
            continue

        title = "{0}  {1}".format(
            label, fmt.money(last, quote.get("currency") or "KRW"))
        rate = (rates.get(symbol) or {}).get("rate")
        if rate is not None:
            title += "  {0}".format(fmt.colored_rate(rate))

        items.append(
            alfred.item(
                title=title,
                subtitle="{0} · {1}".format(symbol, note),
                arg=view.stock_url(symbol),
                uid=symbol,
                copy=symbol,
                icon=icons.for_stock(symbol, saved),
                mods=alfred.stock_mods(symbol, symbol in saved),
            )
        )
    return items


def main():
    token = auth.access_token()
    alfred.live(_index_items(token) + _proxy_items(token))


if __name__ == "__main__":
    alfred.run(main)
