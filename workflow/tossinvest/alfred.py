"""Alfred Script Filter 출력 헬퍼.

Script Filter 는 stdout 으로 받은 JSON 을 결과 목록으로 렌더링한다. 스크립트가
예외로 죽으면 사용자에게는 빈 목록만 보이므로, 오류도 항목 하나로 바꿔서
화면에 띄운다.
"""

from __future__ import annotations

import json
import sys

from .errors import TossError


def item(title, subtitle="", arg=None, uid=None, valid=True, copy=None, icon=None,
         mods=None):
    """Script Filter 항목 하나를 만든다.

    mods 는 {"cmd": {"arg": ..., "subtitle": ...}} 형태로, 수식키를 누른 채
    실행했을 때 다른 오브젝트로 다른 값을 넘기는 데 쓴다.
    """
    entry = {"title": title, "subtitle": subtitle, "valid": valid}
    if arg is not None:
        entry["arg"] = arg
    if uid is not None:
        entry["uid"] = uid
    if copy is not None:
        entry["text"] = {"copy": copy}
    if icon is not None:
        entry["icon"] = {"path": icon}
    if mods:
        entry["mods"] = mods
    return entry


def toggle_mod(symbol, is_saved):
    """관심종목 토글용 ⌘ 수식키 정의."""
    return {
        "cmd": {
            "arg": symbol,
            "subtitle": "관심종목에서 제거" if is_saved else "관심종목에 추가",
            "valid": True,
        }
    }


def output(items, rerun=None):
    """항목 목록을 Alfred 가 읽을 JSON 으로 stdout 에 쓴다."""
    payload = {"items": list(items)}
    if rerun is not None:
        payload["rerun"] = rerun
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def empty(title, subtitle=""):
    """결과가 없을 때 보여줄 선택 불가 항목."""
    output([item(title, subtitle, valid=False)])


def run(handler):
    """진입점 래퍼. TossError 는 결과 항목으로, 그 외 예외는 stderr 로 넘긴다.

    예상 못 한 예외까지 삼키면 Alfred 디버거에서 원인을 볼 수 없으므로 그대로
    올려보낸다.
    """
    try:
        handler()
    except TossError as exc:
        output([item(exc.title, exc.subtitle, valid=False)])
