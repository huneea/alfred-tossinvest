#!/usr/bin/python3
"""Script Filter: 코스피·코스닥 지수와 등락률.

지수도 현재가만 오므로 등락률은 일봉의 전일 종가로 계산한다. 전일 종가는 종목과
같은 캐시를 쓰기 때문에 추가 호출은 그날 처음 한 번뿐이고, 자동 갱신에서는 지수
시세 조회 1회로 끝난다.
"""

from __future__ import annotations

from tossinvest import alfred, api, auth, fmt, icons

# 지수는 원화 금액이 아니라 지수값이다. 통화 기호 없이 소수 둘째 자리까지 쓴다.
DECIMALS = 2


def main():
    token = auth.access_token()
    quotes = api.index_prices(token)
    previous = api.index_prev_closes(token)

    items = []
    for symbol in api.INDEX_SYMBOLS:
        last = (quotes.get(symbol) or {}).get("lastPrice")
        if last is None:
            items.append(alfred.item(symbol, "시세를 받지 못했습니다", valid=False, icon=icons.WARN))
            continue

        _, rate = api.change_against(last, previous.get(symbol))
        title = "{0}  {1}".format(symbol, fmt.number(last, DECIMALS))
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

    alfred.live(items)


if __name__ == "__main__":
    alfred.run(main)
