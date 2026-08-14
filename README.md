# alfred-tossinvest

토스증권 Open API 로 종목 시세와 내 계좌를 조회하는 Alfred 5 워크플로우.

**조회 전용입니다.** 주문/정정/취소 API 는 구현하지 않습니다. 토스증권 Open API
는 모의투자 환경이 없어 모든 호출이 실계좌에 그대로 나가기 때문입니다.

## 기능

| 키워드 | 동작 |
| --- | --- |
| `주가 <종목명\|티커>` | 종목 검색 후 현재가 표시. 엔터로 토스증권 종목 페이지 열기 |
| `잔고` | 보유 종목, 평가금액, 평가손익 |
| `계좌` | 계좌 목록과 매수 가능 금액. 엔터로 `accountSeq` 복사 |

## 사전 준비

1. 토스증권 WTS > **설정 > Open API** 에서 앱을 등록하고 `client_id`,
   `client_secret` 을 발급받습니다.
2. 같은 화면에서 **허용 IP 를 등록합니다.** 등록되지 않은 IP 에서의 요청은
   403 으로 거부됩니다. 노트북에서 네트워크를 옮기면 다시 등록해야 합니다.

현재 공인 IP 확인:

```sh
curl -s https://api.ipify.org
```

## 설치

`workflow/` 디렉터리의 내용이 Alfred 워크플로우 번들입니다. Alfred 설정에서
빈 워크플로우를 만든 뒤 이 파일들을 번들 안에 넣고, Script Filter 를
`price.py` / `holdings.py` / `accounts.py` 에 연결합니다.

Script Filter 설정:

- Language: `/bin/bash`
- Script: `/usr/bin/python3 price.py "$1"`
- with input as **argv**

`python3` 를 그냥 쓰지 말고 `/usr/bin/python3` 로 적으세요. Alfred 는 최소
PATH 로 스크립트를 실행해서 pyenv·nvm 경로를 보지 못합니다.

## 설정

Alfred 워크플로우 설정(**Configure Workflow > Variables**)에 등록합니다.

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `TOSS_CLIENT_ID` | 필수 | 발급받은 client id |
| `TOSS_CLIENT_SECRET` | 필수 | 발급받은 client secret |
| `TOSS_ACCOUNT_SEQ` | 선택 | 사용할 계좌. 비우면 첫 번째 계좌를 씁니다 |

두 자격증명에는 **"Don't Export"** 를 체크하세요. 워크플로우를 `.alfredworkflow`
로 내보낼 때 값이 함께 딸려가는 것을 막습니다.

## 터미널에서 실행

```sh
cd workflow
export TOSS_CLIENT_ID=... TOSS_CLIENT_SECRET=...
/usr/bin/python3 price.py 삼성전자
/usr/bin/python3 holdings.py
/usr/bin/python3 accounts.py
```

Script Filter 용 JSON 이 출력됩니다.

## 캐시

토큰과 종목 마스터는 Alfred 워크플로우 캐시 디렉터리에 저장됩니다. Alfred 밖에서
실행하면 `~/Library/Caches/me.hhjung.tossinvest/` 를 씁니다. 종목 마스터 TTL 은
1일입니다. 캐시를 비우려면 해당 디렉터리를 지우세요.

## 요구사항

macOS 시스템 파이썬(`/usr/bin/python3`, 3.9) 외에 필요한 것이 없습니다.
외부 패키지를 쓰지 않습니다.

## 문서

- `CLAUDE.md` — 설계 결정과 제약
- `docs/api-notes.md` — API 스펙 정리
