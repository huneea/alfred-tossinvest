"""종목 목록 렌더링.

tsp(관심종목/최근 조회)와 tsw(관심종목 전용)가 같은 모양의 목록을 보여주므로
여기 모아둔다.
"""

from __future__ import annotations

from . import alfred, api, fmt, icons, store

STOCK_URL = "https://tossinvest.com/stocks/{0}"


def stock_url(symbol):
    return STOCK_URL.format(symbol)


def price_text(quote):
    if not quote:
        return "시세 없음"
    return fmt.money(quote.get("lastPrice"), quote.get("currency") or "KRW")


def change_rates(token, symbols, quotes):
    """종목코드 -> {"rate": 기준가 대비 %, "regular": 정규장 종가 대비 %}.

    등락은 반드시 화면에 보여주는 현재가(quotes 의 lastPrice)를 기준으로 계산한다.
    다른 값으로 계산하면 표시된 현재가와 등락이 서로 맞지 않는다.

    전일 종가는 api.prev_closes 가 다음 장 시작까지 캐싱하므로 이 함수를 부르는 데
    드는 추가 호출은 그 종목을 처음 본 날뿐이다.
    """
    previous = api.prev_closes(token, symbols)
    result = {}
    for symbol in symbols:
        last = (quotes.get(symbol) or {}).get("lastPrice")
        closes = previous.get(symbol) or {}
        _, rate = api.change_against(last, closes.get("base"))

        regular = None
        # 두 종가가 같으면 같은 값을 두 번 보여줄 이유가 없다.
        if closes.get("candle") and closes.get("candle") != closes.get("base"):
            _, regular = api.change_against(last, closes["candle"])

        result[symbol] = {"rate": rate, "regular": regular}
    return result


def stock_item(symbol, name, quote, rates, market, saved):
    """종목 한 건을 항목으로. 목록과 검색 결과가 같은 모양을 쓴다.

    부제에는 행마다 달라지는 값만 넣는다. 모든 행에 같은 문구를 반복하면 자리만
    차지하고 알려주는 것이 없다.
    """
    rates = rates or {}
    title = "{0}  {1}".format(name, price_text(quote))
    if rates.get("rate") is not None:
        title += "  {0}".format(fmt.signed_rate(rates["rate"]))

    regular = rates.get("regular")
    return alfred.item(
        title=title,
        subtitle=" · ".join(part for part in (
            symbol,
            market,
            "정규장 {0}".format(fmt.signed_rate(regular)) if regular is not None else "",
            "⌘↩ 관심종목 {0}".format("제거" if symbol in saved else "추가"),
        ) if part),
        arg=stock_url(symbol),
        uid=symbol,
        copy=symbol,
        icon=icons.for_stock(symbol, saved),
        mods=alfred.toggle_mod(symbol, symbol in saved),
        autocomplete=name,
    )


def listing(token, symbols):
    """종목코드 목록을 현재가·등락률이 붙은 항목으로 만든다."""
    quotes = api.prices(token, symbols)
    rates = change_rates(token, symbols, quotes)
    info = api.symbol_info(token, symbols)
    saved = set(store.watchlist())

    return [
        stock_item(
            symbol,
            (info.get(symbol) or {}).get("name") or symbol,
            quotes.get(symbol),
            rates.get(symbol),
            (info.get(symbol) or {}).get("market") or "",
            saved,
        )
        for symbol in symbols
    ]
