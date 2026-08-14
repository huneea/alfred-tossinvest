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
        marker = "★ " if symbol in saved else ""
        items.append(
            alfred.item(
                title="{0}{1}  {2}".format(
                    marker, entry.get("name") or symbol, view.price_text(quotes.get(symbol))
                ),
                subtitle="{0} · {1} · ⌘↩ 관심종목 {2}".format(
                    symbol,
                    entry.get("market") or "",
                    "제거" if symbol in saved else "추가",
                ),
                arg=view.stock_url(symbol),
                uid=symbol,
                copy=symbol,
                # 검색 결과에는 등락을 붙이지 않으므로(종목당 호출이 든다)
                # 관심종목 여부만 아이콘으로 표시한다.
                icon=icons.STAR if symbol in saved else None,
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
    )


if __name__ == "__main__":
    alfred.run(main)
