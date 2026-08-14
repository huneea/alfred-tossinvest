# alfred-tossinvest

토스증권 Open API 로 종목 시세와 내 계좌를 조회하는 Alfred 5 워크플로우.

**조회 전용입니다.** 주문/정정/취소 API 는 구현하지 않습니다. 토스증권 Open API
는 모의투자 환경이 없어 모든 호출이 실계좌에 그대로 나가기 때문입니다.

## 기능

키워드는 `ts`(Toss) + 한 글자입니다.

| 키워드 | 동작 |
| --- | --- |
| `tsp` | 관심종목의 현재가와 등락률을 한 번에. 없으면 최근 조회한 종목 |
| `tsp <종목명\|티커>` | 종목 검색 (**p**rice) |
| `tsq <종목명\|티커>` | 등락, 시/고/저, 거래량, 호가, 상하한가 (**q**uote) |
| `tsh [티커]` | 보유 종목과 평가손익 (**h**oldings) |
| `tsa` | 계좌 목록과 매수 가능 금액. 엔터로 `accountSeq` 복사 (**a**ccounts) |

| 키 | 동작 |
| --- | --- |
| `↩` | 토스증권에서 열기. 최근 조회에 기록됩니다 |
| `⌘↩` | 관심종목 추가/제거 |

핫키는 비워둔 채로 배포됩니다. 임의로 배정하면 기존 단축키와 충돌할 수 있어서,
Alfred 에서 Hotkey 오브젝트를 더블클릭해 직접 지정하세요. 지정하면 Alfred 를
거치지 않고 관심종목 시세가 바로 뜹니다.

### 등락률에 대해

`GET /api/v1/prices` 는 **현재가만** 줍니다. 등락률·거래량·시고저가 없어서
일봉 2개(`/api/v1/candles`)로 직접 계산합니다. 이 호출은 **종목당 한 번**이라,
키 입력마다 실행되는 검색 결과에는 붙이지 않습니다. 종목 수가 정해져 있는
관심종목 목록과 `tsq` 상세 화면에서만 씁니다.

`tsq` 도 종목이 확정되기 전에는 상세를 부르지 않습니다. 티커나 종목명이 정확히
일치할 때만 상세로 넘어가고, 그전에는 현재가만 붙인 후보 목록을 보여줍니다.

## 사전 준비

1. 토스증권 WTS > **설정 > Open API** 에서 앱을 등록하고 `client_id`,
   `client_secret` 을 발급받습니다.
2. 같은 화면에서 **허용 IP 를 등록합니다.** 등록되지 않은 IP 에서의 요청은
   403 으로 거부됩니다. 노트북에서 네트워크를 옮기면 다시 등록해야 합니다.

현재 공인 IP 확인:

```sh
curl -s https://api.ipify.org
```

## 개발 중 반영 (설치 후)

```sh
./sync.sh
```

이미 설치된 워크플로우에 소스를 바로 밀어넣고 Alfred 를 리로드합니다. 번들을
다시 만들어 임포트할 필요가 없습니다.

두 가지를 지킵니다.

- **`prefs.plist` 를 건드리지 않습니다.** 입력한 Client ID/Secret 이 여기 있습니다.
- **핫키를 보존합니다.** 핫키 조합은 `info.plist` 안에 저장되기 때문에, 새로 생성한
  plist 로 그냥 덮어쓰면 지정해둔 단축키가 사라집니다. `build/preserve_hotkey.py`
  가 설치본에서 뽑아 다시 심습니다.

`--delete` 로 동기화하므로 소스에서 지운 파일은 설치본에서도 사라집니다.

## 빌드 (배포용)

```sh
./build.sh
```

`dist/Toss Invest.alfredworkflow` 가 만들어집니다. **더블클릭하면 설치됩니다.**

`.alfredworkflow` 는 `info.plist` 가 최상위에 있는 폴더를 zip 으로 압축하고
확장자만 바꾼 것입니다. `build.sh` 가 하는 일은 네 단계입니다.

1. `build/info_plist.py` 로 `workflow/info.plist` 생성
2. `plutil -lint` 로 plist 검증
3. `compileall` 로 파이썬 문법 검증
4. `workflow/` 의 **내용물**을 zip (디렉터리째 압축하면 Alfred 가 `info.plist`
   를 못 찾습니다)

`info.plist` 는 손으로 쓰지 않고 `build/info_plist.py` 에서 생성합니다. 오브젝트
UID 는 스크립트에 고정돼 있어 다시 빌드해도 사용자가 지정한 핫키와 연결이
유지됩니다.

Alfred UI 에서 워크플로우를 직접 수정했다면 그 내용은 다음 빌드 때 덮어써집니다.
바꾼 것을 유지하려면 `build/info_plist.py` 에 반영하세요.

## 설정

설치 후 Alfred 워크플로우 화면의 **Configure Workflow** 에서 입력합니다.

| 항목 | 변수 | 필수 | 설명 |
| --- | --- | --- | --- |
| Client ID | `TOSS_CLIENT_ID` | 필수 | 발급받은 client id |
| Client Secret | `TOSS_CLIENT_SECRET` | 필수 | 발급받은 client secret |
| Account Seq | `TOSS_ACCOUNT_SEQ` | 선택 | 사용할 계좌. 비우면 첫 번째 계좌 |

세 값 모두 `variablesdontexport` 에 등록돼 있어 워크플로우를 `.alfredworkflow`
로 내보낼 때 값이 딸려가지 않습니다.

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
