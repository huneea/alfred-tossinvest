"""도메인 단위 조회 함수.

진입 스크립트가 엔드포인트 경로나 응답 껍데기를 직접 다루지 않도록 감싼다.
"""

from __future__ import annotations

import json
import os
import time

from . import client, config
from .errors import ApiError

# 종목 마스터는 하루 한 번만 받으면 충분하다. Script Filter 는 타이핑마다
# 실행되므로 매번 전종목을 내려받으면 rate limit 과 지연 둘 다 문제가 된다.
MASTER_TTL = 24 * 60 * 60
DEFAULT_MARKETS = ("KOSPI", "KOSDAQ")

# GET /api/v1/prices 의 symbols 파라미터 상한.
MAX_SYMBOLS_PER_CALL = 200


def accounts(token):
    """계좌 목록."""
    result = client.get("/api/v1/accounts", token)
    return result if isinstance(result, list) else []


def resolve_account_seq(token):
    """사용할 계좌 seq 를 결정.

    환경변수에 지정돼 있으면 그대로 쓰고, 없으면 계좌 목록의 첫 번째를 쓴다.
    계좌가 여러 개인데 특정 계좌를 고정하고 싶으면 TOSS_ACCOUNT_SEQ 를 설정한다.
    """
    configured = config.account_seq()
    if configured:
        return configured

    found = accounts(token)
    if not found:
        raise ApiError("계좌를 찾을 수 없습니다", "이 API 키에 연결된 계좌가 없습니다.")
    return found[0].get("accountSeq")


def holdings(token, account_seq):
    """보유 종목과 합계. {"holdings": [...], "summary": {...}} 형태."""
    result = client.get("/api/v1/holdings", token, account_seq=account_seq)
    if not isinstance(result, dict):
        return {"holdings": [], "summary": {}}
    return {
        "holdings": result.get("holdings") or [],
        "summary": result.get("summary") or {},
    }


def buying_power(token, account_seq):
    """매수 가능 금액."""
    return client.get("/api/v1/buying-power", token, account_seq=account_seq) or {}


def prices(token, symbols):
    """종목별 현재가를 {symbol: 항목} 딕셔너리로 반환."""
    symbols = [s for s in symbols if s]
    if not symbols:
        return {}

    collected = {}
    for start in range(0, len(symbols), MAX_SYMBOLS_PER_CALL):
        chunk = symbols[start:start + MAX_SYMBOLS_PER_CALL]
        result = client.get("/api/v1/prices", token, params={"symbols": ",".join(chunk)})
        for entry in result or []:
            symbol = entry.get("symbol")
            if symbol:
                collected[symbol] = entry
    return collected


def _master_cache_file(market):
    return os.path.join(config.cache_dir(), "stocks-{0}.json".format(market))


def _load_master_cache(market):
    path = _master_cache_file(market)
    try:
        if time.time() - os.path.getmtime(path) > MASTER_TTL:
            return None
        with open(path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except (IOError, OSError, ValueError):
        return None
    return cached if isinstance(cached, list) else None


def _store_master_cache(market, entries):
    try:
        with open(_master_cache_file(market), "w", encoding="utf-8") as handle:
            json.dump(entries, handle, ensure_ascii=False)
    except (IOError, OSError):
        # 캐시를 못 써도 이번 조회 자체는 성공했으므로 그대로 진행한다.
        pass


def stock_master(token, markets=DEFAULT_MARKETS):
    """상장 종목 마스터를 합쳐서 반환. 시장별로 하루 단위 캐싱한다."""
    entries = []
    for market in markets:
        cached = _load_master_cache(market)
        if cached is None:
            cached = client.get(
                "/api/v1/stocks/all",
                token,
                params={"market": market, "status": "ACTIVE"},
            ) or []
            _store_master_cache(market, cached)
        for entry in cached:
            entry.setdefault("market", market)
        entries.extend(cached)
    return entries


def search_stocks(token, query, limit=15, markets=DEFAULT_MARKETS):
    """종목명 또는 티커로 마스터를 로컬 검색.

    매 키 입력마다 API 를 때리는 대신 캐싱된 마스터를 필터링한다. 티커 완전
    일치 > 이름 시작 일치 > 부분 일치 순으로 정렬한다.
    """
    needle = (query or "").strip().lower()
    if not needle:
        return []

    scored = []
    for entry in stock_master(token, markets):
        symbol = (entry.get("symbol") or "").lower()
        name = (entry.get("name") or "").lower()

        if symbol == needle:
            rank = 0
        elif name == needle:
            rank = 1
        elif name.startswith(needle):
            rank = 2
        elif symbol.startswith(needle):
            rank = 3
        elif needle in name:
            rank = 4
        else:
            continue

        scored.append((rank, len(name), entry))

    scored.sort(key=lambda row: (row[0], row[1]))
    return [entry for _, _, entry in scored[:limit]]
