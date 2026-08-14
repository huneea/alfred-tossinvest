#!/usr/bin/python3
"""Script Filter: 계좌 목록과 매수 가능 금액.

TOSS_ACCOUNT_SEQ 에 넣을 accountSeq 를 확인하는 용도로도 쓴다. 엔터를 누르면
해당 seq 가 클립보드로 복사되도록 arg 로 넘긴다.
"""

from __future__ import annotations

from tossinvest import alfred, api, auth, fmt


def main():
    token = auth.access_token()
    found = api.accounts(token)
    if not found:
        alfred.empty("계좌가 없습니다", "이 API 키에 연결된 계좌를 찾지 못했습니다.")
        return

    items = []
    for account in found:
        seq = account.get("accountSeq") or ""

        # 매수 가능 금액은 계좌별로 따로 호출해야 한다. 계좌 수는 보통 한 자릿수라
        # 순차 호출로 충분하고, 실패해도 계좌 자체는 보여준다.
        try:
            power = api.buying_power(token, seq)
            power_text = "매수가능 {0}".format(fmt.money(power.get("amount")))
        except Exception:
            power_text = "매수가능 조회 실패"

        items.append(
            alfred.item(
                title=account.get("accountName") or account.get("accountNumber") or seq,
                subtitle="{0} · {1} · {2}".format(
                    account.get("accountNumber") or "-",
                    account.get("accountType") or "-",
                    power_text,
                ),
                arg=seq,
                uid=seq,
                copy=seq,
            )
        )

    alfred.output(items)


if __name__ == "__main__":
    alfred.run(main)
