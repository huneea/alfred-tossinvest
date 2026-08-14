"""Alfred Script Filter 출력 헬퍼.

Script Filter 는 stdout 으로 받은 JSON 을 결과 목록으로 렌더링한다. 스크립트가
예외로 죽으면 사용자에게는 빈 목록만 보이므로, 오류도 항목 하나로 바꿔서
화면에 띄운다.
"""

from __future__ import annotations

import json
import sys

from . import config, icons, jobs
from .errors import TossError


def item(title, subtitle="", arg=None, uid=None, valid=True, copy=None, icon=None,
         mods=None, autocomplete=None):
    """Script Filter 항목 하나를 만든다.

    mods 는 {"cmd": {"arg": ..., "subtitle": ...}} 형태로, 수식키를 누른 채
    실행했을 때 다른 오브젝트로 다른 값을 넘기는 데 쓴다.

    autocomplete 는 탭을 눌렀을 때 쿼리를 대신할 값이다. 종목 항목에는 종목명을
    넣는다. 일부만 입력하고 탭으로 완성할 수 있고, tsq 에서는 이름이 완성되는
    순간 정확히 일치하게 되어 바로 상세 화면으로 넘어간다.
    """
    # Alfred 는 이 필드들이 문자열이 아니면 항목을 렌더링하지 못한다. API 가
    # 숫자로 주는 값(accountSeq 등)이 그대로 흘러들어와 화면이 깨진 적이 있어
    # 출력 직전에 한 번 더 강제한다.
    entry = {"title": str(title), "subtitle": str(subtitle), "valid": valid}
    if arg is not None:
        entry["arg"] = str(arg)
    if uid is not None:
        entry["uid"] = str(uid)
    if copy is not None:
        entry["text"] = {"copy": str(copy)}
    if icon is not None:
        entry["icon"] = {"path": icon}
    if mods:
        entry["mods"] = mods
    if autocomplete is not None:
        entry["autocomplete"] = str(autocomplete)
    return entry


def stock_mods(symbol, is_saved):
    """종목 항목의 수식키 정의.

    ⌘ 관심종목 토글, ⌥ 맨 위로, ⌃ 맨 아래로.

    순서 변경은 관심종목에만 의미가 있으므로 등록되지 않은 종목에서는 valid 를
    꺼서 실행되지 않게 한다. 그냥 빼버리면 Alfred 가 항목의 기본 arg 를 대신
    넘겨 엉뚱한 값이 순서 변경 스크립트로 들어간다.
    """
    def reorder(where, label):
        return {
            "arg": "{0}:{1}".format(where, symbol),
            "subtitle": label if is_saved else "관심종목만 순서를 바꿀 수 있습니다",
            "valid": is_saved,
        }

    return {
        "cmd": {
            "arg": symbol,
            "subtitle": "관심종목에서 제거" if is_saved else "관심종목에 추가",
            "valid": True,
        },
        "alt": reorder("top", "맨 위로"),
        "ctrl": reorder("bottom", "맨 아래로"),
    }


def output(items, rerun=None):
    """항목 목록을 Alfred 가 읽을 JSON 으로 stdout 에 쓴다."""
    payload = {"items": list(items)}
    if rerun is not None:
        payload["rerun"] = rerun
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()

    # 로고·종목 마스터처럼 오래 걸리는 준비 작업은 결과를 다 내보낸 **뒤에**
    # 돌린다. 순서가 뒤집히면 그것이 끝날 때까지 목록이 뜨지 않는다. 준비된
    # 결과는 다음 자동 갱신에 반영된다.
    jobs.run_pending()


def live(items):
    """수치가 계속 변하는 화면의 출력.

    Alfred 는 rerun 값(초)만큼 기다렸다가 같은 Script Filter 를 다시 실행한다.
    결과창이 열려 있는 동안만 돈다. 갱신마다 API 를 다시 부르므로 사용자가 끌 수
    있어야 하고, 꺼져 있으면 rerun 을 아예 넣지 않는다.

    안내·오류 화면에는 쓰지 않는다. 다시 불러도 결과가 달라지지 않는다.
    """
    output(items, rerun=config.refresh_seconds())


def empty(title, subtitle="", icon=icons.WARN):
    """결과가 없을 때 보여줄 선택 불가 항목."""
    output([item(title, subtitle, valid=False, icon=icon)])


def run(handler):
    """진입점 래퍼. TossError 는 결과 항목으로, 그 외 예외는 stderr 로 넘긴다.

    예상 못 한 예외까지 삼키면 Alfred 디버거에서 원인을 볼 수 없으므로 그대로
    올려보낸다.
    """
    try:
        handler()
    except TossError as exc:
        output([item(exc.title, exc.subtitle, valid=False, icon=icons.WARN)])
