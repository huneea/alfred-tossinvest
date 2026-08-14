"""종목 로고 아이콘 캐시.

Alfred 항목의 아이콘은 **로컬 파일 경로만** 받는다. URL 을 넣을 수 없으므로
로고를 쓰려면 미리 받아 디스크에 두고 그 경로를 넘겨야 한다.

로고는 Open API 가 주지 않는다. 토스 웹이 쓰는 정적 CDN 에 티커로 바로 접근되고
(`icn-sec-fill-005930.png` — `A` 접두어 없는 6자리다. 미국 종목은 `AAPL` 처럼
티커 그대로다), 없는 종목은 403 이라 있고 없고가 구분된다. **문서화된 계약이
아니다.** 언제든 경로가 바뀌거나 막힐 수 있으므로 실패는 전부 조용히 기존
아이콘으로 떨어뜨린다.

path() 는 디스크에 있는 것만 돌려주고 네트워크를 타지 않는다. 없는 것은 jobs 에
쌓아 두었다가 결과를 내보낸 뒤 받는다.
"""

from __future__ import annotations

import os
import re

from . import config, jobs

URL_TEMPLATE = "https://static.toss.im/png-icons/securities/icn-sec-fill-{0}.png"

FETCHER = "fetch_logos.py"

# 로고가 없는 종목(403)도 기억한다. 안 그러면 자동 갱신마다 같은 404 를 다시
# 물으러 나간다. 상장 초기에 로고가 나중에 붙는 경우가 있어 영구히 막지는 않는다.
MISS_TTL = 7 * 24 * 60 * 60

# 내려받는 동안 다음 갱신이 같은 종목을 또 요청하는 것을 막는다.
CLAIM_TTL = 60

# 티커는 API 가 주는 값이지만 파일 경로와 URL 을 동시에 만드는 데 쓰이므로
# 영숫자만 통과시킨다.
SAFE_SYMBOL = re.compile(r"\A[A-Za-z0-9]{1,16}\Z")

# 미국 상장 DR(주식예탁증서)은 CDN 에 로고가 없는 경우가 많다. SKHY(SK하이닉스
# ADR)는 티커·소문자·ISIN·대체 접두어 어느 경로로도 403 이다. 그런데 **같은 회사의
# 국내 상장분에는 로고가 있다.** 그쪽을 대신 쓴다.
#
# 아래 표는 이렇게 뽑았다. 다시 만들 일이 생기면 같은 규칙을 쓰면 된다.
#
#   NASDAQ·NYSE 마스터에서 securityType == "DEPOSITARY_RECEIPT" 인 종목 중,
#   name 에서 "(ADR)" 을 뗀 값이 KOSPI·KOSDAQ 종목명과 완전히 일치하는 것
#
# DR 375건 중 6건이 걸린다. 부분 일치를 허용하면 엉뚱한 회사가 붙을 수 있어
# 완전 일치만 쓴다. 국내 기업의 미국 DR 은 거의 늘지 않으므로 표로 둔다.
ADR_ORIGIN = {
    "SKHY": "000660",   # SK하이닉스
    "KEP": "015760",    # 한국전력
    "KT": "030200",     # KT
    "LPL": "034220",    # LG디스플레이
    "SKM": "017670",    # SK텔레콤
    "WYHG": "900340",   # 윙입푸드
}

_dir = None


def enabled():
    """로고 표시 여부. 꺼져 있으면 기존 아이콘을 그대로 쓴다."""
    return config.logos_enabled()


def directory():
    """로고 캐시 디렉터리. 지워져도 다시 받으면 되므로 cache_dir 아래에 둔다."""
    global _dir
    if _dir is None:
        _dir = os.path.join(config.cache_dir(), "logos")
        os.makedirs(_dir, exist_ok=True)
    return _dir


def paths(symbol):
    """(로고, 없음표식, 선점표식) 경로."""
    base = os.path.join(directory(), symbol)
    return base + ".png", base + ".miss", base + ".claim"


def path(symbol):
    """캐시에 있는 로고 경로. 없으면 None 을 돌려주고 받을 목록에 넣는다.

    네트워크는 절대 타지 않는다. 이 함수는 목록 한 화면에 종목 수만큼, 그리고
    갱신마다 다시 불린다.
    """
    if not symbol or not enabled() or not SAFE_SYMBOL.match(symbol):
        return None

    # DR 은 제 티커로 받으면 반드시 403 이다. 국내 상장분으로 바꿔서 받는다.
    symbol = ADR_ORIGIN.get(symbol, symbol)

    logo, miss, claim = paths(symbol)
    if os.path.exists(logo):
        return logo
    if jobs.fresh(miss, MISS_TTL):
        return None

    jobs.queue(FETCHER, symbol, claim, CLAIM_TTL)
    return None
