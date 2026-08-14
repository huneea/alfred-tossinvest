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

# 버전은 여기서만 고친다. build.sh 가 이 값을 읽어 산출물 파일명에 붙인다.
VERSION = "0.1.1"

# UID 는 고정한다. 빌드할 때마다 새로 만들면 Alfred 가 기존 연결과 사용자가 지정한
# 핫키를 잃어버린다.
UID_PRICE = "A1B2C3D4-0001-4000-8000-000000000001"
UID_HOLDINGS = "A1B2C3D4-0002-4000-8000-000000000002"
UID_ACCOUNTS = "A1B2C3D4-0003-4000-8000-000000000003"
UID_OPEN_URL = "A1B2C3D4-0004-4000-8000-000000000004"
UID_CLIPBOARD = "A1B2C3D4-0005-4000-8000-000000000005"
UID_QUOTE = "A1B2C3D4-0006-4000-8000-000000000006"
UID_RECORD = "A1B2C3D4-0007-4000-8000-000000000007"
UID_TOGGLE = "A1B2C3D4-0008-4000-8000-000000000008"
UID_NOTIFY = "A1B2C3D4-0009-4000-8000-000000000009"
UID_HOTKEY = "A1B2C3D4-0010-4000-8000-000000000010"
UID_WATCHLIST = "A1B2C3D4-0011-4000-8000-000000000011"
UID_REORDER = "A1B2C3D4-0012-4000-8000-000000000012"

# NSEvent 수식키 플래그. Alfred 는 연결마다 이 값으로 어떤 수식키를 눌렀을 때
# 그 경로로 갈지 판단한다.
MOD_NONE = 0
MOD_CMD = 1048576
MOD_ALT = 524288
MOD_CTRL = 262144

README = """토스증권 Open API 로 시세와 계좌를 조회합니다. 조회 전용이며 주문 기능은 없습니다.

■ 사용법  (ts = Toss, 뒤에 한 글자)
  tsp                  관심종목의 현재가와 등락률을 한 번에 봅니다
                       (관심종목이 없으면 최근 조회한 종목을 보여줍니다)
  tsp <종목명|티커>    종목 검색                          (price)
  tsw                  관심종목만 봅니다                  (watchlist)
  tsw <검색어>         관심종목 안에서 좁히기
  tsq <종목명|티커>    등락·시가/고가/저가·거래량·호가    (quote)
  tsh [티커]           보유 종목과 평가손익               (holdings)
  tsa                  계좌 목록과 매수가능금액           (accounts)
                       엔터로 accountSeq 복사

  ↩   토스증권에서 열기 (최근 조회에 기록됩니다)
  ⌘↩  관심종목 추가/제거
  ⌥↩  관심종목 맨 위로   ⌃↩  맨 아래로

■ 관심종목 관리
  등록  tsp 로 종목을 검색한 뒤 ⌘↩
  제거  tsw 에서 해당 종목에 ⌘↩ (tsp 검색 결과에서도 됩니다)
  확인  tsw — 등록한 종목만 보여줍니다. 별 아이콘이 등록된 종목입니다.

■ 핫키
  이 워크플로우의 Hotkey 오브젝트는 비어 있습니다. 더블클릭해 원하는 키를
  지정하면 Alfred 를 거치지 않고 관심종목 시세를 바로 띄울 수 있습니다.

■ 설정 (필수)
  1. 토스증권 WTS > 설정 > Open API 에서 앱을 등록해 client id/secret 을 발급받습니다.
  2. 같은 화면에서 이 맥의 공인 IP 를 허용 목록에 등록합니다.
     등록하지 않은 IP 에서의 요청은 403 으로 거부됩니다.
     현재 IP 확인: curl -s https://api.ipify.org
     네트워크를 옮기면 IP 를 다시 등록해야 합니다.
  3. 위 Workflow Configuration 에 client id/secret 을 입력합니다.

■ 자동 갱신
  결과창을 열어두면 시세가 주기적으로 다시 불러와집니다. 기본 2초이며, 위
  Workflow Configuration 의 '자동 갱신(초)' 에서 바꾸거나 0 으로 끌 수 있습니다.

■ 참고
  - 계좌가 여러 개면 Account Seq 를 지정하세요. 비우면 첫 번째 계좌를 씁니다.
    accountSeq 값은 tsa 에서 엔터를 눌러 복사할 수 있습니다.
  - 등락률은 API 가 시세와 함께 주지 않아 전일 종가로 직접 계산합니다. 전일
    종가는 다음 장이 열릴 때까지 캐싱하므로 종목당 조회는 처음 한 번뿐입니다.
  - 관심종목이 아주 많거나 자동 갱신 주기가 짧으면 rate limit 에 걸릴 수
    있습니다. 그럴 때는 갱신 주기를 늘리거나 0 으로 끄세요.
  - 시스템 파이썬(/usr/bin/python3)만 사용하며 외부 패키지가 필요 없습니다.
  - 응답이 느리거나 rate limit 에 걸리면 각 Script Filter 를 열어
    'Please wait' 지연 값을 늘리세요.
"""


def script_filter(uid, keyword, script, arg_hint, subtext, takes_argument=True):
    """Script Filter 오브젝트 하나.

    제목은 키워드에서 조립한다. 'ts' 만 쳤을 때 뜨는 목록에서 어떤 키워드인지,
    뒤에 무엇을 더 입력해야 하는지 한눈에 보이게 하기 위해서다. 손으로 적으면
    키워드를 바꿀 때 제목이 따라오지 않고 어긋난다.

    arg_hint 는 <필수> / [선택] 표기를 그대로 넘긴다. 인자가 없으면 None.
    """
    title = "{0} {1}".format(keyword, arg_hint) if arg_hint else keyword

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
            "tsp",
            '/usr/bin/python3 price.py "$1"',
            "[종목명|티커]",
            "비우면 관심종목 시세 · 입력하면 종목을 검색합니다",
        ),
        script_filter(
            UID_HOLDINGS,
            "tsh",
            '/usr/bin/python3 holdings.py "$1"',
            "[종목명]",
            "보유 종목과 평가손익 · 입력하면 그 종목만 추립니다",
        ),
        script_filter(
            UID_ACCOUNTS,
            "tsa",
            "/usr/bin/python3 accounts.py",
            None,
            "계좌 목록과 매수가능금액 · ↩ 로 accountSeq 복사",
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
        script_filter(
            UID_WATCHLIST,
            "tsw",
            '/usr/bin/python3 watchlist.py "$1"',
            "[검색어]",
            "관심종목만 보기 · ⌘↩ 로 제거합니다",
        ),
        script_filter(
            UID_QUOTE,
            "tsq",
            '/usr/bin/python3 quote.py "$1"',
            "<종목명|티커>",
            "상세 시세 — 등락·시고저·거래량·호가·상하한가",
        ),
        {
            # 최근 조회를 기록한 뒤 받은 URL 을 그대로 흘려보낸다. Script Filter 와
            # Open URL 사이에 끼워 쓴다.
            "uid": UID_RECORD,
            "type": "alfred.workflow.action.script",
            "version": 2,
            "config": {
                "concurrently": False,
                "escaping": 102,
                "script": '/usr/bin/python3 record.py "$1"',
                "scriptargtype": 1,
                "scriptfile": "",
                "type": 0,
            },
        },
        {
            "uid": UID_REORDER,
            "type": "alfred.workflow.action.script",
            "version": 2,
            "config": {
                "concurrently": False,
                "escaping": 102,
                "script": '/usr/bin/python3 reorder.py "$1"',
                "scriptargtype": 1,
                "scriptfile": "",
                "type": 0,
            },
        },
        {
            "uid": UID_TOGGLE,
            "type": "alfred.workflow.action.script",
            "version": 2,
            "config": {
                "concurrently": False,
                "escaping": 102,
                "script": '/usr/bin/python3 toggle.py "$1"',
                "scriptargtype": 1,
                "scriptfile": "",
                "type": 0,
            },
        },
        {
            "uid": UID_NOTIFY,
            "type": "alfred.workflow.output.notification",
            "version": 1,
            "config": {
                "lastpathcomponent": False,
                "onlyshowifquerypopulated": True,
                "removeextension": False,
                "text": "{query}",
                "title": "Toss Invest",
            },
        },
        {
            # 핫키는 일부러 비워둔다. 임의로 배정하면 기존 단축키와 충돌할 수 있어
            # 사용자가 Alfred UI 에서 직접 지정하게 한다.
            "uid": UID_HOTKEY,
            "type": "alfred.workflow.trigger.hotkey",
            "version": 2,
            "config": {
                "action": 0,
                "argument": 0,
                "focusedappvariable": False,
                "focusedappvariablename": "",
                "leftcursor": False,
                "modsmode": 0,
                "relatedAppsMode": 0,
            },
        },
    ]

    def link(destination, modifiers=MOD_NONE, subtext=""):
        return {
            "destinationuid": destination,
            "modifiers": modifiers,
            "modifiersubtext": subtext,
            "vitoclose": False,
        }

    def _stock_links():
        """종목 항목을 보여주는 화면의 공통 연결.

        ↩ 열기, ⌘↩ 관심종목 토글, ⌥↩ 맨 위로, ⌃↩ 맨 아래로.
        """
        return [
            link(UID_RECORD),
            link(UID_TOGGLE, MOD_CMD, "관심종목 토글"),
            link(UID_REORDER, MOD_ALT, "맨 위로"),
            link(UID_REORDER, MOD_CTRL, "맨 아래로"),
        ]

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
            # ↩ 는 기록을 거쳐 링크로, ⌘↩ 는 관심종목 토글로 간다.
            UID_PRICE: _stock_links(),
            UID_QUOTE: _stock_links(),
            UID_WATCHLIST: _stock_links(),
            UID_HOLDINGS: _stock_links(),
            UID_ACCOUNTS: [link(UID_CLIPBOARD)],
            UID_RECORD: [link(UID_OPEN_URL)],
            UID_TOGGLE: [link(UID_NOTIFY)],
            UID_REORDER: [link(UID_NOTIFY)],
            # 핫키를 누르면 관심종목 목록(빈 쿼리의 주가 화면)이 바로 열린다.
            UID_HOTKEY: [link(UID_PRICE)],
        },
        "uidata": {
            UID_HOTKEY: {"xpos": 40, "ypos": 40},
            UID_PRICE: {"xpos": 220, "ypos": 40},
            UID_WATCHLIST: {"xpos": 220, "ypos": 180},
            UID_QUOTE: {"xpos": 220, "ypos": 320},
            UID_HOLDINGS: {"xpos": 220, "ypos": 460},
            UID_ACCOUNTS: {"xpos": 220, "ypos": 600},
            UID_RECORD: {"xpos": 520, "ypos": 120},
            UID_TOGGLE: {"xpos": 520, "ypos": 260},
            UID_REORDER: {"xpos": 520, "ypos": 380},
            UID_OPEN_URL: {"xpos": 760, "ypos": 120},
            UID_NOTIFY: {"xpos": 760, "ypos": 260},
            UID_CLIPBOARD: {"xpos": 520, "ypos": 460},
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
            {
                "type": "textfield",
                "variable": "TOSS_REFRESH_SECONDS",
                "label": "자동 갱신(초)",
                "description": "결과창을 열어둔 동안 시세를 다시 불러오는 주기. "
                               "0 이면 끕니다. 1~5 초까지 지정할 수 있습니다",
                "config": {"default": "2", "placeholder": "2", "required": False, "trim": True},
            },
        ],
        "variables": {
            "TOSS_CLIENT_ID": "",
            "TOSS_CLIENT_SECRET": "",
            "TOSS_ACCOUNT_SEQ": "",
            "TOSS_REFRESH_SECONDS": "2",
        },
        # 워크플로우를 .alfredworkflow 로 내보낼 때 이 값들을 빼고 내보낸다.
        # 자격증명이 배포 파일에 박혀 나가는 사고를 막는다.
        "variablesdontexport": [
            "TOSS_CLIENT_ID",
            "TOSS_CLIENT_SECRET",
            "TOSS_ACCOUNT_SEQ",
        ],
        "version": VERSION,
    }

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(root, "workflow", "info.plist")
    with open(target, "wb") as handle:
        plistlib.dump(plist, handle)
    return target


if __name__ == "__main__":
    print(build())
