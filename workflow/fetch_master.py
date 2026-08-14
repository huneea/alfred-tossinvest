#!/usr/bin/python3
"""종목 마스터를 미리 받아 캐시에 넣는다.

`tossinvest.jobs.run_pending()` 이 분리된 프로세스로 띄운다. 미국 시장을 붙이면서
필요해졌다 — `/api/v1/stocks/all` 이 **초당 1회** 제한이라 시장 수만큼 초가 걸리고,
그동안 Alfred 결과창을 멈춰 세울 수는 없다.

출력은 없다. 실패해도 조용히 끝낸다. 다음 실행이 다시 시도한다.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tossinvest import api, auth, jobs  # noqa: E402


def main():
    markets = [m for m in sys.argv[1:] if m in api.DEFAULT_MARKETS]
    if not markets:
        return

    try:
        token = auth.access_token()
    except Exception:
        # 자격증명이 없거나 발급에 실패한 상황이다. 화면 쪽에서 이미 오류를
        # 보여주고 있으므로 여기서 더 할 일이 없다.
        for market in markets:
            jobs.release(api._master_claim_file(market))
        return

    # 한 시장씩 순서대로 받는다. api.fetch_master 가 호출 간격을 지킨다.
    for market in markets:
        try:
            api.fetch_master(token, market)
        except Exception:
            pass
        finally:
            jobs.release(api._master_claim_file(market))


if __name__ == "__main__":
    main()
