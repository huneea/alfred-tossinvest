"""문자열 비교 정규화.

한글은 완성형(NFC, '하')과 조합형(NFD, 'ㅎ'+'ㅏ')으로 다르게 표현될 수 있다.
눈으로는 같지만 파이썬 문자열로는 다르므로 in·startswith·== 이 모두 실패한다.
macOS 는 입력 경로에 따라 NFD 를 흘려보내는 반면 API 가 주는 종목명은 NFC 라,
정규화하지 않으면 '하이닉스' 같은 검색어가 입력 방식에 따라 되기도 하고 안 되기도
한다.

비교에 쓰는 모든 문자열은 여기를 통과시킨다.
"""

from __future__ import annotations

import unicodedata


def fold(value):
    """비교용으로 정규화한다. NFC 통일 + 앞뒤 공백 제거 + 소문자."""
    if not value:
        return ""
    return unicodedata.normalize("NFC", value).strip().lower()
