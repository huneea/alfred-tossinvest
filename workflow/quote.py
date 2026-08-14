#!/usr/bin/python3
"""Script Filter: 한 종목의 상세 시세.

현재가 외에 등락·시고저·거래량·호가·상하한가를 보여준다. 이 정보를 모으려면
prices/candles/orderbook/price-limits 를 각각 불러야 해서 한 화면에 4회 호출이
든다.

Script Filter 는 키 입력마다 실행되므로, 종목이 확정되기 전에는 상세를 부르지
않는다. 티커나 종목명이 정확히 일치할 때만 상세로 넘어가고, 그전에는 현재가만
붙인 후보 목록을 보여준다. '삼', '삼성', '삼성전' 을 지나 '삼성전자' 를 다 쳤을
때 한 번만 상세를 부르게 된다.
"""

from __future__ import annotations

import sys

from tossinvest import alfred, api, auth, fmt, store

STOCK_URL = "https://tossinvest.com/stocks/{0}"

# 호가는 단계가 많아 목록이 길어진다. 위에서 몇 단계만 보여준다.
ORDERBOOK_LEVELS = 3


def _exact_match(matches, query):
    """티커 또는 종목명이 정확히 일치하는 종목. 없으면 None."""
    needle = query.strip().lower()
    for entry in matches:
        if (entry.get("symbol") or "").lower() == needle:
            return entry
        if (entry.get("name") or "").lower() == needle:
            return entry
    return None


def _candidates(token, matches):
    quotes = api.prices(token, [e.get("symbol") for e in matches])
    saved = set(store.watchlist())

    items = []
    for entry in matches:
        symbol = entry.get("symbol") or ""
        quote = quotes.get(symbol) or {}
        items.append(
            alfred.item(
                title="{0}  {1}".format(
                    entry.get("name") or symbol,
                    fmt.money(quote.get("lastPrice"), quote.get("currency") or "KRW"),
                ),
                subtitle="{0} · 종목명을 끝까지 입력하면 상세 시세를 봅니다".format(symbol),
                arg=STOCK_URL.format(symbol),
                uid=symbol,
                copy=symbol,
                mods=alfred.toggle_mod(symbol, symbol in saved),
            )
        )
    alfred.output(items)


def _detail(token, entry):
    symbol = entry.get("symbol")
    name = entry.get("name") or symbol
    url = STOCK_URL.format(symbol)

    quote = api.prices(token, [symbol]).get(symbol) or {}
    currency = quote.get("currency") or "KRW"
    change = api.daily_change(token, symbol) or {}
    saved = set(store.watchlist())
    mods = alfred.toggle_mod(symbol, symbol in saved)

    def row(title, subtitle):
        return alfred.item(title, subtitle, arg=url, copy=symbol, mods=mods)

    rate = change.get("changeRate")
    headline = fmt.money(quote.get("lastPrice"), currency)
    if rate is not None:
        headline += "   {0}  ({1})".format(
            fmt.signed_rate(rate), fmt.signed_money(change.get("change"), currency)
        )

    items = [
        row(headline, "{0} · {1} · ↩ 토스증권에서 열기".format(name, symbol)),
        row(
            "시 {0} · 고 {1} · 저 {2}".format(
                fmt.money(change.get("open"), currency),
                fmt.money(change.get("high"), currency),
                fmt.money(change.get("low"), currency),
            ),
            "당일 시가 · 고가 · 저가",
        ),
        row(
            "거래량 {0}".format(fmt.number(change.get("volume"))),
            "전일 종가 {0}".format(fmt.money(change.get("prevClose"), currency)),
        ),
    ]

    # 호가와 상하한가는 없어도 나머지 화면은 쓸모가 있으므로 개별적으로 감싼다.
    try:
        book = api.orderbook(token, symbol)
        asks = list(reversed(book["asks"][:ORDERBOOK_LEVELS]))
        bids = book["bids"][:ORDERBOOK_LEVELS]
        for level in asks:
            items.append(row(
                "매도 {0}".format(fmt.money(level.get("price"), currency)),
                "잔량 {0}".format(fmt.number(level.get("volume"))),
            ))
        for level in bids:
            items.append(row(
                "매수 {0}".format(fmt.money(level.get("price"), currency)),
                "잔량 {0}".format(fmt.number(level.get("volume"))),
            ))
    except Exception:
        items.append(row("호가 조회 실패", "장 시간이 아니거나 호가를 제공하지 않는 종목입니다"))

    try:
        limits = api.price_limits(token, symbol)
        items.append(row(
            "상한 {0} · 하한 {1}".format(
                fmt.money(limits.get("upperLimitPrice"), currency),
                fmt.money(limits.get("lowerLimitPrice"), currency),
            ),
            "가격 제한폭",
        ))
    except Exception:
        pass

    alfred.output(items)


def main():
    query = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not query:
        alfred.empty("종목명 또는 티커를 입력하세요", "예: 삼성전자, 005930")
        return

    token = auth.access_token()
    matches = api.search_stocks(token, query, limit=10)
    if not matches:
        alfred.empty("검색 결과가 없습니다", "'{0}' 와 일치하는 종목이 없습니다.".format(query))
        return

    exact = _exact_match(matches, query)
    if exact is not None:
        _detail(token, exact)
    else:
        _candidates(token, matches)


if __name__ == "__main__":
    alfred.run(main)
