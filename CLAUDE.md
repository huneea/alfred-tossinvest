# CLAUDE.md

토스증권 Open API 로 종목 시세와 내 계좌를 조회하는 Alfred 워크플로우.

## 절대 지켜야 할 것

**주문 API 를 구현하지 않는다.** 토스증권 Open API 에는 주문/정정/취소
(`POST /api/v1/orders`, `/api/v1/conditional-orders`)가 있지만 이 워크플로우는
조회 전용이다. 샌드박스 환경이 없어 모든 호출이 실계좌에 그대로 나가고, Alfred
런처 특성상 오타 한 번이 주문으로 이어질 수 있다. 주문 경로를 코드에 두지 않는
것 자체가 안전장치다. 요청이 있어도 사용자에게 이 결정을 먼저 확인한다.

**자격증명을 저장소에 커밋하지 않는다.** `client_id`/`client_secret` 은 Alfred
워크플로우 환경변수로만 주입한다. `.gitignore` 가 `.env`·`*.pem` 을 막고 있지만
테스트 코드나 문서에 실제 키를 넣지 않도록 주의한다.

## 런타임 제약

Alfred 는 스크립트를 최소 PATH(`/bin:/usr/bin:/usr/local/bin`)로 실행한다. 이
맥의 `python3` 는 pyenv shim(`~/.pyenv/shims`), `node` 는 nvm 경로라 **Alfred
안에서는 둘 다 잡히지 않는다.** 그래서:

- 인터프리터는 `/usr/bin/python3` (시스템 파이썬 **3.9.6**) 로 못 박는다.
  진입 스크립트 shebang 도 `#!/usr/bin/python3` 이다.
- **표준 라이브러리만 쓴다.** pip 설치가 필요한 코드는 넣지 않는다. HTTP 는
  `urllib` 로 처리한다.
- 3.10+ 문법(`match`, `X | Y` 런타임 어노테이션)을 쓰지 않는다. 어노테이션은
  `from __future__ import annotations` 로 문자열화한다.

## 구조

```
workflow/                 # 이 디렉터리가 곧 Alfred 워크플로우 번들
├── price.py              # Script Filter tsp — 관심종목 목록 / 종목 검색
├── quote.py              # Script Filter tsq — 한 종목 상세 시세
├── holdings.py           # Script Filter tsh — 보유 종목/평가손익
├── accounts.py           # Script Filter tsa — 계좌 목록 + 매수가능금액
├── record.py             # Run Script — 최근 조회 기록 후 URL 통과
├── toggle.py             # Run Script — 관심종목 토글 (⌘↩)
└── tossinvest/
    ├── config.py         # 환경변수, 캐시/데이터 경로, 상수
    ├── errors.py         # TossError 계열 (title/subtitle 을 들고 다님)
    ├── client.py         # urllib HTTP, {result:...} 언랩, 오류 변환
    ├── auth.py           # OAuth2 토큰 발급 + 파일 캐시
    ├── api.py            # 도메인 조회 함수, 종목 마스터 캐시
    ├── store.py          # 관심종목·최근 조회 영속 저장
    ├── fmt.py            # 금액/수익률 표시 포맷 (Decimal 기반)
    └── alfred.py         # Script Filter JSON 출력, run() 래퍼
build/
├── info_plist.py         # info.plist 생성 (오브젝트·연결·UID 정본)
└── preserve_hotkey.py    # 동기화 시 사용자 지정 핫키 보존
build.sh                  # 배포용 .alfredworkflow 번들
sync.sh                   # 설치본에 즉시 반영 + Alfred 리로드
```

진입 스크립트는 얇게 유지한다. 엔드포인트 경로와 응답 껍데기는 `api.py` 가
전담하고, 진입 스크립트는 표시 로직만 담당한다.

`record.py` 는 받은 URL 을 **반드시 그대로 다시 출력**해야 한다. Run Script 의
출력이 다음 오브젝트의 `{query}` 가 되므로, 문자열을 바꾸면 링크가 열리지 않는다.

## 캐시와 사용자 데이터를 섞지 않는다

`config.cache_dir()` 은 지워져도 다시 만들 수 있는 것만 둔다 (토큰, 종목 마스터).
관심종목·최근 조회처럼 사용자가 쌓은 데이터는 `config.data_dir()` 로 간다.
Alfred 는 캐시 디렉터리를 임의로 비울 수 있다.

## 설치본에 반영할 때

`./sync.sh` 를 쓴다. 직접 복사하지 않는다. 두 가지를 잃기 쉽다.

- `prefs.plist` — 사용자가 입력한 Client ID/Secret 이 여기 있다. 덮어쓰지 않는다.
- `info.plist` 안의 핫키 — 사용자가 지정한 조합이 여기 저장된다. 생성한 plist 로
  덮어쓰기 전에 `build/preserve_hotkey.py` 로 옮긴다.

## 오류를 다루는 방식

Script Filter 스크립트가 예외로 죽으면 사용자에게는 **빈 목록**만 보인다. 그래서
`alfred.run()` 이 `TossError` 를 잡아 결과 항목 하나로 렌더링한다. 사용자가
스스로 고칠 수 있는 오류(설정 누락, IP 미등록, rate limit)는 반드시 `TossError`
계열로 던져 화면에 이유가 뜨게 한다. 예상 못 한 예외는 일부러 그대로 올려보내
Alfred 디버거에서 스택을 볼 수 있게 둔다.

## 자주 걸리는 함정

- **IP 허용 목록** — 등록되지 않은 공인 IP 에서의 요청은 403 이다. 네트워크를
  옮기면 토스증권 WTS > 설정 > Open API 에서 IP 를 다시 등록해야 한다.
  `client.py` 가 403 을 이 안내 문구로 바꿔서 보여준다.
- **Rate limit** — Script Filter 는 키 입력마다 실행된다. 토큰(`auth.py`)과
  종목 마스터(`api.py`)를 반드시 캐싱해야 한다. 캐싱 없이 호출을 추가하지 않는다.
- **검색 결과에 종목당 호출을 붙이지 않는다** — `/api/v1/prices` 는 현재가만 주고
  등락률·거래량이 없어서 `/api/v1/candles` 로 계산하는데, 이건 `symbol` 이 단수라
  종목당 한 번씩 불러야 한다. 검색 결과 15건에 붙이면 키 입력마다 15회다.
  종목 수가 정해진 화면(관심종목, 확정된 상세)에서만 쓰고, 그때도
  `api.daily_changes()` 로 동시 실행 수를 제한해 병렬 호출한다.
- **캔들 순서를 가정하지 않는다** — API 가 어떤 순서로 주는지 문서에 없다.
  `api.candles()` 가 timestamp 로 정렬한다. 가정하면 등락 부호가 뒤집힌다.
- **금액은 문자열로 온다** — 응답의 금액·수량·수익률은 전부 문자열이다.
  `float` 로 바꾸지 말고 `fmt.to_decimal()` 을 쓴다.

## 확인되지 않은 스펙

`GET /api/v1/buying-power` 의 응답 필드명은 공식 스키마로 확인하지 못했다.
`accounts.py` 는 `amount` 를 가정하고 있으며, 실호출로 검증한 뒤 고쳐야 한다.
`docs/api-notes.md` 참고.

## 테스트

실계좌 API 라 자동화 테스트로 실호출을 하지 않는다. 문법·임포트 검증은:

```sh
/usr/bin/python3 -m compileall -q workflow
cd workflow && /usr/bin/python3 -c "import tossinvest.api, tossinvest.alfred"
```

동작 확인은 자격증명을 export 한 뒤 진입 스크립트를 직접 실행한다:

```sh
cd workflow
export TOSS_CLIENT_ID=... TOSS_CLIENT_SECRET=...
/usr/bin/python3 price.py 삼성전자
```
