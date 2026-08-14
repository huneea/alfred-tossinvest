"""표시용 숫자 포매팅.

API 는 금액·수량·수익률을 문자열로 돌려준다. 부동소수점 오차를 피하려고
Decimal 로 다룬 뒤 문자열로 되돌린다.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

CURRENCY_SYMBOL = {"KRW": "₩", "USD": "$"}


def to_decimal(value):
    """문자열/숫자를 Decimal 로. 변환 불가면 None."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _strip_zeros(text):
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".")


def number(value, places=None):
    """천 단위 구분 기호를 넣어 반환. 변환 불가면 원본을 그대로 돌려준다."""
    amount = to_decimal(value)
    if amount is None:
        return str(value) if value is not None else "-"

    if places is None:
        # KRW 처럼 정수로 떨어지면 소수점을 붙이지 않는다.
        formatted = "{0:,f}".format(amount)
        return _strip_zeros(formatted)
    return "{0:,.{1}f}".format(amount, places)


def money(value, currency="KRW"):
    """통화 기호를 붙인 금액. USD 는 소수점 둘째 자리까지.

    값이 없으면 통화 기호까지 빼고 "-" 만 돌려준다. "₩-" 는 0원처럼 읽혀서
    오해를 부른다.
    """
    if to_decimal(value) is None:
        return "-"
    places = 2 if currency == "USD" else None
    return "{0}{1}".format(CURRENCY_SYMBOL.get(currency, ""), number(value, places))


def signed_rate(value):
    """수익률을 부호와 함께. 상승 ▲ / 하락 ▼ 로 방향을 표시한다."""
    rate = to_decimal(value)
    if rate is None:
        return "-"
    marker = "▲" if rate > 0 else ("▼" if rate < 0 else "―")
    return "{0} {1}%".format(marker, number(abs(rate), 2))


def signed_money(value, currency="KRW"):
    """손익 금액을 부호와 함께."""
    amount = to_decimal(value)
    if amount is None:
        return "-"
    sign = "+" if amount > 0 else ("-" if amount < 0 else "")
    return "{0}{1}".format(sign, money(abs(amount), currency))
