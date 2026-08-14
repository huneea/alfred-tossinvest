#!/usr/bin/python3
"""Script Filter: 시장 랭킹 (거래대금·거래량 상위, 급등·급락).

관심종목 밖을 보여주는 화면이다. 랭킹은 lastPrice·basePrice·changeRate 를 직접
주므로 등락률을 계산하지 않고, 호출 한 번으로 목록 전체를 받는다.

인자로 어떤 랭킹인지 고른다. 비우면 거래대금 상위를 보여주고, 인자가 어떤
이름과도 맞지 않으면 고를 수 있는 목록을 띄운다. 탭으로 완성하면 된다.
"""

from __future__ import annotations

import sys

from tossinvest import alfred, api, auth, fmt, icons, store, text, view

DEFAULT_TYPE = "MARKET_TRADING_AMOUNT"


def _match(query):
    """입력과 맞는 랭킹 종류. 없으면 None."""
    needle = text.fold(query)
    if not needle:
        return DEFAULT_TYPE
    for key, label in api.RANKING_TYPES.items():
        if text.fold(label).startswith(needle) or needle in text.fold(label):
            return key
    return None


def _chooser(query):
    """고를 수 있는 랭킹 목록. 탭으로 이름을 완성한다."""
    alfred.output([
        alfred.item(
            title=label,
            subtitle="⇥ 로 완성하거나 이름을 마저 입력하세요",
            valid=False,
            autocomplete=label,
            icon=icons.SEARCH,
        )
        for label in api.RANKING_TYPES.values()
    ])


def main():
    query = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    ranking_type = _match(query)
    if ranking_type is None:
        _chooser(query)
        return

    token = auth.access_token()
    _, entries = api.rankings(token, ranking_type)
    if not entries:
        alfred.empty(
            "{0} 집계가 없습니다".format(api.RANKING_TYPES[ranking_type]),
            "장 시작 전이거나 휴장일일 수 있습니다.",
        )
        return

    info = api.symbol_info(token, [e.get("symbol") for e in entries])
    saved = set(store.watchlist())

    items = []
    for entry in entries:
        symbol = entry.get("symbol") or ""
        price = entry.get("price") or {}
        currency = entry.get("currency") or "KRW"
        name = (info.get(symbol) or {}).get("name") or symbol

        items.append(
            alfred.item(
                title="{0}. {1}  {2}  {3}".format(
                    entry.get("rank"),
                    view.stock_name(name, symbol, saved),
                    fmt.money(price.get("lastPrice"), currency),
                    fmt.colored_ratio(price.get("changeRate")),
                ),
                # 어떤 랭킹인지는 모든 행이 같으므로 넣지 않는다. 행마다 달라지는
                # 값만 부제에 둔다.
                subtitle="{0} · 거래대금 {1} · ⌘↩ 관심종목 {2}".format(
                    symbol,
                    fmt.korean_amount(entry.get("tradingAmount")),
                    "제거" if symbol in saved else "추가",
                ),
                arg=view.stock_url(symbol),
                uid=symbol,
                copy=symbol,
                icon=icons.for_stock(symbol, saved),
                mods=alfred.stock_mods(symbol, symbol in saved),
                autocomplete=name,
            )
        )

    alfred.live(items)


if __name__ == "__main__":
    alfred.run(main)
