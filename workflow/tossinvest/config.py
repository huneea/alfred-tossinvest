"""환경변수 기반 설정.

자격증명은 Alfred 워크플로우 환경변수(Configure Workflow > Variables)로 주입한다.
Alfred 는 워크플로우 변수를 프로세스 환경변수로 그대로 넘겨준다. 값에는 "Don't
Export" 를 걸어 워크플로우를 내보낼 때 딸려가지 않게 한다.

터미널에서 직접 돌려볼 때는 같은 이름의 셸 환경변수를 export 하면 된다.
"""

from __future__ import annotations

import os

from .errors import ConfigError

BUNDLE_ID = "me.hhjung.tossinvest"
BASE_URL = "https://openapi.tossinvest.com"

ENV_CLIENT_ID = "TOSS_CLIENT_ID"
ENV_CLIENT_SECRET = "TOSS_CLIENT_SECRET"
ENV_ACCOUNT_SEQ = "TOSS_ACCOUNT_SEQ"
ENV_REFRESH = "TOSS_REFRESH_SECONDS"

# Alfred 가 rerun 으로 받아주는 범위는 0.1~5.0 초다. 그보다 자주 돌면 값을 받아
# 그리기도 전에 다시 실행되고 rate limit 만 축낸다.
REFRESH_MIN = 1.0
REFRESH_MAX = 5.0
REFRESH_DEFAULT = 2.0

# 네트워크 타임아웃(초). Alfred 는 응답이 느리면 사용자가 그냥 창을 닫아버리므로
# 넉넉하게 잡기보다 빨리 실패시키고 원인을 보여주는 편이 낫다.
TIMEOUT = 10


def _require(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            "설정이 필요합니다",
            "{0} 환경변수가 비어 있습니다. Alfred 워크플로우 설정에서 등록하세요.".format(name),
        )
    return value


def client_credentials():
    """(client_id, client_secret) 반환. 하나라도 없으면 ConfigError."""
    return _require(ENV_CLIENT_ID), _require(ENV_CLIENT_SECRET)


def account_seq():
    """기본 계좌 seq. 미설정이면 None — 호출부가 계좌 목록에서 첫 번째를 고른다."""
    return os.environ.get(ENV_ACCOUNT_SEQ, "").strip() or None


def refresh_seconds():
    """결과 화면 자동 갱신 주기(초). 끄면 None.

    Alfred 는 Script Filter 출력의 rerun 값만큼 기다렸다가 같은 화면을 다시
    실행한다. 갱신마다 API 를 다시 부르므로 사용자가 끌 수 있어야 한다.
    """
    raw = os.environ.get(ENV_REFRESH, "").strip()
    if not raw:
        return REFRESH_DEFAULT
    try:
        value = float(raw)
    except ValueError:
        return REFRESH_DEFAULT
    if value <= 0:
        return None
    return min(REFRESH_MAX, max(REFRESH_MIN, value))


def cache_dir():
    """쓰기 가능한 캐시 디렉터리 경로를 보장해서 반환.

    Alfred 안에서는 alfred_workflow_cache 가 주어지지만, 터미널에서 직접 실행할
    때는 없으므로 표준 캐시 경로로 떨어뜨린다.

    여기 있는 것은 언제 지워져도 다시 만들 수 있는 것만 둔다. 관심종목처럼 사용자가
    쌓은 데이터는 data_dir() 로 간다.
    """
    path = os.environ.get("alfred_workflow_cache", "").strip()
    if not path:
        path = os.path.expanduser("~/Library/Caches/" + BUNDLE_ID)
    os.makedirs(path, exist_ok=True)
    return path


def data_dir():
    """사용자 데이터 디렉터리. 관심종목·최근 조회처럼 잃으면 안 되는 것을 둔다.

    Alfred 는 캐시 디렉터리를 임의로 비울 수 있으므로 캐시와 반드시 분리한다.
    """
    path = os.environ.get("alfred_workflow_data", "").strip()
    if not path:
        path = os.path.expanduser("~/Library/Application Support/" + BUNDLE_ID)
    os.makedirs(path, exist_ok=True)
    return path
