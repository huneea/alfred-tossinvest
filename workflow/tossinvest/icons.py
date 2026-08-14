"""아이콘 경로.

Alfred 는 항목의 icon.path 를 워크플로우 디렉터리 기준 상대 경로로 해석한다.
원본은 assets/icons/*.svg 이고 build/render_icons.js 가 PNG 로 굽는다.

아이콘은 그 행이 **무엇인지** 알려주는 것으로 고른다. 등락 방향처럼 제목에 이미
숫자로 적혀 있는 내용을 아이콘으로 반복하지 않는다.
"""

from __future__ import annotations

from . import logos

STOCK = "icons/stock.png"          # 종목
STAR = "icons/star.png"            # 관심종목
CANDLE = "icons/candle.png"        # 시가·고가·저가
VOLUME = "icons/volume.png"        # 거래량
ASK = "icons/ask.png"              # 매도 호가
BID = "icons/bid.png"              # 매수 호가
LIMIT = "icons/limit.png"          # 상한가·하한가
PORTFOLIO = "icons/portfolio.png"  # 보유 자산 합계
CARD = "icons/card.png"            # 계좌
SEARCH = "icons/search.png"        # 검색 안내
WARN = "icons/warn.png"            # 안내·오류


def for_stock(symbol, saved):
    """종목 행의 아이콘.

    업체 로고가 캐시에 있으면 그것을 쓴다. 로고를 쓰면 관심종목 여부를 별로
    알리던 신호가 사라지지만, 목록에서 종목을 골라내는 속도는 로고 쪽이 훨씬
    빠르다. 관심종목 여부는 부제의 `⌘↩ 관심종목 추가/제거` 문구에 남아 있다.

    로고가 아직 안 받아졌거나 없는 종목이면 기존 아이콘으로 떨어진다.
    """
    return logos.path(symbol) or (STAR if symbol in saved else STOCK)
