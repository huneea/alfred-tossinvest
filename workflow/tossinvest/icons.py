"""아이콘 경로.

Alfred 는 항목의 icon.path 를 워크플로우 디렉터리 기준 상대 경로로 해석한다.
파일은 build/icons.py 가 생성한다.
"""

from __future__ import annotations

UP = "icons/up.png"
DOWN = "icons/down.png"
FLAT = "icons/flat.png"
STAR = "icons/star.png"
ASK = "icons/ask.png"
BID = "icons/bid.png"
INFO = "icons/info.png"
WARN = "icons/warn.png"
ACCOUNT = "icons/account.png"


def for_change(value):
    """등락 값의 부호로 아이콘을 고른다.

    부호만 보므로 퍼센트든 소수비율이든 상관없다. 값이 없으면 None 을 돌려주고,
    호출부는 아이콘 없이 기본 아이콘으로 둔다.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 0:
        return UP
    if number < 0:
        return DOWN
    return FLAT
