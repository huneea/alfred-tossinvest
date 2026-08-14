#!/usr/bin/python3
"""설치본에서 사용자가 지정한 핫키를 새로 생성한 info.plist 로 옮긴다.

핫키 조합은 prefs.plist 가 아니라 info.plist 안 hotkey 오브젝트에 저장된다.
그래서 생성된 plist 를 그대로 덮어쓰면 사용자가 지정해둔 단축키가 사라진다.
동기화할 때마다 핫키를 다시 잡아야 하는 일을 막으려고 여기서 병합한다.

사용법: preserve_hotkey.py <설치본 info.plist> <새로 생성한 info.plist>
"""

from __future__ import annotations

import plistlib
import sys

# 사용자가 Alfred UI 에서 지정하는 값들. 나머지 config 는 생성 결과를 정본으로 본다.
USER_SET_KEYS = ("hotkey", "hotmod", "hotstring")


def _load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    installed_path, generated_path = sys.argv[1], sys.argv[2]

    try:
        installed = _load(installed_path)
    except (IOError, OSError):
        # 첫 설치라 아직 설치본이 없다. 보존할 것도 없으므로 그냥 통과한다.
        print("보존할 기존 설정 없음")
        return 0

    saved = {}
    for obj in installed.get("objects", []):
        if "trigger.hotkey" not in obj.get("type", ""):
            continue
        config = obj.get("config") or {}
        kept = {k: config[k] for k in USER_SET_KEYS if k in config}
        if kept:
            saved[obj.get("uid")] = kept

    if not saved:
        print("보존할 핫키 없음")
        return 0

    generated = _load(generated_path)
    applied = 0
    for obj in generated.get("objects", []):
        kept = saved.get(obj.get("uid"))
        if kept:
            obj.setdefault("config", {}).update(kept)
            applied += 1

    with open(generated_path, "wb") as handle:
        plistlib.dump(generated, handle)

    print("핫키 {0}개 보존".format(applied))
    return 0


if __name__ == "__main__":
    sys.exit(main())
