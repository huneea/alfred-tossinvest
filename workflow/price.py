#!/usr/bin/python3
"""Script Filter: 관심종목 목록과 종목 검색.

빈 쿼리면 관심종목을, 관심종목이 없으면 최근 조회한 종목을 보여준다. 관심종목만
보려면 tsw 를 쓴다.

검색 결과에는 현재가만 붙인다. Script Filter 는 키 입력마다 실행되므로 결과마다
캔들을 부르면 곧바로 rate limit 에 걸린다.
"""

from __future__ import annotations

import sys

from tossinvest import alfred, api, auth, icons, store, view


def _search(token, query):
    matches = api.search_stocks(token, query)
    if not matches:
        alfred.empty("검색 결과가 없습니다", "'{0}' 와 일치하는 종목이 없습니다.".format(query))
        return

    symbols = [entry.get("symbol") for entry in matches]
    quotes = api.prices(token, symbols)
    saved = set(store.watchlist())

    items = []
    for entry in matches:
        symbol = entry.get("symbol") or ""
        items.append(
            alfred.item(
                # 관심종목 여부는 아이콘(별)이 알려주므로 제목에 표시를 덧붙이지 않는다.
                title="{0}  {1}".format(
                    entry.get("name") or symbol, view.price_text(quotes.get(symbol))
                ),
                subtitle="{0} · {1} · ⌘↩ 관심종목 {2}".format(
                    symbol,
                    entry.get("market") or "",
                    "제거" if symbol in saved else "추가",
                ),
                arg=view.stock_url(symbol),
                uid=symbol,
                copy=symbol,
                icon=icons.for_stock(symbol, saved),
                mods=alfred.toggle_mod(symbol, symbol in saved),
            )
        )

    alfred.output(items)


def main():
    query = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    token = auth.access_token()

    if query:
        _search(token, query)
        return

    saved = store.watchlist()
    if saved:
        alfred.output(view.listing(token, saved, "관심종목"))
        return

    seen = store.recent()
    if seen:
        alfred.output(view.listing(token, seen, "최근 조회"))
        return

    alfred.empty(
        "종목명 또는 티커를 입력하세요",
        "검색 결과에서 ⌘↩ 를 누르면 관심종목으로 등록됩니다. 예: 삼성전자, 005930",
        icon=icons.SEARCH,
    )


if __name__ == "__main__":
    alfred.run(main)
