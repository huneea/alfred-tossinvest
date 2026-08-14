"""도메인 단위 조회 함수.

진입 스크립트가 엔드포인트 경로나 응답 껍데기를 직접 다루지 않도록 감싼다.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from . import client, config, fmt, jobs, text
from .errors import ApiError, TossError

# 종목 마스터는 하루 한 번만 받으면 충분하다. Script Filter 는 타이핑마다
# 실행되므로 매번 전종목을 내려받으면 rate limit 과 지연 둘 다 문제가 된다.
MASTER_TTL = 24 * 60 * 60

# `market` 허용값 중 이 워크플로우가 쓰는 것. AMEX·US_ETC 는 대부분 ETF·워런트라
# 검색을 어수선하게 만들어 뺐다.
KR_MARKETS = ("KOSPI", "KOSDAQ")
US_MARKETS = ("NASDAQ", "NYSE")
DEFAULT_MARKETS = KR_MARKETS + US_MARKETS

# `/api/v1/stocks/all` 의 rate limit 은 **초당 1회**다(응답의 X-RateLimit-Limit 이
# 1). 문서의 rate limit 표에는 이 그룹이 아예 없어서 실측으로 확인했다. 시장을
# 연달아 받으면 두 번째부터 429 가 나고, 그러면 그날 검색이 통째로 빈다.
MASTER_MIN_INTERVAL = 1.2
MASTER_RETRY_WAIT = 2.0

# 마스터 한 시장을 받는 데 걸리는 시간(0.5초 안팎)에 간격까지 더한 여유값.
MASTER_CLAIM_TTL = 180

MASTER_FETCHER = "fetch_master.py"

_last_master_call = 0.0

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
PREV_CLOSE_VERSION = 4
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


def candles(token, symbol, interval="1d", count=2, adjusted=True):
    """시간순으로 정렬된 캔들 목록.

    API 가 어떤 순서로 주는지 문서에 명시돼 있지 않으므로 timestamp 로 직접
    정렬한다. 순서를 가정하면 전일 종가와 당일 종가가 뒤바뀔 수 있다.
    """
    result = client.get(
        "/api/v1/candles",
        token,
        params={
            "symbol": symbol,
            "interval": interval,
            "count": count,
            # 기본값이 true 다. 배당·분할 보정이 들어간 수정주가를 준다.
            "adjusted": "true" if adjusted else "false",
        },
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
    """종목코드 -> {"base": 기준가, "candle": 일봉 전일 종가}.

    둘 다 다음 장이 열리기 전까지 바뀌지 않으므로 함께 캐싱한다. 덕분에 목록·검색
    화면에서 등락률을 두 기준으로 보여주면서도, 종목당 호출은 그 종목을 처음 본
    날 두 번(상하한가·일봉)뿐이다. 이후 조회와 자동 갱신에서는 추가 호출이 없다.

    base 는 등락률 계산의 기준이고 candle 은 정규장 기준 등락률 표시에 쓴다.
    base 를 못 구하면(제한폭 없는 종목·해외) candle 이 그 자리를 대신한다.
    """
    symbols = [s for s in symbols if s]
    if not symbols:
        return {}

    known = _load_prev_closes()
    missing = [s for s in symbols if s not in known]

    if missing:
        def fetch(symbol):
            base = None
            try:
                base = base_price(token, symbol)
            except TossError:
                pass

            from_candle = None
            try:
                from_candle = previous_close(
                    candles(token, symbol, interval="1d", count=3))
            except TossError:
                pass

            if base is None and from_candle is None:
                return symbol, None
            return symbol, {"base": base or from_candle, "candle": from_candle}

        workers = min(CHANGE_WORKERS, len(missing))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for symbol, value in pool.map(fetch, missing):
                if value is not None:
                    known[symbol] = value
        _store_prev_closes(known)

    return {symbol: known.get(symbol) or {} for symbol in symbols}


# 투자자별 매매동향. 일별 값이지만 장중 잠정치가 갱신되고 개인 확정치는 당일
# 저녁에야 채워지므로 짧게 캐싱한다.
INVESTOR_FILE = "investor.json"
INVESTOR_TTL = 600


def _investor_file():
    return os.path.join(config.cache_dir(), INVESTOR_FILE)


def _read_investor_cache():
    try:
        with open(_investor_file(), "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except (IOError, OSError, ValueError):
        return {}
    return cached if isinstance(cached, dict) else {}


def investor_trading(token, symbol):
    """투자자별 매매동향 기록 목록(최신순). 없으면 빈 목록.

    2일치를 받는다. 당일 개인 잠정치는 제공되지 않아 null 이므로, 그럴 때 전일
    확정치를 대신 보여주려면 하루치가 더 필요하다.

    국내 종목(KRX 6자리)만 지원하는 엔드포인트다. 그 외 심볼은 부르지 않는다.
    """
    if not (symbol or "").isdigit() or len(symbol) != 6:
        return []

    cache = _read_investor_cache()
    entry = cache.get(symbol)
    if (isinstance(entry, dict) and "records" in entry
            and time.time() - entry.get("at", 0) < INVESTOR_TTL):
        return entry.get("records") or []

    result = client.get(
        "/api/v1/stocks/{0}/investor-trading".format(symbol),
        token,
        params={"count": 2},
    )
    records = (result or {}).get("records") or []

    cache[symbol] = {"at": time.time(), "records": records}
    try:
        with open(_investor_file(), "w", encoding="utf-8") as handle:
            json.dump(cache, handle, ensure_ascii=False, default=str)
    except (IOError, OSError):
        pass
    return records


# 랭킹. basePrice·changeRate 를 직접 주는 유일한 엔드포인트다.
# TOP_GAINERS/TOP_LOSERS 는 basePrice 가 duration 시작 시점 기준가이고, 나머지는
# 항상 전일 기준가다.
RANKING_TYPES = {
    "MARKET_TRADING_AMOUNT": "거래대금 상위",
    "MARKET_TRADING_VOLUME": "거래량 상위",
    "TOP_GAINERS": "급등",
    "TOP_LOSERS": "급락",
    "TOSS_SECURITIES_TRADING_AMOUNT": "토스 거래대금 상위",
    "TOSS_SECURITIES_TRADING_VOLUME": "토스 거래량 상위",
}
RANKING_COUNT = 30


def rankings(token, ranking_type, market_country="KR", duration="realtime",
             count=RANKING_COUNT):
    """(집계 시각, 랭킹 목록) 을 돌려준다.

    응답은 {"rankings": [...], "rankedAt": ...} 이고 항목마다 price 에
    lastPrice·basePrice·changeRate 가 들어 있다. 등락률을 우리가 계산할 필요가
    없는 유일한 화면이다.
    """
    result = client.get(
        "/api/v1/rankings",
        token,
        params={
            "type": ranking_type,
            "marketCountry": market_country,
            "duration": duration,
            "count": count,
        },
    )
    if not isinstance(result, dict):
        return None, []
    return result.get("rankedAt"), result.get("rankings") or []


# 시장 지표 심볼. 문서의 심볼 카탈로그 중 이 워크플로우가 쓰는 것만 둔다.
INDEX_SYMBOLS = ("KOSPI", "KOSDAQ")


def index_prices(token, symbols=INDEX_SYMBOLS):
    """지수 현재가. {symbol: {"lastPrice", "timestamp"}} 형태.

    종목 시세와 마찬가지로 현재가만 준다. 등락률은 일봉으로 직접 계산한다.
    """
    result = client.get(
        "/api/v1/market-indicators/prices",
        token,
        params={"symbols": ",".join(symbols)},
    )
    return {e.get("symbol"): e for e in (result or []) if e.get("symbol")}


def index_candles(token, symbol, count=3):
    """지수 일봉. 종목 캔들과 같은 구조({candles: [...]})다."""
    result = client.get(
        "/api/v1/market-indicators/{0}/candles".format(symbol),
        token,
        params={"interval": "1d", "count": count},
    )
    entries = (result or {}).get("candles") or []
    return sorted(entries, key=lambda c: c.get("timestamp") or "")


def index_prev_closes(token, symbols=INDEX_SYMBOLS):
    """지수의 전일 종가. 종목과 같은 캐시를 쓴다(다음 장 시작까지 유효).

    지수에는 가격제한폭이 없어 기준가를 역산할 수 없다. 일봉 종가가 유일한
    수단이고, 지수는 정규장에서 산출되므로 넥스트장 때문에 어긋날 일도 없다.
    """
    known = _load_prev_closes()
    missing = [s for s in symbols if s not in known]

    if missing:
        def fetch(symbol):
            try:
                return symbol, previous_close(index_candles(token, symbol))
            except TossError:
                return symbol, None

        workers = min(CHANGE_WORKERS, len(missing))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for symbol, close in pool.map(fetch, missing):
                if close is not None:
                    known[symbol] = {"base": close, "candle": close}
        _store_prev_closes(known)

    return {s: (known.get(s) or {}).get("base") for s in symbols}


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
    # 일봉이 말하는 전일 종가. 기준가와 다를 수 있어(거래소 차이로 추정) 등락률을
    # 두 기준으로 보여줄 때 쓴다.
    info["candlePrevClose"] = previous_close(entries)

    # 등락 계산에는 기준가를 쓴다. 앱·거래소가 그 기준이다.
    previous = prev_close if prev_close is not None else info["candlePrevClose"]
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


FX_FILE = "exchange-rate.json"

# 표시 환율은 1분마다 갱신된다(문서 명시, 응답의 validFrom~validUntil 도 약 1분).
# 자동 갱신이 2초라 캐싱하지 않으면 화면 하나에 분당 30회가 나간다.
FX_TTL = 60


def usd_krw(token):
    """1 USD 가 몇 원인지. 구하지 못하면 None.

    `rate` 는 매수 환율이라 스프레드가 섞여 있다. 화면에 참고로 덧붙이는 값이므로
    중립적인 `midRate`(매매기준율)를 쓴다. 문서도 이 엔드포인트를 "참고용 표시
    환율" 이라고 못박는다 — 실제 주문 체결 환율과는 다르다.

    환율을 못 받았다고 시세 목록 전체를 오류로 덮지는 않는다. 원화 환산은 곁들이는
    정보라 없으면 달러 표기만 남으면 된다.
    """
    path = os.path.join(config.cache_dir(), FX_FILE)
    try:
        if time.time() - os.path.getmtime(path) < FX_TTL:
            with open(path, "r", encoding="utf-8") as handle:
                return fmt.to_decimal(json.load(handle).get("rate"))
    except (IOError, OSError, ValueError):
        pass

    try:
        result = client.get(
            "/api/v1/exchange-rate",
            token,
            params={"baseCurrency": "USD", "quoteCurrency": "KRW"},
        ) or {}
    except TossError:
        return None

    rate = fmt.to_decimal(result.get("midRate") or result.get("rate"))
    if rate is None:
        return None

    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"rate": str(rate)}, handle)
    except (IOError, OSError):
        pass
    return rate


def price_limits(token, symbol):
    """상한가/하한가."""
    return client.get("/api/v1/price-limits", token, params={"symbol": symbol}) or {}


def base_from_limits(limits):
    """상하한가에서 기준가를 역산한다. 구할 수 없으면 None.

    국내 가격제한폭은 기준가 ±30% 라 두 값의 평균이 곧 기준가다. 상한은 호가단위
    내림, 하한은 올림이라 오차가 서로 상쇄돼 반올림 오차는 호가단위의 절반을
    넘지 않는다(160만원대 종목에서 500원, 0.03%).

    기준가는 거래소가 등락률을 계산하는 기준이고 토스 앱이 보여주는 값도 이것이다.
    일봉의 종가는 이 값과 어긋나는 경우가 있다 — SK하이닉스에서 캔들 1,572,000 vs
    기준가 1,593,000 으로 1.3% 차이가 났다. adjusted=false 로 보정을 꺼도 같은 값이
    나왔으므로 수정주가 문제는 아니고, 원인은 밝히지 못했다. 역산한 기준가가 맞다는
    것은 랭킹의 basePrice 와 일치하는 것으로 확인했다.

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


def _master_claim_file(market):
    return os.path.join(config.cache_dir(), "master-{0}.claim".format(market))


def search_markets():
    """검색 대상 시장. 미국 종목은 설정으로 끌 수 있다."""
    return KR_MARKETS + (US_MARKETS if config.us_stocks_enabled() else ())


def fetch_master(token, market):
    """한 시장의 전종목을 받아 캐시에 넣는다. 초당 1회 제한을 지킨다.

    이 함수를 부르는 쪽이 여러 시장을 도는 경우가 있어 간격을 여기서 지킨다.
    호출부가 기억해야 하는 규칙을 만들면 언젠가는 빠뜨린다.
    """
    global _last_master_call

    def call():
        global _last_master_call
        wait = MASTER_MIN_INTERVAL - (time.time() - _last_master_call)
        if wait > 0:
            time.sleep(wait)
        try:
            return client.get(
                "/api/v1/stocks/all",
                token,
                params={"market": market, "status": "ACTIVE"},
            ) or []
        finally:
            _last_master_call = time.time()

    try:
        rows = call()
    except ApiError as exc:
        if exc.status != 429:
            raise
        # 간격을 지켰는데도 걸렸다면 다른 프로세스가 같은 한도를 쓰고 있다.
        time.sleep(MASTER_RETRY_WAIT)
        rows = call()

    _store_master_cache(market, rows)
    return rows


def stock_master(token, markets=None):
    """상장 종목 마스터를 합쳐서 반환. 시장별로 하루 단위 캐싱한다.

    국내 시장은 없으면 그 자리에서 받는다. 검색의 알맹이라 비어 있으면 화면이
    쓸모없어진다.

    미국 시장은 백그라운드에 맡기고 이번 실행은 그냥 넘어간다. 초당 1회 제한
    때문에 네 시장을 다 받으려면 몇 초가 걸리는데, 그동안 Alfred 결과창이 멈춰
    있게 할 수는 없다. 준비되기 전까지는 국내 종목만 검색되고, 받아지면 다음
    갱신부터 자연스럽게 합쳐진다.
    """
    wanted = search_markets() if markets is None else markets

    entries = []
    for market in wanted:
        cached = _load_master_cache(market)
        if cached is None:
            if market in US_MARKETS:
                jobs.queue(MASTER_FETCHER, market,
                           _master_claim_file(market), MASTER_CLAIM_TTL)
                continue
            cached = fetch_master(token, market)
        for entry in cached:
            entry.setdefault("market", market)
        entries.extend(cached)
    return entries


def search_stocks(token, query, limit=15, markets=None):
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
