"""OAuth2 Client Credentials 토큰 발급과 캐싱.

Script Filter 는 사용자가 한 글자 칠 때마다 실행된다. 매번 토큰을 새로 받으면
AUTH 그룹 rate limit(5 req/s)에 바로 걸리므로 디스크에 캐싱한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

from . import client, config
from .errors import AuthError

TOKEN_PATH = "token.json"

# 만료 직전에 발급된 토큰으로 요청을 보내다 401 을 맞는 걸 피하기 위한 여유분(초).
EXPIRY_MARGIN = 60


def _cache_file():
    return os.path.join(config.cache_dir(), TOKEN_PATH)


def _fingerprint(client_id):
    """client_id 가 바뀌면 캐시를 무효화하기 위한 짧은 지문."""
    return hashlib.sha256(client_id.encode("utf-8")).hexdigest()[:12]


def _read_cache(fingerprint):
    try:
        with open(_cache_file(), "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except (IOError, OSError, ValueError):
        return None

    if not isinstance(cached, dict):
        return None
    if cached.get("fingerprint") != fingerprint:
        return None
    if cached.get("expires_at", 0) - EXPIRY_MARGIN <= time.time():
        return None
    return cached.get("access_token") or None


def _write_cache(fingerprint, token, expires_in):
    path = _cache_file()
    payload = {
        "fingerprint": fingerprint,
        "access_token": token,
        "expires_at": time.time() + expires_in,
    }
    # 파일에 베어러 토큰이 들어가므로 소유자만 읽을 수 있게 만든 뒤 내용을 쓴다.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def access_token(force_refresh=False):
    """유효한 access token 을 반환. 캐시가 살아 있으면 네트워크를 타지 않는다."""
    client_id, client_secret = config.client_credentials()
    fingerprint = _fingerprint(client_id)

    if not force_refresh:
        cached = _read_cache(fingerprint)
        if cached:
            return cached

    payload = client.post_form(
        "/oauth2/token",
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )

    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise AuthError("토큰 발급 실패", "응답에 access_token 이 없습니다.")

    token = payload["access_token"]
    try:
        expires_in = int(payload.get("expires_in", 0))
    except (TypeError, ValueError):
        expires_in = 0
    # expires_in 이 없거나 이상하면 짧게 잡아 다음 호출에서 다시 받게 한다.
    if expires_in <= 0:
        expires_in = 300

    try:
        _write_cache(fingerprint, token, expires_in)
    except (IOError, OSError):
        # 캐시 실패는 치명적이지 않다. 이번 요청은 그대로 진행한다.
        pass

    return token
