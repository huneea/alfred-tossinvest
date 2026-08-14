"""워크플로우 전역에서 쓰는 예외.

Alfred 는 스크립트가 죽으면 stderr 를 디버거에만 흘리고 사용자에게는 아무것도
보여주지 않는다. 그래서 예외마다 사람이 읽을 제목/부제를 들려보내 Script Filter
결과 항목으로 그대로 렌더링할 수 있게 한다.
"""

from __future__ import annotations


class TossError(Exception):
    """이 워크플로우가 발생시키는 모든 예외의 기반."""

    def __init__(self, title, subtitle=""):
        super().__init__("{0}: {1}".format(title, subtitle) if subtitle else title)
        self.title = title
        self.subtitle = subtitle


class ConfigError(TossError):
    """자격증명 등 필수 설정이 비어 있을 때."""


class AuthError(TossError):
    """토큰 발급 실패. client_id/secret 오류이거나 AUTH rate limit 초과."""


class ApiError(TossError):
    """API 가 2xx 가 아닌 응답을 돌려줬을 때."""

    def __init__(self, title, subtitle="", status=None, code=None, request_id=None):
        super().__init__(title, subtitle)
        self.status = status
        self.code = code
        self.request_id = request_id
