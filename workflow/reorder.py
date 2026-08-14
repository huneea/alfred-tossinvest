#!/usr/bin/python3
"""Run Script: 관심종목 순서 변경 (⌥↩ 맨 위로 / ⌃↩ 맨 아래로).

인자는 "top:005930" 또는 "bottom:005930" 형태다. 출력은 뒤에 연결된 알림
오브젝트의 {query} 가 되므로 사용자에게 보여줄 문구를 그대로 찍는다.
"""

from __future__ import annotations

import sys

from tossinvest import store

MOVES = {"top": (store.move_to_top, "맨 위로"), "bottom": (store.move_to_bottom, "맨 아래로")}


def main():
    raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    where, _, symbol = raw.partition(":")

    move = MOVES.get(where)
    if move is None or not symbol:
        # 관심종목이 아닌 항목에서 눌렸거나 형식이 어긋났다. 조용히 넘기지 않는다.
        print("순서를 바꿀 수 없습니다")
        return

    handler, label = move
    if handler(symbol):
        print("{0} — {1} 옮겼습니다".format(symbol, label))
    else:
        print("{0} — 관심종목에 없습니다".format(symbol))


if __name__ == "__main__":
    main()
