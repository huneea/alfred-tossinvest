"""관심종목과 최근 조회 종목의 영속 저장.

둘 다 종목코드 문자열의 순서 있는 목록이다. 캐시가 아니라 사용자 데이터이므로
config.data_dir() 에 둔다.
"""

from __future__ import annotations

import json
import os

from . import config

WATCHLIST_FILE = "watchlist.json"
RECENT_FILE = "recent.json"

# 관심종목 화면은 종목당 캔들을 한 번씩 호출해 등락률을 만든다. 종목 수가 늘수록
# 화면이 느려지고 rate limit 에 가까워지므로 상한을 둔다.
WATCHLIST_MAX = 40
RECENT_MAX = 15


def _path(name):
    return os.path.join(config.data_dir(), name)


def _read(name):
    try:
        with open(_path(name), "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (IOError, OSError, ValueError):
        return []
    if not isinstance(loaded, list):
        return []
    # 저장된 값이 손상돼도 화면 전체가 죽지 않도록 문자열만 걸러낸다.
    return [item for item in loaded if isinstance(item, str) and item]


def _write(name, symbols):
    try:
        with open(_path(name), "w", encoding="utf-8") as handle:
            json.dump(symbols, handle, ensure_ascii=False)
    except (IOError, OSError):
        return False
    return True


def watchlist():
    return _read(WATCHLIST_FILE)


def in_watchlist(symbol):
    return symbol in _read(WATCHLIST_FILE)


def toggle_watchlist(symbol):
    """관심종목에 넣거나 뺀다.

    (추가되었는가, 안내 문구) 를 돌려준다. 상한을 넘으면 추가하지 않는다.
    """
    symbols = _read(WATCHLIST_FILE)

    if symbol in symbols:
        symbols.remove(symbol)
        _write(WATCHLIST_FILE, symbols)
        return False, "관심종목에서 제거했습니다"

    if len(symbols) >= WATCHLIST_MAX:
        return False, "관심종목이 가득 찼습니다 (최대 {0}개)".format(WATCHLIST_MAX)

    symbols.append(symbol)
    _write(WATCHLIST_FILE, symbols)
    return True, "관심종목에 추가했습니다"


def move_to_top(symbol):
    """관심종목 맨 앞으로. 목록에 없으면 아무 것도 하지 않는다."""
    return _move(symbol, to_top=True)


def move_to_bottom(symbol):
    """관심종목 맨 뒤로."""
    return _move(symbol, to_top=False)


def _move(symbol, to_top):
    symbols = _read(WATCHLIST_FILE)
    if symbol not in symbols:
        return False
    symbols.remove(symbol)
    if to_top:
        symbols.insert(0, symbol)
    else:
        symbols.append(symbol)
    _write(WATCHLIST_FILE, symbols)
    return True


def recent():
    return _read(RECENT_FILE)


def record_recent(symbol):
    """최근 조회 목록 맨 앞으로 올린다. 이미 있으면 중복 없이 순서만 바꾼다."""
    symbols = _read(RECENT_FILE)
    if symbol in symbols:
        symbols.remove(symbol)
    symbols.insert(0, symbol)
    _write(RECENT_FILE, symbols[:RECENT_MAX])
