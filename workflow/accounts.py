#!/usr/bin/python3
"""Script Filter: 계좌 목록과 매수 가능 금액.

TOSS_ACCOUNT_SEQ 에 넣을 accountSeq 를 확인하는 용도로도 쓴다. 엔터를 누르면
해당 seq 가 클립보드로 복사되도록 arg 로 넘긴다.
"""

from __future__ import annotations

from tossinvest import alfred, api, auth, fmt
from tossinvest.errors import TossError

# BuyingPowerResponse 는 currency 와 cashBuyingPower 두 필드다. 응답이 바뀌어도
# 화면이 조용히 비지 않도록, 못 찾으면 실제 필드명을 그대로 띄운다.
BUYING_POWER_KEY = "cashBuyingPower"

# 매수가능금액은 통화별로 따로 조회한다. 원화 계좌 기준으로 KRW 를 본다.
BUYING_POWER_CURRENCY = "KRW"

# Account.accountType 의 enum. 문서가 "알 수 없는 값을 처리하라"고 명시하고 있어
# 매핑에 없으면 원래 값을 그대로 보여준다.
ACCOUNT_TYPES = {
    "BROKERAGE": "위탁",
    "OVERSEAS_DERIVATIVES": "해외파생",
    "PENSION_SAVINGS": "연금저축",
    "RESHORING_INVESTMENT": "리쇼어링투자",
}


def _label(account, seq):
    """계좌를 가리키는 사람이 읽을 이름.

    계좌번호 필드는 accountNo 다. accountName 이나 accountNumber 는 없다.
    """
    number = account.get("accountNo")
    if number:
        return str(number)
    return "계좌 {0}".format(seq)


def _type_label(account):
    raw = account.get("accountType")
    if not raw:
        return "-"
    return ACCOUNT_TYPES.get(raw, str(raw))


def _buying_power_text(token, seq):
    try:
        power = api.buying_power(token, seq, BUYING_POWER_CURRENCY)
    except TossError as exc:
        # 이유를 감추면 원인을 알 수 없다. API 가 돌려준 설명까지 보여준다.
        # 어떤 파라미터가 빠졌는지는 대개 여기에 적혀 있다.
        detail = " {0}".format(exc.subtitle) if exc.subtitle else ""
        return "매수가능 실패 [{0}]{1}".format(exc.title, detail)

    if not isinstance(power, dict) or not power:
        return "매수가능 정보 없음"

    if BUYING_POWER_KEY in power:
        return "매수가능 {0}".format(
            fmt.money(power[BUYING_POWER_KEY], power.get("currency") or BUYING_POWER_CURRENCY)
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
                    _type_label(account),
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
