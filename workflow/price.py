#!/usr/bin/python3
"""Script Filter: 종목 검색 후 현재가 표시.

Alfred 는 pyenv/nvm 을 못 보므로 시스템 인터프리터를 shebang 에 못 박는다.
"""

from __future__ import annotations

import sys

from tossinvest import alfred, api, auth, fmt

# 토스증권 웹에서 해당 종목을 여는 주소. 엔터를 누르면 이 값이 arg 로 넘어간다.
STOCK_URL = "https://tossinvest.com/stocks/{0}"


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    if not query.strip():
        alfred.empty("종목명 또는 티커를 입력하세요", "예: 삼성전자, 005930")
        return

    token = auth.access_token()
    matches = api.search_stocks(token, query)
    if not matches:
        alfred.empty("검색 결과가 없습니다", "'{0}' 와 일치하는 종목이 없습니다.".format(query))
        return

    quotes = api.prices(token, [entry.get("symbol") for entry in matches])

    items = []
    for entry in matches:
        symbol = entry.get("symbol") or ""
        name = entry.get("name") or symbol
        quote = quotes.get(symbol) or {}
        currency = quote.get("currency") or "KRW"
        last = quote.get("lastPrice")

        price_text = fmt.money(last, currency) if last is not None else "시세 없음"
        items.append(
            alfred.item(
                title="{0}  {1}".format(name, price_text),
                subtitle="{0} · {1}".format(symbol, entry.get("market") or ""),
                arg=STOCK_URL.format(symbol),
                uid=symbol,
                copy=str(last) if last is not None else symbol,
            )
        )

    alfred.output(items)


if __name__ == "__main__":
    alfred.run(main)
