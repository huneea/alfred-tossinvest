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


def money_with_krw(value, currency="KRW", rate=None):
    """외화 금액 옆에 원화 환산을 덧붙인다.

    환율이 없으면 원래 표기만 돌려준다. 환산은 곁들이는 정보라 없다고 화면이
    망가지면 안 된다. 원화 종목에는 애초에 붙일 것이 없다.
    """
    text = money(value, currency)
    amount = to_decimal(value)
    if currency == "KRW" or rate is None or amount is None:
        return text
    return "{0} ({1})".format(text, money(round_won(amount * rate), "KRW"))


RATE_PLACES = Decimal("0.01")


def _shown_rate(value):
    """화면에 찍힐 자리수로 반올림한 등락률. 부호·색을 이 값으로 판단한다.

    반올림 전 값으로 부호를 정하면 `+0.00%` 처럼 앞뒤가 안 맞는 표기가 나온다.
    0.002% 는 오른 것이 맞지만 소수 둘째 자리까지만 보여주는 화면에서는 보합으로
    읽히는 게 자연스럽다.
    """
    rate = to_decimal(value)
    if rate is None:
        return None
    return rate.quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


def signed_rate(value):
    """등락률을 부호와 함께. 보합은 부호 없이 0.00% 로 둔다."""
    rate = _shown_rate(value)
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


# 상승 난색, 하락 한색. 국내 시장 관례를 따른다.
#
# 소형 다이아몬드를 쓰는 이유는 크기다. 🔴/🔵 는 이름대로 large circle 이라
# 글자 칸의 79% 를 잉크로 채워 목록에서 수치보다 이모지가 먼저 눈에 들어온다.
# 🔸/🔹 는 30% 로 절반 이하다. 다만 유니코드에 "small red diamond" 가 없어
# 상승은 빨강 대신 주황이 된다. 크기를 얻는 대가로 받아들인 타협이다.
RATE_UP = "🔸"
RATE_DOWN = "🔹"


def colored_rate(value):
    """등락률 앞에 색 이모지를 붙인다.

    Alfred 결과 항목에는 텍스트 스타일·색상 키가 없다. 색으로 등락을 구분하려면
    이모지가 유일한 수단이다. 방향과 색을 동시에 주는 이모지는 없어서(방향
    이모지는 전부 회색) 색은 이모지가, 방향은 +/- 부호가 맡는다.

    눈으로 훑는 제목에만 쓴다. 부제까지 넣으면 이모지가 너무 많아진다.
    보합에는 붙이지 않는다.
    """
    rate = _shown_rate(value)
    if rate is None:
        return "-"
    text = signed_rate(rate)
    if rate > 0:
        return "{0} {1}".format(RATE_UP, text)
    if rate < 0:
        return "{0} {1}".format(RATE_DOWN, text)
    return text


def colored_ratio(value):
    """소수비율로 오는 손익률을 색 이모지와 함께 퍼센트로."""
    ratio = to_decimal(value)
    if ratio is None:
        return "-"
    return colored_rate(ratio * 100)


def signed_number(value, unit=""):
    """부호를 붙인 수량. 순매수처럼 음수가 의미를 갖는 값에 쓴다."""
    amount = to_decimal(value)
    if amount is None:
        return "-"
    sign = "+" if amount > 0 else ("-" if amount < 0 else "")
    return "{0}{1}{2}".format(sign, number(abs(amount)), unit)


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
