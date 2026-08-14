#!/usr/bin/python3
"""workflow/info.plist 를 생성한다.

plist 를 손으로 쓰면 UID 오타나 구조 실수를 잡기 어렵다. 여기서 파이썬 자료구조로
기술하고 plistlib 로 직렬화해 항상 유효한 plist 가 나오게 한다.

각 오브젝트의 config 키는 이 맥에 이미 설치된 워크플로우들의 info.plist 에서
확인한 실제 스키마를 따른다. 특히:
  - scriptfilter config["type"] = 0 은 /bin/bash
  - scriptfilter config["scriptargtype"] = 1 은 argv($1), 0 은 {query} 치환
큐 지연 관련 값(queuedelay*)은 정상 동작이 확인된 기존 워크플로우 설정을 그대로
가져왔다. 추측으로 바꾸지 않는다.
"""

from __future__ import annotations

import os
import plistlib

BUNDLE_ID = "me.hhjung.tossinvest"

# UID 는 고정한다. 빌드할 때마다 새로 만들면 Alfred 가 기존 연결과 사용자가 지정한
# 핫키를 잃어버린다.
UID_PRICE = "A1B2C3D4-0001-4000-8000-000000000001"
UID_HOLDINGS = "A1B2C3D4-0002-4000-8000-000000000002"
UID_ACCOUNTS = "A1B2C3D4-0003-4000-8000-000000000003"
UID_OPEN_URL = "A1B2C3D4-0004-4000-8000-000000000004"
UID_CLIPBOARD = "A1B2C3D4-0005-4000-8000-000000000005"

README = """토스증권 Open API 로 시세와 계좌를 조회합니다. 조회 전용이며 주문 기능은 없습니다.

■ 사용법
  주가 <종목명|티커>   종목 검색 후 현재가. 엔터로 토스증권 종목 페이지 열기
  잔고 [티커]          보유 종목과 평가손익
  계좌                 계좌 목록과 매수가능금액. 엔터로 accountSeq 복사

■ 설정 (필수)
  1. 토스증권 WTS > 설정 > Open API 에서 앱을 등록해 client id/secret 을 발급받습니다.
  2. 같은 화면에서 이 맥의 공인 IP 를 허용 목록에 등록합니다.
     등록하지 않은 IP 에서의 요청은 403 으로 거부됩니다.
     현재 IP 확인: curl -s https://api.ipify.org
     네트워크를 옮기면 IP 를 다시 등록해야 합니다.
  3. 위 Workflow Configuration 에 client id/secret 을 입력합니다.

■ 참고
  - 계좌가 여러 개면 Account Seq 를 지정하세요. 비우면 첫 번째 계좌를 씁니다.
    accountSeq 값은 '계좌' 키워드에서 엔터를 눌러 복사할 수 있습니다.
  - 시스템 파이썬(/usr/bin/python3)만 사용하며 외부 패키지가 필요 없습니다.
  - 응답이 느리거나 rate limit 에 걸리면 각 Script Filter 를 열어
    'Please wait' 지연 값을 늘리세요.
"""


def script_filter(uid, keyword, script, title, subtext, takes_argument=True):
    """Script Filter 오브젝트 하나."""
    return {
        "uid": uid,
        "type": "alfred.workflow.input.scriptfilter",
        "version": 3,
        "config": {
            # 필터링은 스크립트가 직접 한다. Alfred 의 자체 필터를 켜면 종목명
            # 정렬 규칙(티커 완전일치 우선)이 무시된다.
            "alfredfiltersresults": False,
            "alfredfiltersresultsmatchmode": 0,
            "argumenttreatemptyqueryasnil": False,
            "argumenttrimmode": 0,
            "argumenttype": 1 if takes_argument else 2,
            "escaping": 102,
            "keyword": keyword,
            "queuedelaycustom": 3,
            "queuedelayimmediatelyinitially": True,
            "queuedelaymode": 0,
            "queuemode": 1,
            "runningsubtext": "조회 중…",
            "script": script,
            "scriptargtype": 1,  # argv — 스크립트가 sys.argv[1] 로 받는다
            "scriptfile": "",
            "subtext": subtext,
            "title": title,
            "type": 0,  # /bin/bash
            "withspace": takes_argument,
        },
    }


def build():
    objects = [
        script_filter(
            UID_PRICE,
            "주가",
            '/usr/bin/python3 price.py "$1"',
            "종목 시세 조회",
            "종목명 또는 티커로 검색해 현재가를 봅니다",
        ),
        script_filter(
            UID_HOLDINGS,
            "잔고",
            '/usr/bin/python3 holdings.py "$1"',
            "보유 종목 조회",
            "보유 종목과 평가손익을 봅니다",
        ),
        script_filter(
            UID_ACCOUNTS,
            "계좌",
            "/usr/bin/python3 accounts.py",
            "계좌 조회",
            "계좌 목록과 매수가능금액을 봅니다",
            takes_argument=False,
        ),
        {
            "uid": UID_OPEN_URL,
            "type": "alfred.workflow.action.openurl",
            "version": 1,
            "config": {
                "browser": "",
                # 스크립트가 arg 로 완성된 URL 을 넘기므로 그대로 연다.
                "url": "{query}",
                "skipqueryencode": True,
                "skipvarencode": True,
                "spaces": "",
            },
        },
        {
            "uid": UID_CLIPBOARD,
            "type": "alfred.workflow.output.clipboard",
            "version": 3,
            "config": {
                "autopaste": False,
                "clipboardtext": "{query}",
                "ignoredynamicplaceholders": False,
                "transient": False,
            },
        },
    ]

    def link(destination):
        return [{
            "destinationuid": destination,
            "modifiers": 0,
            "modifiersubtext": "",
            "vitoclose": False,
        }]

    plist = {
        "bundleid": BUNDLE_ID,
        "name": "Toss Invest",
        "category": "Productivity",
        "description": "토스증권 시세·계좌 조회 (조회 전용)",
        "createdby": "huneea",
        "webaddress": "https://github.com/huneea/alfred-tossinvest",
        "readme": README,
        "disabled": False,
        "objects": objects,
        "connections": {
            UID_PRICE: link(UID_OPEN_URL),
            UID_HOLDINGS: link(UID_OPEN_URL),
            UID_ACCOUNTS: link(UID_CLIPBOARD),
        },
        "uidata": {
            UID_PRICE: {"xpos": 60, "ypos": 60},
            UID_HOLDINGS: {"xpos": 60, "ypos": 200},
            UID_ACCOUNTS: {"xpos": 60, "ypos": 340},
            UID_OPEN_URL: {"xpos": 380, "ypos": 130},
            UID_CLIPBOARD: {"xpos": 380, "ypos": 340},
        },
        "userconfigurationconfig": [
            {
                "type": "textfield",
                "variable": "TOSS_CLIENT_ID",
                "label": "Client ID",
                "description": "토스증권 WTS > 설정 > Open API 에서 발급한 client id",
                "config": {"default": "", "placeholder": "", "required": True, "trim": True},
            },
            {
                "type": "textfield",
                "variable": "TOSS_CLIENT_SECRET",
                "label": "Client Secret",
                "description": "함께 발급받은 client secret",
                "config": {"default": "", "placeholder": "", "required": True, "trim": True},
            },
            {
                "type": "textfield",
                "variable": "TOSS_ACCOUNT_SEQ",
                "label": "Account Seq",
                "description": "사용할 계좌의 accountSeq. 비우면 첫 번째 계좌를 씁니다",
                "config": {"default": "", "placeholder": "선택", "required": False, "trim": True},
            },
        ],
        "variables": {
            "TOSS_CLIENT_ID": "",
            "TOSS_CLIENT_SECRET": "",
            "TOSS_ACCOUNT_SEQ": "",
        },
        # 워크플로우를 .alfredworkflow 로 내보낼 때 이 값들을 빼고 내보낸다.
        # 자격증명이 배포 파일에 박혀 나가는 사고를 막는다.
        "variablesdontexport": [
            "TOSS_CLIENT_ID",
            "TOSS_CLIENT_SECRET",
            "TOSS_ACCOUNT_SEQ",
        ],
        "version": "0.1.0",
    }

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(root, "workflow", "info.plist")
    with open(target, "wb") as handle:
        plistlib.dump(plist, handle)
    return target


if __name__ == "__main__":
    print(build())
