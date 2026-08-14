"""표시용 숫자 포매팅.

API 는 금액·수량·수익률을 문자열로 돌려준다. 부동소수점 오차를 피하려고
Decimal 로 다룬 뒤 문자열로 되돌린다.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

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
    """등락률을 부호와 함께. 보합은 부호 없이 0.00% 로 둔다."""
    rate = to_decimal(value)
    if rate is None:
        return "-"
    sign = "+" if rate > 0 else ("-" if rate < 0 else "")
    return "{0}{1}%".format(sign, number(abs(rate), 2))


def signed_money(value, currency="KRW"):
    """손익 금액을 부호와 함께."""
    amount = to_decimal(value)
    if amount is None:
        return "-"
    sign = "+" if amount > 0 else ("-" if amount < 0 else "")
    return "{0}{1}".format(sign, money(abs(amount), currency))


def round_won(value):
    """원 단위로 반올림한 Decimal. 계산으로 만든 금액을 표시·비교용으로 다듬는다."""
    amount = to_decimal(value)
    if amount is None:
        return None
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def signed_ratio(value):
    """소수비율로 오는 손익률을 퍼센트로 표시한다.

    holdings 계열의 rate 는 0.1077 처럼 소수비율이다. 캔들에서 직접 계산하는
    등락률(signed_rate)은 이미 퍼센트라 단위가 다르니 섞어 쓰지 않는다.
    """
    ratio = to_decimal(value)
    if ratio is None:
        return "-"
    return signed_rate(ratio * 100)


def korean_amount(value):
    """큰 금액을 조·억 단위로 줄인다. 거래대금처럼 자릿수가 큰 값에 쓴다."""
    amount = to_decimal(value)
    if amount is None:
        return "-"
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 10 ** 12:
        return "{0}{1}조".format(sign, number(amount / 10 ** 12, 1))
    if amount >= 10 ** 8:
        return "{0}{1}억".format(sign, number(amount / 10 ** 8, 0))
    return sign + number(amount)


def price(value):
    """Price 모델({"krw": ..., "usd": ...})을 문자열로.

    국내 종목만 있으면 usd 는 null 로 온다. 있는 통화만 이어 붙인다.
    """
    if not isinstance(value, dict):
        return money(value)

    parts = []
    for key, currency in (("krw", "KRW"), ("usd", "USD")):
        amount = to_decimal(value.get(key))
        if amount is not None and amount != 0:
            parts.append(money(amount, currency))
    if parts:
        return " + ".join(parts)

    # 전부 0 이거나 없을 때. krw 는 종목이 없어도 0 으로 오므로 0 을 그대로 보인다.
    return money(value.get("krw"), "KRW") if "krw" in value else "-"


def signed_price(value):
    """Price 모델을 부호와 함께. 손익 표시에 쓴다."""
    if not isinstance(value, dict):
        return signed_money(value)

    parts = []
    for key, currency in (("krw", "KRW"), ("usd", "USD")):
        amount = to_decimal(value.get(key))
        if amount is not None and amount != 0:
            parts.append(signed_money(amount, currency))
    if parts:
        return " + ".join(parts)
    return signed_money(value.get("krw"), "KRW") if "krw" in value else "-"
