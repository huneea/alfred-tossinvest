#!/usr/bin/python3
"""Script Filter: 관심종목 목록과 종목 검색.

빈 쿼리면 관심종목(없으면 최근 조회)을 등락률과 함께 보여준다. 이 화면은 종목
수가 정해져 있어 종목당 캔들 한 번씩을 감당할 수 있다.

검색 결과에는 현재가만 붙인다. Script Filter 는 키 입력마다 실행되므로 결과마다
캔들을 부르면 곧바로 rate limit 에 걸린다.
"""

from __future__ import annotations

import sys

from tossinvest import alfred, api, auth, fmt, store

STOCK_URL = "https://tossinvest.com/stocks/{0}"


def _price_text(quote):
    if not quote:
        return "시세 없음"
    return fmt.money(quote.get("lastPrice"), quote.get("currency") or "KRW")


def _listing(token, symbols, heading):
    """관심종목·최근 조회 공용 렌더링. 등락률을 함께 보여준다."""
    quotes = api.prices(token, symbols)
    changes = api.daily_changes(token, symbols)
    names = api.symbol_names(token, symbols)
    saved = set(store.watchlist())

    items = []
    for symbol in symbols:
        quote = quotes.get(symbol)
        change = changes.get(symbol) or {}
        rate = change.get("changeRate")

        title = "{0}  {1}".format(names.get(symbol, symbol), _price_text(quote))
        if rate is not None:
            title += "  {0}".format(fmt.signed_rate(rate))

        detail = heading
        if change.get("volume") is not None:
            detail += " · 거래량 {0}".format(fmt.number(change["volume"]))

        items.append(
            alfred.item(
                title=title,
                subtitle="{0} · {1}".format(symbol, detail),
                arg=STOCK_URL.format(symbol),
                uid=symbol,
                copy=symbol,
                mods=alfred.toggle_mod(symbol, symbol in saved),
            )
        )
    return items


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
                    marker, entry.get("name") or symbol, _price_text(quotes.get(symbol))
                ),
                subtitle="{0} · {1} · ⌘↩ 관심종목 {2}".format(
                    symbol,
                    entry.get("market") or "",
                    "제거" if symbol in saved else "추가",
                ),
                arg=STOCK_URL.format(symbol),
                uid=symbol,
                copy=symbol,
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
        alfred.output(_listing(token, saved, "관심종목"))
        return

    seen = store.recent()
    if seen:
        alfred.output(_listing(token, seen, "최근 조회"))
        return

    alfred.empty(
        "종목명 또는 티커를 입력하세요",
        "검색 결과에서 ⌘↩ 를 누르면 관심종목으로 등록됩니다. 예: 삼성전자, 005930",
    )


if __name__ == "__main__":
    alfred.run(main)
