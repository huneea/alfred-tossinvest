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

## 커밋 계정

이 저장소는 개인 GitHub 계정(`huneea`)으로 커밋한다. 공개 저장소라 회사 이메일이
커밋에 박히면 안 된다. `.git/config` 에 로컬 설정이 들어 있다.

```
user.name   huneea
user.email  67728580+huneea@users.noreply.github.com
```

**`.git/config` 는 클론하면 따라오지 않는다.** 새로 클론했거나 커밋 전에 확인이
필요하면 `git config user.email` 로 값을 보고, 회사 계정이면 위 두 줄을
`git config --local` 로 다시 넣는다.

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
├── watchlist.py          # Script Filter tsw — 관심종목 전용 조회·제거
├── quote.py              # Script Filter tsq — 한 종목 상세 시세
├── holdings.py           # Script Filter tsh — 보유 종목/평가손익
├── accounts.py           # Script Filter tsa — 계좌 목록 + 매수가능금액
├── indices.py            # Script Filter tsi — 코스피·코스닥 지수
├── rankings.py           # Script Filter tsr — 시장 랭킹
├── record.py             # Run Script — 최근 조회 기록 후 URL 통과
├── toggle.py             # Run Script — 관심종목 토글 (⌘↩)
└── tossinvest/
    ├── config.py         # 환경변수, 캐시/데이터 경로, 상수
    ├── errors.py         # TossError 계열 (title/subtitle 을 들고 다님)
    ├── client.py         # urllib HTTP, {result:...} 언랩, 오류 변환
    ├── auth.py           # OAuth2 토큰 발급 + 파일 캐시
    ├── api.py            # 도메인 조회 함수, 종목 마스터 캐시
    ├── store.py          # 관심종목·최근 조회 영속 저장
    ├── view.py           # 종목 목록 렌더링 (tsp·tsw 공용)
    ├── text.py           # 비교용 문자열 정규화 (NFC)
    ├── fmt.py            # 금액/수익률 표시 포맷 (Decimal 기반)
    └── alfred.py         # Script Filter JSON 출력, run() 래퍼
assets/icons/*.svg        # 아이콘 원본 (벡터). 여기를 고친다
build/
├── info_plist.py         # info.plist 생성 (오브젝트·연결·UID 정본)
├── render_icons.js       # SVG -> PNG (macOS NSImage, JXA)
└── preserve_hotkey.py    # 동기화 시 사용자 지정 핫키 보존
build.sh                  # 배포용 .alfredworkflow 번들
sync.sh                   # 설치본에 즉시 반영 + Alfred 리로드
```

진입 스크립트는 얇게 유지한다. 엔드포인트 경로와 응답 껍데기는 `api.py` 가
전담하고, 진입 스크립트는 표시 로직만 담당한다.

`record.py` 는 받은 URL 을 **반드시 그대로 다시 출력**해야 한다. Run Script 의
출력이 다음 오브젝트의 `{query}` 가 되므로, 문자열을 바꾸면 링크가 열리지 않는다.

## 액션을 실행하면 Alfred 창이 닫힌다

그래서 순서 변경을 '한 칸 위/아래' 로 만들면 한 번 옮길 때마다 창을 다시 열어야
한다. `맨 위로`/`맨 아래로` 로 둔 이유다. 반복 동작이 필요한 기능을 설계할 때
이 제약을 먼저 고려할 것.

순서 변경은 관심종목에만 의미가 있다. 등록되지 않은 종목에서는 수식키 정의를
빼지 말고 `valid: false` 로 둔다. 빼버리면 Alfred 가 항목의 기본 `arg`(종목 URL)를
대신 넘겨 엉뚱한 값이 순서 변경 스크립트로 들어간다.

## 자동 갱신은 rerun 으로 한다

Alfred 는 Script Filter 출력의 `rerun`(초)만큼 기다렸다가 같은 화면을 다시
실행한다. 결과창이 열려 있는 동안만 돈다. 수치가 계속 변하는 화면은
`alfred.live()` 로 내보내고, 안내·오류 화면은 `alfred.output()`/`alfred.empty()`
그대로 둔다 — 다시 불러도 결과가 달라지지 않는데 호출만 축낸다.

갱신 주기는 `TOSS_REFRESH_SECONDS` 로 사용자가 끌 수 있어야 한다(0 이면 끔).
갱신마다 API 를 다시 부르므로, **화면 한 번에 나가는 호출 수를 먼저 줄이고 나서**
갱신을 붙인다. 전일 종가(`api.prev_closes`)와 기본 계좌 seq 를 캐싱하는 이유가
이것이다. 새 화면을 live 로 만들 때는 그 화면이 갱신마다 몇 번 호출하는지 세어볼 것.

## 캐시와 사용자 데이터를 섞지 않는다

`config.cache_dir()` 은 지워져도 다시 만들 수 있는 것만 둔다 (토큰, 종목 마스터).
관심종목·최근 조회처럼 사용자가 쌓은 데이터는 `config.data_dir()` 로 간다.
Alfred 는 캐시 디렉터리를 임의로 비울 수 있다.

## 아이콘

원본은 `assets/icons/*.svg` 다. **SVG 를 직접 고친다.** PNG 는 산출물이라 손대지
않는다. `build/render_icons.js` 가 macOS 의 NSImage 로 굽는다 — SVG 를 네이티브로
읽으므로 설치할 것이 없고, 그라디언트·linecap·linejoin 과 안티에일리어싱을 Apple
렌더러가 처리한다.

아이콘은 그 행이 **무엇인지** 알려주는 것으로 고른다. 등락 방향처럼 제목에 이미
숫자로 적혀 있는 내용을 아이콘으로 되풀이하지 않는다.

JXA 주의: `$.NSGraphicsContext.currentContext = ctx` 같은 **속성 대입은 조용히
무시된다.** `setCurrentContext(ctx)` 로 호출해야 한다. 이걸 놓쳐서 아무것도 그리지
않은 투명 PNG 가 '성공' 으로 나온 적이 있다. 그래서 렌더러가 저장 전에 칠해진
픽셀이 있는지 검사한다.

아이콘은 반드시 `icons/` 하위에 둔다. 번들 최상위의 `*.png` 는 Alfred 가 사용자
지정 아이콘(`icon.png`, `<오브젝트 uid>.png`)을 두는 자리이고, `sync.sh` 가 그걸
보호하려고 최상위 png 를 동기화에서 제외한다. 최상위에 두면 설치본에 전달되지
않는다.

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
- **등락률은 전일 종가 캐시로 만든다** — `/api/v1/prices` 는 현재가만 주고
  등락률이 없다. `/api/v1/candles` 로 계산해야 하는데 `symbol` 이 단수라 종목당
  한 번씩 불러야 하고, 목록·검색에 그대로 붙이면 키 입력마다 결과 수만큼 호출이
  나간다. 전일 종가는 다음 장이 열릴 때까지 바뀌지 않으므로 `api.prev_closes()`
  가 캐싱하고, 등락은 이미 한 번에 받아둔 현재가와 그 값으로 계산한다. 종목당
  호출은 그 종목을 처음 본 날 한 번뿐이다. 새 화면에서도 `view.change_rates()`
  를 쓰고 종목마다 캔들을 부르는 코드를 새로 만들지 않는다.
  캐시 만료를 자정이 아니라 **다음 09:00 KST** 로 잡는 이유는, 장 시작 전에
  받아둔 값(그 전날 종가)이 개장 후까지 남으면 등락률 기준이 어긋나기 때문이다.
- **캔들 순서를 가정하지 않는다** — API 가 어떤 순서로 주는지 문서에 없다.
  `api.candles()` 가 timestamp 로 정렬한다. 가정하면 등락 부호가 뒤집힌다.
- **문자열 비교 전에 `text.fold()` 를 통과시킨다** — 한글은 NFC('하')와
  NFD('ㅎ'+'ㅏ')로 다르게 표현될 수 있고, 눈으로는 같아도 문자열로는 다르다.
  API 가 주는 종목명은 NFC 인데 macOS 는 입력 경로에 따라 NFD 를 흘려보내서,
  정규화하지 않으면 같은 검색어가 되기도 하고 안 되기도 한다. 실제로 겪은 버그다.
- **금액은 문자열로 온다** — 응답의 금액·수량·수익률은 전부 문자열이다.
  `float` 로 바꾸지 말고 `fmt.to_decimal()` 을 쓴다.

## 응답 타입을 신뢰하지 않는다

스펙 요약에 string 이라고 적힌 `accountSeq` 가 실제로는 숫자로 왔고, 그 값이
Alfred 항목의 title/arg/uid 로 흘러들어가 화면이 통째로 깨졌다. Alfred 는 이
필드들이 문자열이 아니면 항목을 렌더링하지 못한다. `alfred.item()` 이 출력 직전에
`str()` 로 강제하니 새 필드를 넣을 때 그 경로를 우회하지 말 것.

## 토큰은 만료 전에도 죽는다

`expires_in` 은 24시간이지만 그전에 무효해질 수 있다. 다른 곳에서 토큰을 새로
발급하면 기존 토큰이 죽는다. 그러면 캐시에는 아직 만료되지 않은 토큰이 남아 있어
재발급 없이는 만료 시각까지 계속 401 이 난다. 실제로 겪었다.

`client.get()` 이 401 을 받으면 `auth.access_token(force_refresh=True)` 로 새로
받아 **한 번만** 재시도한다. 두 번째도 401 이면 그대로 올린다. 401 이 아닌 오류는
재시도하지 않는다.

`auth` 가 `client` 를 쓰므로 이 임포트는 함수 안에서 한다. 최상단에 두면 순환
임포트가 된다.

## 예외를 조용히 삼키지 않는다

`accounts.py` 가 매수가능금액 조회 실패를 `except Exception` 으로 잡고 "조회 실패"
라고만 표시하는 바람에, 원인(헤더에 정수를 넣어 urllib 이 거부 → 이후 400)을
찾는 데 왕복이 더 들었다. 사용자에게 보여주는 실패 문구에는 API 가 돌려준
message 까지 붙인다. 어떤 파라미터가 빠졌는지는 대개 거기 적혀 있다.

## 등락은 화면에 보여주는 현재가 기준으로 계산한다

`/api/v1/prices` 의 `lastPrice` 와 일봉의 `closePrice` 는 갱신 시점이 달라 장중에
어긋난다. 현재가는 lastPrice 로 보여주면서 등락만 캔들 종가로 계산하면 화면 안에서
'현재가 - 전일종가 ≠ 표시된 등락' 이 된다. 실제로 겪었다 — 267,000 을 띄우면서
+3,500(266,500 기준)을 함께 보여줬다.

`api.daily_change(token, symbol, last_price)` 에 현재가를 넘겨서 같은 기준으로
계산시킨다. 새 화면을 만들 때도 반드시 넘길 것. 안 넘기면 캔들 종가로 조용히
폴백해서 다시 어긋난다.

## 전일 종가는 기준가로 구한다

**캔들의 종가를 전일 종가로 쓰지 않는다.** 실측에서 캔들이 주는 전일 종가와 거래소
기준가가 어긋났다 — SK하이닉스 캔들 1,572,000 vs 기준가 1,593,000 (1.3%).
`adjusted=false` 로 보정을 꺼도 같은 값이 나왔으므로 수정주가 문제가 아니다.
유력한 설명은 **거래소 차이** 다 — 캔들은 KRX 정규장 종가, 기준가는 넥스트레이드
(NXT) 애프터마켓까지 반영한 최종가. 시장 캘린더 문서가 "통합 모드 (KRX+NXT) 기준"
이라 적고 있고 `KrMarketDetail` 이 두 거래소를 구분해서 다룬다. 확정하지는 못했다.
거래소를 고르는 파라미터가 API 에 없어 캔들을 통합 기준으로 받을 방법이 없다.

기준가가 맞다는 것은 두 경로로 확인했다.

- 상한·하한 두 값이 모두 기준가에서 정확히 떨어진다
  (1,593,000 ×1.3 → 2,070,000, ×0.7 → 1,116,000. 응답과 일치)
- `/api/v1/rankings` 의 `price.basePrice` 가 1,593,000 으로 같았고,
  같은 응답의 `changeRate` 도 우리 계산과 일치했다 (앱 표시와도 동일)

`RankingPrice` 문서가 등락률을 `(lastPrice - basePrice) / basePrice` 로 정의한다.
우리 계산과 같은 식이다.

`api.base_from_limits()` 가 `/api/v1/price-limits` 에서 기준가를 역산한다. 국내
제한폭은 기준가 ±30% 라 두 값의 평균이 곧 기준가다. 상한은 호가단위 내림, 하한은
올림이라 오차가 상쇄돼 반올림 오차는 호가단위의 절반을 넘지 않는다. 호출 비용은
캔들과 같은 종목당 1회다.

제한폭이 없는 종목(정리매매·신규상장)과 해외 종목은 null 이 오므로 캔들로 떨어진다.
그 경로가 `api.previous_close()` 이고, 거기서도 뒤에서 두 번째를 그냥 쓰면 안 된다.
응답에 진행 중인 당일 캔들이 없으면 그저께 종가를 집는다. 날짜를 보고 오늘이 아닌
마지막 캔들을 고른다.

`daily_change()` 는 `isToday` 를 함께 돌려준다. 마지막 캔들이 어제 것이면 시고저·
거래량도 어제 값이라 '당일' 이라고 적으면 거짓이 된다.

전일 종가 캐시에는 `PREV_CLOSE_VERSION` 이 붙어 있다. 계산 방식을 바꾸면 올릴 것.
안 올리면 예전 방식으로 저장해 둔 값이 만료 전까지 살아남아 계속 틀린 값을 보여준다.

## 값이 의심스러우면 랭킹과 대조한다

`/api/v1/rankings` 는 토스가 `basePrice` 와 `changeRate` 를 **직접 주는 유일한
엔드포인트**다. 종목을 지정할 수 없어 평소 조회에는 못 쓰지만, 거래대금 상위권
종목이라면 우리 계산을 정답과 맞춰볼 수 있다. 실제로 이 방법으로 기준가 역산이
맞다는 것을 확정했다.

```
GET /api/v1/rankings?type=MARKET_TRADING_AMOUNT&marketCountry=KR&duration=realtime&count=100
```

`TOP_GAINERS`/`TOP_LOSERS` 는 `basePrice` 가 duration 시작 시점 기준가라 쓰면 안
된다. 나머지 타입은 항상 전일 기준가다.

## 값이 비는 게 정상인 경우가 있다

투자자별 매매동향의 `individual` 은 **당일 장중에는 null 이다.** 개인 확정치가
당일 저녁에야 채워진다고 문서에 명시돼 있다. 기관의 `breakdown` 도 같다.
빈 값을 오류로 취급하지 말고, 화면에도 왜 비었는지 적어 준다.

## 손익률 단위를 섞지 않는다

holdings 계열의 `rate` 는 **소수비율**(0.1077 = 10.77%)이고, 캔들에서 직접
계산하는 등락률은 **퍼센트**다. 표시 함수가 따로 있다 — `fmt.signed_ratio()` 와
`fmt.signed_rate()`. 잘못 고르면 100배 틀린 값이 조용히 화면에 뜬다.

## 스펙을 확인할 때

`openapi.json` 은 커서 통째로 읽으면 뒤가 잘린다. 엔드포인트별 문서
(`…/api-reference/Apis/*.md`, `…/Models/*.md`)를 직접 보는 편이 정확하다.
경로는 `docs/api-notes.md` 에 적어뒀다.

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
