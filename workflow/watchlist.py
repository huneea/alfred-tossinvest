#!/usr/bin/python3
"""Script Filter: 관심종목 전용 조회와 관리.

tsp 와 달리 최근 조회로 넘어가지 않는다. 관심종목이 비어 있으면 비어 있다고
말하고 등록 방법을 알려준다.

  tsw           등록한 관심종목 전체
  tsw <검색어>  관심종목 안에서 이름·티커로 좁히기 (지울 종목을 찾을 때)
  ⌘↩            해당 종목을 관심종목에서 제거
"""

from __future__ import annotations

import sys

from tossinvest import alfred, api, auth, store, text, view


def main():
    query = (sys.argv[1] if len(sys.argv) > 1 else "").strip()

    saved = store.watchlist()
    if not saved:
        alfred.empty(
            "관심종목이 없습니다",
            "tsp 로 종목을 검색한 뒤 ⌘↩ 를 누르면 등록됩니다.",
        )
        return

    token = auth.access_token()

    if query:
        # 이름으로도 찾을 수 있게 한다. 마스터는 캐싱돼 있어 추가 호출이 없다.
        names = api.symbol_names(token, saved)
        needle = text.fold(query)
        saved = [
            symbol for symbol in saved
            if needle in text.fold(symbol) or needle in text.fold(names.get(symbol))
        ]
        if not saved:
            alfred.empty(
                "일치하는 관심종목이 없습니다",
                "'{0}' 와 일치하는 종목이 관심종목에 없습니다.".format(query),
            )
            return

    heading = "관심종목 {0}개".format(len(store.watchlist()))
    alfred.live(view.listing(token, saved, heading))


if __name__ == "__main__":
    alfred.run(main)
