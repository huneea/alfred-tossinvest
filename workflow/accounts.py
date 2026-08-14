#!/usr/bin/python3
"""Script Filter: 계좌 목록과 매수 가능 금액.

TOSS_ACCOUNT_SEQ 에 넣을 accountSeq 를 확인하는 용도로도 쓴다. 엔터를 누르면
해당 seq 가 클립보드로 복사되도록 arg 로 넘긴다.
"""

from __future__ import annotations

from tossinvest import alfred, api, auth, fmt
from tossinvest.errors import TossError

# /api/v1/buying-power 의 응답 필드명을 공식 스키마로 확인하지 못했다. 실호출에서
# 확인되는 대로 이 목록을 정리한다. 하나도 맞지 않으면 화면에 실제 필드명을
# 그대로 띄워서 다음에 고칠 수 있게 한다.
BUYING_POWER_KEYS = ("amount", "buyingPower", "orderableAmount", "availableAmount", "cash")


def _label(account, seq):
    """계좌를 가리키는 사람이 읽을 이름.

    accountName·accountNumber 가 비어 오는 경우가 있어 순서대로 떨어뜨린다.
    """
    for key in ("accountName", "accountNumber"):
        value = account.get(key)
        if value:
            return str(value)
    return "계좌 {0}".format(seq)


def _buying_power_text(token, seq):
    try:
        power = api.buying_power(token, seq)
    except TossError as exc:
        # 이유를 감추면 원인을 알 수 없다. 짧게라도 그대로 보여준다.
        return "매수가능 조회 실패 ({0})".format(exc.title)

    if not isinstance(power, dict) or not power:
        return "매수가능 정보 없음"

    for key in BUYING_POWER_KEYS:
        if key in power:
            return "매수가능 {0}".format(
                fmt.money(power[key], power.get("currency") or "KRW")
            )

    return "매수가능 필드 미확인: {0}".format(", ".join(sorted(power.keys())))


def main():
    token = auth.access_token()
    found = api.accounts(token)
    if not found:
        alfred.empty("계좌가 없습니다", "이 API 키에 연결된 계좌를 찾지 못했습니다.")
        return

    items = []
    for account in found:
        # accountSeq 는 숫자로 오는 경우가 있다. 헤더 값과 클립보드 양쪽에서
        # 문자열이어야 한다.
        seq = str(account.get("accountSeq"))

        items.append(
            alfred.item(
                title=_label(account, seq),
                subtitle="seq {0} · {1} · {2}".format(
                    seq,
                    account.get("accountType") or "-",
                    _buying_power_text(token, seq),
                ),
                arg=seq,
                uid=seq,
                copy=seq,
            )
        )

    alfred.output(items)


if __name__ == "__main__":
    alfred.run(main)
