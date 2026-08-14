#!/usr/bin/python3
"""Script Filter: 내 계좌의 보유 종목과 평가손익.

응답 구조가 중첩돼 있다. HoldingsOverview 안에 items(HoldingsItem 목록)와
합계가 들어 있고, 합계 금액은 통화별로 나뉜 Price 모델이다. 손익률은 퍼센트가
아니라 소수비율(0.1077 = 10.77%)이라 fmt.signed_ratio 로 표시한다.
"""

from __future__ import annotations

import sys

from tossinvest import alfred, api, auth, fmt, icons, store, text, view


def _overview_item(overview):
    """맨 위에 붙일 계좌 전체 요약."""
    market_value = overview.get("marketValue") or {}
    profit_loss = overview.get("profitLoss") or {}
    daily = overview.get("dailyProfitLoss") or {}

    subtitle = "평가손익 {0} ({1}) · 투자원금 {2}".format(
        fmt.signed_price(profit_loss.get("amount")),
        fmt.signed_ratio(profit_loss.get("rate")),
        fmt.price(overview.get("totalPurchaseAmount")),
    )
    if daily.get("rate") is not None:
        subtitle += " · 오늘 {0}".format(fmt.signed_ratio(daily.get("rate")))

    return alfred.item(
        title="총 평가금액  {0}".format(fmt.price(market_value.get("amount"))),
        subtitle=subtitle,
        valid=False,
        icon=icons.PORTFOLIO,
    )


def _position_item(position, saved):
    symbol = position.get("symbol") or ""
    name = position.get("name") or symbol
    currency = position.get("currency") or "KRW"

    market_value = position.get("marketValue") or {}
    profit_loss = position.get("profitLoss") or {}
    daily = position.get("dailyProfitLoss") or {}

    subtitle = "{0}주 · 평단 {1} · 현재 {2} · 손익 {3}".format(
        fmt.number(position.get("quantity")),
        fmt.money(position.get("averagePurchasePrice"), currency),
        fmt.money(position.get("lastPrice"), currency),
        fmt.signed_money(profit_loss.get("amount"), currency),
    )
    if daily.get("rate") is not None:
        subtitle += " · 오늘 {0}".format(fmt.signed_ratio(daily.get("rate")))

    return alfred.item(
        title="{0}  {1}  {2}".format(
            name,
            fmt.money(market_value.get("amount"), currency),
            fmt.signed_ratio(profit_loss.get("rate")),
        ),
        subtitle=subtitle,
        arg=view.stock_url(symbol),
        uid=symbol,
        copy=symbol,
        icon=icons.for_stock(symbol, saved),
        mods=alfred.toggle_mod(symbol, symbol in saved),
    )


def main():
    query = (sys.argv[1] if len(sys.argv) > 1 else "").strip()

    token = auth.access_token()
    account_seq = api.resolve_account_seq(token)
    overview = api.holdings(token, account_seq)

    positions = overview.get("items") or []
    if not positions:
        alfred.empty("보유 종목이 없습니다", "계좌 {0}".format(account_seq))
        return

    if query:
        needle = text.fold(query)
        positions = [
            p for p in positions
            if needle in text.fold(p.get("symbol")) or needle in text.fold(p.get("name"))
        ]
        if not positions:
            alfred.empty(
                "일치하는 보유 종목이 없습니다",
                "'{0}' 와 일치하는 종목을 보유하고 있지 않습니다.".format(query),
            )
            return

    saved = set(store.watchlist())
    items = [_overview_item(overview)]
    items.extend(_position_item(position, saved) for position in positions)
    alfred.live(items)


if __name__ == "__main__":
    alfred.run(main)
