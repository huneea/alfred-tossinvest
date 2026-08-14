"""결과를 내보낸 뒤에 도는 준비 작업.

Script Filter 는 키 입력마다, 그리고 자동 갱신 주기마다 실행된다. 목록을 그리는
경로에서 네트워크를 타면 그만큼 화면이 늦는다. 그래서 오래 걸리는 준비 작업(로고
다운로드, 종목 마스터 수집)은 여기에 쌓아 두고 결과를 stdout 으로 내보낸 **뒤**
분리된 프로세스에 넘긴다. 다음 갱신에 결과가 반영된다.

두 가지를 반드시 지켜야 한다.

- **선점 표식** — 자동 갱신이 2초라 표식이 없으면 아직 받는 중인 대상을 다음
  실행이 또 요청한다. 프로세스가 죽어 표식만 남는 경우가 있어 수명을 둔다.
- **세션 분리** — 사용자가 키를 더 누르면 Alfred 가 지금 Script Filter 를 죽인다.
  자식이 같은 세션에 있으면 함께 죽어서 준비 작업이 영영 끝나지 않는다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

_queued = []


def bundle_dir():
    """워크플로우 번들 최상위. 진입 스크립트들이 있는 자리다."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fresh(path, ttl):
    """파일이 존재하고 ttl 초 이내에 쓰였으면 True."""
    try:
        return (time.time() - os.path.getmtime(path)) < ttl
    except OSError:
        return False


def claim(path, ttl):
    """이 프로세스가 맡겠다는 표식을 남긴다. 이미 누가 잡았으면 False."""
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return True
    except FileExistsError:
        if fresh(path, ttl):
            return False
        # 하다 죽은 프로세스가 남긴 표식. 수명이 지났으니 다시 잡는다.
        try:
            os.utime(path, None)
        except OSError:
            return False
        return True
    except OSError:
        return False


def release(path):
    try:
        os.remove(path)
    except OSError:
        pass


def queue(script, arg, claim_path, ttl):
    """준비 작업을 쌓는다. 실제 실행은 run_pending() 이 한다."""
    _queued.append((script, arg, claim_path, ttl))


def run_pending():
    """쌓인 작업을 스크립트별로 묶어 분리된 프로세스로 띄운다.

    **결과를 stdout 으로 내보낸 뒤에 부른다.** 순서가 뒤집히면 준비 작업이 끝날
    때까지 목록이 뜨지 않는다.
    """
    if not _queued:
        return

    grouped = {}
    for script, arg, claim_path, ttl in _queued:
        # 같은 대상을 이미 다른 실행이 잡았으면 여기서 걸러진다.
        if claim(claim_path, ttl):
            grouped.setdefault(script, []).append((str(arg), claim_path))
    del _queued[:]

    for script, targets in grouped.items():
        if not _spawn(script, [arg for arg, _ in sorted(targets)]):
            # 못 띄웠으면 표식을 남겨둘 이유가 없다. 다음 실행이 다시 시도한다.
            for _, claim_path in targets:
                release(claim_path)


def _spawn(script, args):
    path = os.path.join(bundle_dir(), script)
    try:
        subprocess.Popen(
            [sys.executable or "/usr/bin/python3", path] + list(args),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            cwd=bundle_dir(),
        )
        return True
    except OSError:
        # 준비 작업은 전부 부가 기능이다. 못 띄워도 화면은 이미 나갔다.
        return False
