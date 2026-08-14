"""도메인 단위 조회 함수.

진입 스크립트가 엔드포인트 경로나 응답 껍데기를 직접 다루지 않도록 감싼다.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from . import client, config, fmt, text
from .errors import ApiError, TossError

# 종목 마스터는 하루 한 번만 받으면 충분하다. Script Filter 는 타이핑마다
# 실행되므로 매번 전종목을 내려받으면 rate limit 과 지연 둘 다 문제가 된다.
MASTER_TTL = 24 * 60 * 60
DEFAULT_MARKETS = ("KOSPI", "KOSDAQ")

# GET /api/v1/prices 의 symbols 파라미터 상한.
MAX_SYMBOLS_PER_CALL = 200

# 등락률용 캔들을 동시에 몇 개까지 가져올지. MARKET_DATA_CHART 가 20 req/s 이므로
# 그 아래로 넉넉히 잡는다.
CHANGE_WORKERS = 6


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


def candles(token, symbol, interval="1d", count=2):
    """시간순으로 정렬된 캔들 목록.

    API 가 어떤 순서로 주는지 문서에 명시돼 있지 않으므로 timestamp 로 직접
    정렬한다. 순서를 가정하면 전일 종가와 당일 종가가 뒤바뀔 수 있다.
    """
    result = client.get(
        "/api/v1/candles",
        token,
        params={"symbol": symbol, "interval": interval, "count": count},
    )
    entries = (result or {}).get("candles") or []
    return sorted(entries, key=lambda c: c.get("timestamp") or "")


def daily_change(token, symbol):
    """전일 종가 대비 등락과 당일 시/고/저·거래량.

    /api/v1/prices 에는 등락률도 거래량도 없어서 일봉 2개로 직접 계산한다.
    """
    entries = candles(token, symbol, interval="1d", count=2)
    if not entries:
        return None

    latest = entries[-1]
    close = fmt.to_decimal(latest.get("closePrice"))
    info = {
        "open": latest.get("openPrice"),
        "high": latest.get("highPrice"),
        "low": latest.get("lowPrice"),
        "close": latest.get("closePrice"),
        "volume": latest.get("volume"),
        "currency": latest.get("currency"),
        "change": None,
        "changeRate": None,
        "prevClose": None,
    }

    if len(entries) < 2 or close is None:
        return info

    previous = fmt.to_decimal(entries[-2].get("closePrice"))
    if previous is None or previous == 0:
        return info

    info["prevClose"] = entries[-2].get("closePrice")
    info["change"] = close - previous
    info["changeRate"] = (close - previous) / previous * 100
    return info


def daily_changes(token, symbols):
    """여러 종목의 등락을 병렬로 모은다.

    캔들은 종목당 한 번씩 호출해야 해서 순차로 돌리면 목록이 눈에 띄게 느려진다.
    MARKET_DATA_CHART 는 20 req/s 이므로 동시 실행 수를 넉넉히 아래로 잡는다.
    한 종목이 실패해도 화면 전체를 버리지 않고 그 종목만 비워둔다.
    """
    symbols = [s for s in symbols if s]
    if not symbols:
        return {}

    collected = {}

    def fetch(symbol):
        try:
            return symbol, daily_change(token, symbol)
        except TossError:
            return symbol, None

    workers = min(CHANGE_WORKERS, len(symbols))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for symbol, info in pool.map(fetch, symbols):
            collected[symbol] = info
    return collected


def orderbook(token, symbol):
    """호가. {"asks": [...], "bids": [...]} 형태."""
    result = client.get("/api/v1/orderbook", token, params={"symbol": symbol})
    if not isinstance(result, dict):
        return {"asks": [], "bids": []}
    return {
        "asks": result.get("asks") or [],
        "bids": result.get("bids") or [],
        "currency": result.get("currency"),
    }


def price_limits(token, symbol):
    """상한가/하한가."""
    return client.get("/api/v1/price-limits", token, params={"symbol": symbol}) or {}


def symbol_names(token, symbols):
    """종목코드 -> 종목명. 캐싱된 마스터에서 찾으므로 추가 호출이 없다."""
    wanted = set(symbols)
    if not wanted:
        return {}
    found = {}
    for entry in stock_master(token):
        symbol = entry.get("symbol")
        if symbol in wanted:
            found[symbol] = entry.get("name") or symbol
    return found


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

    검색어와 종목명 모두 text.fold() 로 정규화한다. 한글이 NFD 로 들어오면
    정규화 없이는 어떤 비교도 걸리지 않는다.
    """
    needle = text.fold(query)
    if not needle:
        return []

    scored = []
    for entry in stock_master(token, markets):
        symbol = text.fold(entry.get("symbol"))
        name = text.fold(entry.get("name"))

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
