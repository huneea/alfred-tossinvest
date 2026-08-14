#!/usr/bin/python3
"""종목 로고를 내려받아 캐시에 넣는다.

`tossinvest.jobs.run_pending()` 이 분리된 프로세스로 띄운다. Script Filter 본체와
따로 도는 이유는 하나다 — 목록을 그리는 경로에서 네트워크를 타지 않기 위해서다.
이 스크립트가 얼마나 걸리든 사용자가 보는 화면은 이미 나가 있다.

출력은 없다. 실패해도 조용히 끝낸다. 로고는 부가 기능이라 실패가 화면을 망치면
안 된다. 다음 실행이 다시 시도할 수 있도록 표식만 정리한다.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tossinvest import jobs, logos  # noqa: E402

TIMEOUT = 15

# 한 화면에 뜨는 종목 수만큼 동시에 붙지 않게 한다. 어차피 한 종목당 한 번뿐인
# 다운로드라 서두를 이유가 없다.
WORKERS = 4

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _download(symbol):
    logo, miss, _ = logos.paths(symbol)
    request = urllib.request.Request(
        logos.URL_TEMPLATE.format(symbol),
        headers={"User-Agent": "alfred-tossinvest"},
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        # 403/404 는 그 종목에 로고가 없다는 뜻이다(S3 는 없는 객체에 403 을
        # 준다). 다시 묻지 않도록 기억해 둔다. 5xx 나 429 는 일시적일 수 있으니
        # 표식을 남기지 않고 다음 기회에 다시 시도한다.
        if exc.code in (403, 404):
            _touch(miss)
        return
    except Exception:
        return

    # 로그인 페이지나 에러 문서를 아이콘으로 저장하면 Alfred 가 깨진 이미지를
    # 그린다. 실제 PNG 인지 확인하고 넣는다.
    if not body.startswith(PNG_MAGIC):
        _touch(miss)
        return

    # 받다 만 파일을 Alfred 가 읽는 일이 없도록 임시 이름에 쓰고 바꿔 끼운다.
    temp = "{0}.part{1}".format(logo, os.getpid())
    try:
        with open(temp, "wb") as handle:
            handle.write(body)
        os.replace(temp, logo)
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass


def _touch(path):
    try:
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
        os.utime(path, None)
    except OSError:
        pass


def _fetch(symbol):
    try:
        _download(symbol)
    finally:
        # 선점 표식은 성공이든 실패든 반드시 지운다. 남으면 CLAIM_TTL 동안
        # 그 종목을 아무도 다시 받지 못한다.
        jobs.release(logos.paths(symbol)[2])


def main():
    symbols = [s for s in sys.argv[1:] if logos.SAFE_SYMBOL.match(s)]
    if not symbols:
        return
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(symbols))) as pool:
        list(pool.map(_fetch, symbols))


if __name__ == "__main__":
    main()
