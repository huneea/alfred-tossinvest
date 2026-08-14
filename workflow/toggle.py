#!/usr/bin/python3
"""Run Script: 관심종목 토글 (⌘↩ 로 실행된다).

출력은 뒤에 연결된 알림 오브젝트의 {query} 가 되므로, 사용자에게 보여줄 문구를
그대로 찍는다.
"""

from __future__ import annotations

import sys

from tossinvest import store


def main():
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not symbol:
        print("종목을 알 수 없습니다")
        return

    _, message = store.toggle_watchlist(symbol)
    print("{0} — {1}".format(symbol, message))


if __name__ == "__main__":
    main()
