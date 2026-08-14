"""urllib 기반 HTTP 계층.

이 워크플로우는 조회 전용이다. 주문/정정/취소(POST /api/v1/orders 계열)는
의도적으로 구현하지 않는다. 토스증권 Open API 는 샌드박스가 없어 모든 호출이
실계좌에 그대로 나가므로, 주문 경로를 코드에 두지 않는 것 자체가 안전장치다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .config import BASE_URL, TIMEOUT
from .errors import ApiError


def _decode(raw):
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _raise_for_error(status, payload, fallback):
    """API 오류 응답을 사람이 읽을 수 있는 ApiError 로 변환."""
    code = None
    request_id = None
    message = fallback

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            # 일반 API 엔드포인트: {"error": {"code", "message", "requestId"}}
            code = error.get("code")
            request_id = error.get("requestId")
            message = error.get("message") or message
        elif isinstance(error, str):
            # OAuth 엔드포인트: {"error", "error_description"}
            code = error
            message = payload.get("error_description") or error

    if status == 403:
        raise ApiError(
            "403 — IP 허용 목록을 확인하세요",
            "등록되지 않은 IP 에서의 요청은 차단됩니다. 토스증권 WTS > 설정 > Open API "
            "에서 현재 공인 IP 를 등록하세요. ({0})".format(message),
            status=status,
            code=code,
            request_id=request_id,
        )
    if status == 429:
        raise ApiError(
            "429 — 요청이 너무 잦습니다",
            "잠시 후 다시 시도하세요. ({0})".format(message),
            status=status,
            code=code,
            request_id=request_id,
        )

    raise ApiError(
        "{0} — 요청 실패".format(status),
        message,
        status=status,
        code=code,
        request_id=request_id,
    )


def _send(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return _decode(res.read())
    except urllib.error.HTTPError as exc:
        payload = _decode(exc.read())
        _raise_for_error(exc.code, payload, exc.reason or "알 수 없는 오류")
    except urllib.error.URLError as exc:
        raise ApiError("네트워크 오류", str(exc.reason))


def post_form(path, fields):
    """application/x-www-form-urlencoded POST. 토큰 발급 전용이라 인증 헤더가 없다."""
    body = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    return _send(req)


def get(path, token, params=None, account_seq=None):
    """인증된 GET 요청을 보내고 {"result": ...} 껍데기를 벗겨서 반환."""
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", "Bearer " + token)
    if account_seq:
        # accountSeq 는 문서와 달리 숫자로 오는 경우가 있다. 헤더 값은 문자열이어야
        # urllib 이 받아준다.
        req.add_header("X-Tossinvest-Account", str(account_seq))

    payload = _send(req)
    if isinstance(payload, dict) and "result" in payload:
        return payload["result"]
    return payload
