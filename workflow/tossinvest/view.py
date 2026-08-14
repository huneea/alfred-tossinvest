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


def listing(token, symbols, heading):
    """종목코드 목록을 현재가·등락률이 붙은 항목으로 만든다.

    등락률은 종목당 캔들 한 번이 든다. 종목 수가 정해진 화면에서만 부르라는
    전제이며, 검색 결과처럼 개수가 유동적인 곳에서는 쓰지 않는다.
    """
    quotes = api.prices(token, symbols)
    # 등락은 화면에 보여줄 현재가와 같은 기준으로 계산한다. 캔들 종가로 계산하면
    # 표시된 현재가와 등락이 서로 맞지 않는다.
    last_prices = {symbol: quote.get("lastPrice") for symbol, quote in quotes.items()}
    changes = api.daily_changes(token, symbols, last_prices)
    names = api.symbol_names(token, symbols)
    saved = set(store.watchlist())

    items = []
    for symbol in symbols:
        change = changes.get(symbol) or {}
        rate = change.get("changeRate")

        title = "{0}  {1}".format(names.get(symbol, symbol), price_text(quotes.get(symbol)))
        if rate is not None:
            title += "  {0}".format(fmt.signed_rate(rate))

        detail = heading
        if change.get("volume") is not None:
            detail += " · 거래량 {0}".format(fmt.number(change["volume"]))
        detail += " · ⌘↩ 관심종목 {0}".format("제거" if symbol in saved else "추가")

        items.append(
            alfred.item(
                title=title,
                subtitle="{0} · {1}".format(symbol, detail),
                arg=stock_url(symbol),
                uid=symbol,
                copy=symbol,
                # 등락을 못 구한 종목은 관심종목 표시로 대신한다.
                icon=icons.for_change(rate) or (icons.STAR if symbol in saved else None),
                mods=alfred.toggle_mod(symbol, symbol in saved),
            )
        )
    return items
