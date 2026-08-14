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

# 기본 계좌 seq 캐시. 계좌 구성은 거의 바뀌지 않는다.
ACCOUNT_SEQ_FILE = "account-seq.json"
ACCOUNT_SEQ_TTL = 24 * 60 * 60

# 전일 종가 캐시. 다음 장이 열릴 때까지 유효하다.
PREV_CLOSE_FILE = "prev-close.json"
# 저장된 값을 만드는 방식이 바뀌면 올린다. 예전 방식으로 계산해 둔 값이 만료 전까지
# 살아남아 잘못된 등락률을 계속 보여주는 것을 막는다.
PREV_CLOSE_VERSION = 3
KST_OFFSET = 9 * 3600
SESSION_OPEN_HOUR = 9


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

    # 계좌 구성은 거의 바뀌지 않는다. 화면이 자동 갱신될 때마다 계좌 목록을 다시
    # 부르면 조회 한 번에 호출이 두 번씩 나가므로 결과를 캐싱한다.
    cached = _read_cached_seq()
    if cached:
        return cached

    found = accounts(token)
    if not found:
        raise ApiError("계좌를 찾을 수 없습니다", "이 API 키에 연결된 계좌가 없습니다.")
    # 숫자로 오는 경우가 있어 문자열로 맞춰둔다. 헤더 값으로 그대로 쓰인다.
    seq = str(found[0].get("accountSeq"))
    _write_cached_seq(seq)
    return seq


def _account_seq_file():
    return os.path.join(config.cache_dir(), ACCOUNT_SEQ_FILE)


def _read_cached_seq():
    try:
        with open(_account_seq_file(), "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except (IOError, OSError, ValueError):
        return None
    if not isinstance(cached, dict) or cached.get("expires_at", 0) <= time.time():
        return None
    value = cached.get("value")
    return value if isinstance(value, str) and value else None


def _write_cached_seq(seq):
    try:
        with open(_account_seq_file(), "w", encoding="utf-8") as handle:
            json.dump({"value": seq, "expires_at": time.time() + ACCOUNT_SEQ_TTL}, handle)
    except (IOError, OSError):
        pass


def holdings(token, account_seq):
    """보유 종목 개요(HoldingsOverview)를 그대로 반환.

    보유 종목 목록의 키는 items 다. holdings 가 아니다. 합계 금액은 Price
    모델({"krw": ..., "usd": ...})로 통화별로 나뉘어 오고, 손익률(rate)은
    퍼센트가 아니라 소수비율(0.1077 = 10.77%)이다.
    """
    result = client.get("/api/v1/holdings", token, account_seq=account_seq)
    if not isinstance(result, dict):
        return {}
    result.setdefault("items", [])
    return result


def buying_power(token, account_seq, currency="KRW"):
    """현금 기반 매수 가능 금액. {"currency": ..., "cashBuyingPower": ...} 형태.

    currency 는 필수 쿼리 파라미터다. 빼면 400 이 떨어진다.
    """
    return client.get(
        "/api/v1/buying-power",
        token,
        params={"currency": currency},
        account_seq=account_seq,
    ) or {}


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


def today_kst():
    """오늘 날짜(KST) 를 'YYYY-MM-DD' 로."""
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + KST_OFFSET))


def _candle_date(entry):
    """캔들의 날짜 부분. timestamp 가 +09:00 로 오므로 앞 10자가 곧 KST 날짜다."""
    return (entry.get("timestamp") or "")[:10]


def previous_close(entries, today=None):
    """일봉 목록에서 '전일 종가' 를 고른다.

    뒤에서 두 번째를 그냥 쓰면 안 된다. 그건 응답에 진행 중인 당일 캔들이 들어
    있을 때만 맞고, 들어 있지 않으면 그저께 종가를 집어 등락률이 하루치 어긋난다.
    날짜를 보고 오늘이 아닌 마지막 캔들을 고르면 두 경우 모두에서 맞다.
    """
    today = today or today_kst()
    for entry in reversed(entries):
        if _candle_date(entry) < today:
            return entry.get("closePrice")
    return None


def change_against(last_price, prev_close):
    """(등락금액, 등락률 %) 를 돌려준다. 계산할 수 없으면 (None, None)."""
    last = fmt.to_decimal(last_price)
    previous = fmt.to_decimal(prev_close)
    if last is None or previous is None or previous == 0:
        return None, None
    diff = last - previous
    return diff, diff / previous * 100


def _prev_close_file():
    return os.path.join(config.cache_dir(), PREV_CLOSE_FILE)


def _next_session_open(now):
    """다음 장 시작(09:00 KST) 의 epoch.

    전일 종가는 장이 새로 열리기 전까지 바뀌지 않으므로 그 시각을 만료로 삼는다.
    자정 기준으로 만료시키면 장 시작 전에 받아둔 값(그 전날 종가)이 개장 후까지
    남아 등락률이 엉뚱한 기준으로 계산된다.
    """
    kst = now + KST_OFFSET
    open_at = (kst // 86400) * 86400 + SESSION_OPEN_HOUR * 3600
    if kst >= open_at:
        open_at += 86400
    return open_at - KST_OFFSET


def _load_prev_closes():
    try:
        with open(_prev_close_file(), "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except (IOError, OSError, ValueError):
        return {}
    if not isinstance(cached, dict) or cached.get("expires_at", 0) <= time.time():
        return {}
    if cached.get("version") != PREV_CLOSE_VERSION:
        return {}
    values = cached.get("values")
    return values if isinstance(values, dict) else {}


def _store_prev_closes(values):
    payload = {
        "version": PREV_CLOSE_VERSION,
        "expires_at": _next_session_open(time.time()),
        "values": values,
    }
    try:
        with open(_prev_close_file(), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except (IOError, OSError):
        pass


def prev_closes(token, symbols):
    """종목코드 -> 전일 종가.

    전일 종가는 다음 장이 열리기 전까지 그대로이므로 캐싱한다. 덕분에 목록·검색
    화면에서 등락률을 보여주면서도 캔들 호출은 그 종목을 처음 본 날 한 번뿐이다.
    이 캐시가 없으면 결과 한 건마다 한 번씩, 키 입력마다 반복해서 부르게 된다.
    """
    symbols = [s for s in symbols if s]
    if not symbols:
        return {}

    known = _load_prev_closes()
    missing = [s for s in symbols if s not in known]

    if missing:
        def fetch(symbol):
            # 기준가를 먼저 쓴다. 캔들 종가는 수정주가라 등락률 기준으로 맞지 않는다.
            try:
                base = base_price(token, symbol)
                if base is not None:
                    return symbol, base
            except TossError:
                pass
            try:
                entries = candles(token, symbol, interval="1d", count=3)
            except TossError:
                return symbol, None
            return symbol, previous_close(entries)

        workers = min(CHANGE_WORKERS, len(missing))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for symbol, close in pool.map(fetch, missing):
                if close is not None:
                    known[symbol] = close
        _store_prev_closes(known)

    return {symbol: known.get(symbol) for symbol in symbols}


def daily_change(token, symbol, last_price=None, prev_close=None):
    """전일 종가 대비 등락과 당일 시/고/저·거래량.

    /api/v1/prices 에는 등락률도 거래량도 없어서 일봉 2개로 직접 계산한다.

    등락의 기준가는 last_price 를 주면 그 값을, 없으면 당일 캔들의 종가를 쓴다.
    일봉의 closePrice 와 /api/v1/prices 의 lastPrice 는 갱신 시점이 달라 장중에
    서로 어긋난다. 화면에 현재가를 lastPrice 로 보여주면서 등락만 캔들로 계산하면
    '현재가 - 전일종가' 가 표시된 등락과 맞지 않는다. 그래서 보여주는 값과 같은
    기준으로 계산하도록 호출부가 현재가를 넘긴다.
    """
    # 3개를 받는다. 2개면 응답에 당일 캔들이 포함되는 경우에만 전일이 들어온다.
    entries = candles(token, symbol, interval="1d", count=3)
    if not entries:
        return None

    latest = entries[-1]
    info = {
        "open": latest.get("openPrice"),
        "high": latest.get("highPrice"),
        "low": latest.get("lowPrice"),
        "close": latest.get("closePrice"),
        "volume": latest.get("volume"),
        "currency": latest.get("currency"),
        # 시고저·거래량이 오늘 것인지. 응답에 당일 캔들이 없으면 마지막 캔들은
        # 어제 것이고, 그걸 '당일' 이라고 적으면 거짓말이 된다.
        "isToday": _candle_date(latest) == today_kst(),
        "change": None,
        "changeRate": None,
        "prevClose": None,
    }

    reference = last_price if fmt.to_decimal(last_price) is not None else latest.get("closePrice")
    # 기준가를 받았으면 그것을 쓴다. 캔들 종가는 수정주가라 등락률 기준과 다르다.
    previous = prev_close if prev_close is not None else previous_close(entries)
    change, rate = change_against(reference, previous)
    if change is None:
        return info

    info["prevClose"] = previous
    info["change"] = change
    info["changeRate"] = rate
    return info


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


def base_from_limits(limits):
    """상하한가에서 기준가를 역산한다. 구할 수 없으면 None.

    국내 가격제한폭은 기준가 ±30% 라 두 값의 평균이 곧 기준가다. 상한은 호가단위
    내림, 하한은 올림이라 오차가 서로 상쇄돼 반올림 오차는 호가단위의 절반을
    넘지 않는다(160만원대 종목에서 500원, 0.03%).

    기준가는 거래소가 등락률을 계산하는 기준이고 토스 앱이 보여주는 값도 이것이다.
    일봉의 종가는 adjusted 기본값 때문에 배당·분할이 보정된 수정주가라 기준가와
    어긋난다. 실제로 SK하이닉스에서 1.3% 차이가 났다.

    정리매매·신규상장처럼 제한폭이 없는 종목과 해외 종목은 null 이 와서 None 이
    된다. 그때는 호출부가 캔들로 떨어진다.
    """
    upper = fmt.to_decimal((limits or {}).get("upperLimitPrice"))
    lower = fmt.to_decimal((limits or {}).get("lowerLimitPrice"))
    if upper is None or lower is None:
        return None
    base = fmt.round_won((upper + lower) / 2)
    return str(base) if base is not None else None


def base_price(token, symbol):
    """기준가(= 전일 종가). 구할 수 없으면 None."""
    return base_from_limits(price_limits(token, symbol))


def symbol_info(token, symbols):
    """종목코드 -> {"name", "market"}. 캐싱된 마스터에서 찾으므로 추가 호출이 없다."""
    wanted = set(symbols)
    if not wanted:
        return {}
    found = {}
    for entry in stock_master(token):
        symbol = entry.get("symbol")
        if symbol in wanted:
            found[symbol] = {
                "name": entry.get("name") or symbol,
                "market": entry.get("market") or "",
            }
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
