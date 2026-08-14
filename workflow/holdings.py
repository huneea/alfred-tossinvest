#!/usr/bin/python3
"""Script Filter: 내 계좌의 보유 종목과 평가손익."""

from __future__ import annotations

import sys

from tossinvest import alfred, api, auth, fmt

STOCK_URL = "https://tossinvest.com/stocks/{0}"


def _summary_item(summary):
    """맨 위에 붙일 계좌 전체 요약 항목."""
    total = summary.get("totalEvaluationAmount")
    profit = summary.get("totalProfitLoss")
    rate = summary.get("totalProfitLossRate")
    return alfred.item(
        title="총 평가금액  {0}".format(fmt.money(total)),
        subtitle="평가손익 {0} ({1}) · 매입 {2}".format(
            fmt.signed_money(profit),
            fmt.signed_rate(rate),
            fmt.money(summary.get("totalPurchaseAmount")),
        ),
        valid=False,
    )


def main():
    query = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()

    token = auth.access_token()
    account_seq = api.resolve_account_seq(token)
    data = api.holdings(token, account_seq)

    positions = data["holdings"]
    if not positions:
        alfred.empty("보유 종목이 없습니다", "계좌 {0}".format(account_seq))
        return

    items = [_summary_item(data["summary"])]
    for position in positions:
        symbol = position.get("symbol") or ""
        # 마스터에 종목명이 있지만 보유 목록만으로도 티커 필터링은 가능하다.
        if query and query not in symbol.lower():
            continue

        currency = position.get("currency") or "KRW"
        items.append(
            alfred.item(
                title="{0}  {1}  ({2})".format(
                    symbol,
                    fmt.money(position.get("evaluationAmount"), currency),
                    fmt.signed_rate(position.get("profitLossRate")),
                ),
                subtitle="{0}주 · 평단 {1} · 현재 {2} · 손익 {3}".format(
                    fmt.number(position.get("quantity")),
                    fmt.money(position.get("purchasePrice"), currency),
                    fmt.money(position.get("evaluationPrice"), currency),
                    fmt.signed_money(position.get("profitLoss"), currency),
                ),
                arg=STOCK_URL.format(symbol),
                uid=symbol,
                copy=symbol,
            )
        )

    if len(items) == 1:
        alfred.empty("일치하는 보유 종목이 없습니다", "'{0}'".format(query))
        return

    alfred.output(items)


if __name__ == "__main__":
    alfred.run(main)
