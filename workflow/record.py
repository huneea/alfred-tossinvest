#!/usr/bin/python3
"""Run Script: 최근 조회 기록 후 입력을 그대로 흘려보낸다.

Script Filter 와 Open URL 사이에 끼워 쓴다. 출력이 다음 오브젝트의 {query} 가
되므로 받은 URL 을 반드시 그대로 다시 찍어야 한다. 여기서 문자열을 바꾸면 링크가
열리지 않는다.

종목코드는 URL 마지막 경로에서 뽑는다. 별도 변수를 얹는 것보다 배선이 단순하고,
스크립트가 넘기는 URL 형식 하나만 지키면 된다.
"""

from __future__ import annotations

import sys

from tossinvest import store


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else ""

    symbol = url.rstrip("/").rsplit("/", 1)[-1]
    if symbol and symbol != url:
        try:
            store.record_recent(symbol)
        except Exception:
            # 기록 실패가 링크 열기를 막아서는 안 된다.
            pass

    sys.stdout.write(url)


if __name__ == "__main__":
    main()
