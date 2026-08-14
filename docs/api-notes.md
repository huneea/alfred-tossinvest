# 토스증권 Open API 정리

출처: <https://developers.tossinvest.com/docs>
LLM 용 인덱스 `https://developers.tossinvest.com/llms.txt`,
정규 스펙 `https://openapi.tossinvest.com/openapi-docs/latest/openapi.json`

Base URL: `https://openapi.tossinvest.com`

## 인증

```
POST /oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=...&client_secret=...
```

응답(껍데기 없음):

```json
{ "access_token": "...", "token_type": "Bearer", "expires_in": 86400 }
```

이후 모든 요청에 `Authorization: Bearer {access_token}`.
계좌·자산·주문 계열은 `X-Tossinvest-Account: {accountSeq}` 를 추가로 요구한다.

`client_id`/`client_secret` 은 토스증권 WTS > 설정 > Open API 에서 발급한다.
**같은 화면에서 허용 IP 를 등록해야 한다. 미등록 IP 는 403.**

## 사용하는 엔드포인트

| 기능 | 엔드포인트 | 파라미터 |
| --- | --- | --- |
| 계좌 목록 | `GET /api/v1/accounts` | 없음 |
| 보유 주식 | `GET /api/v1/holdings` | 계좌 헤더 |
| 매수 가능 금액 | `GET /api/v1/buying-power` | 계좌 헤더 + `currency` **필수** |
| 현재가 | `GET /api/v1/prices` | `symbols` (쉼표 구분, 최대 200) |
| 전종목 마스터 | `GET /api/v1/stocks/all` | `market` 필수, `status` 기본 ACTIVE |

`market` 허용값: `KOSPI`, `KOSDAQ`, `NYSE`, `NASDAQ`, `AMEX`, `KR_ETC`, `US_ETC`.

## 응답 껍데기

인증 엔드포인트를 제외한 모든 응답은 `{"result": ...}` 로 감싸여 온다.
`client.get()` 이 이 껍데기를 벗겨서 반환한다.

금액·수량·수익률은 **문자열**로 온다. (`"lastPrice": "71500"`)

### 확인된 필드

`GET /api/v1/accounts` → `result: []`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `accountNo` | String | 계좌번호 |
| `accountSeq` | **Long** | 계좌 식별 키. 다른 API 호출 시 이 값을 헤더로 쓴다 |
| `accountType` | String | `BROKERAGE`(위탁, 국내·해외 주식 통합) / `OVERSEAS_DERIVATIVES`(해외파생) / `PENSION_SAVINGS`(연금저축) / `RESHORING_INVESTMENT`(리쇼어링투자, RIA) |

`accountName`, `accountNumber`, `status`, `currency` 는 **없다.** 초기 스펙 요약에
그렇게 적혀 있었지만 `Models/Account.md` 기준 실제 필드는 위 세 개뿐이다.

문서가 accountType 의 "알 수 없는 enum 값을 처리하라"고 명시한다. `accounts.py`
는 매핑에 없는 값이면 원래 문자열을 그대로 보여준다.

`GET /api/v1/holdings` → `result: HoldingsOverview`
쿼리 `symbol` 은 선택 (특정 종목만 조회).

```
result (HoldingsOverview)
├── items: [HoldingsItem]        ← 보유 종목 목록. holdings 가 아니다
├── totalPurchaseAmount: Price
├── marketValue:    { amount: Price, amountAfterCost: Price }
├── profitLoss:     { amount: Price, amountAfterCost: Price, rate, rateAfterCost }
└── dailyProfitLoss:{ amount: Price, rate }

HoldingsItem
├── symbol, name, marketCountry, currency
├── quantity, lastPrice, averagePurchasePrice
├── marketValue:    { purchaseAmount, amount, amountAfterCost }
├── profitLoss:     { amount, amountAfterCost, rate, rateAfterCost }
├── dailyProfitLoss:{ amount, rate }
└── cost

Price = { krw, usd }   국내만 있으면 usd 는 null, krw 는 종목이 없어도 0
```

**손익률(`rate`)은 퍼센트가 아니라 소수비율이다.** `0.1077` = 10.77%.
`fmt.signed_ratio()` 로 표시한다. 캔들에서 직접 계산하는 등락률은 이미 퍼센트라
`fmt.signed_rate()` 를 쓴다. 둘을 섞으면 100배 틀린다.

개요의 금액은 통화별로 나뉜 `Price` 지만, 종목 항목의 금액은 그냥 숫자이고
해당 종목의 `currency` 기준이다.

`GET /api/v1/prices` → `result: []`
`symbol`, `timestamp`, `lastPrice`, `currency`

`GET /api/v1/stocks/all` → `result: []`
`symbol`, `name`, `securityType`, `isCommonShare`, `isinCode`

`GET /api/v1/buying-power` → `result: {}`
`currency`, `cashBuyingPower` (현금 기반 매수 가능 금액, 미수 미발생 기준)

**`currency` 는 필수 쿼리 파라미터다.** 빼면 400 이 떨어진다. 이 엔드포인트는
Account 가 아니라 **ORDER_INFO** rate limit 그룹(6 req/s, 09:00–09:10 KST 3 req/s)
에 속한다.

### 실제 응답이 문서와 다른 부분

`accountSeq` 는 스펙 요약에 string 으로 적혀 있었지만 **실제로는 숫자**로 온다.
헤더 값과 Alfred 항목의 title/arg/uid 는 문자열이어야 해서 `str()` 로 맞춘다.
`OrderInfoApi.md` 의 파라미터 표에도 `X-Tossinvest-Account` 가 Long 으로 적혀 있다.

`accountName`, `accountNumber` 는 비어서 오는 경우가 있다. `accounts.py` 가
`계좌 <seq>` 로 떨어뜨린다.

### 개별 엔드포인트 문서

`openapi.json` 은 커서 통째로 읽으면 잘린다. 엔드포인트별 문서를 직접 보는 편이
빠르고 정확하다.

- `…/api-reference/Apis/OrderInfoApi.md` — buying-power, sellable-quantity, commissions
- `…/api-reference/Apis/AccountApi.md` — accounts
- `…/api-reference/Apis/AssetApi.md` — holdings
- `…/api-reference/Models/<모델명>.md` — 응답 모델 필드

베이스: `https://openapi.tossinvest.com/openapi-docs/latest/`

## 등락률을 구하는 방법

전일 종가·기준가·등락률을 **직접 주는 엔드포인트가 없다.** `MarketDataApi.md` 가
명시한다. `PriceResponse` 는 `lastPrice` 뿐이고 `StockInfo` 는 가격이 없다.
`/api/v1/rankings` 만 `price.basePrice` 와 `price.changeRate` 를 주지만 임의 종목을
지정할 수 없어 관심종목 조회에는 못 쓴다.

그래서 기준가를 `/api/v1/price-limits` 에서 역산한다.

```
기준가 = (upperLimitPrice + lowerLimitPrice) / 2      국내 제한폭 ±30%
등락률 = (lastPrice - 기준가) / 기준가 × 100
```

검산 (SK하이닉스, 실측):

```
1,593,000 × 1.3 = 2,070,900 → 호가단위 내림 = 2,070,000  (응답과 일치)
1,593,000 × 0.7 = 1,115,100 → 올림          = 1,116,000  (응답과 일치)
```

**캔들 종가를 쓰면 안 된다.** 캔들이 주는 전일 종가가 기준가와 어긋난다. 실측:

```
SK하이닉스 (2026-08-14)
  캔들 전일 종가 adjusted=true   1,572,000
  캔들 전일 종가 adjusted=false  1,572,000   ← 보정을 꺼도 같다
  기준가 (상하한가 역산)          1,593,000
  랭킹 basePrice                1,593,000   ← 토스가 직접 주는 값
```

`adjusted` 를 꺼도 같으므로 수정주가 문제가 아니다. 기준가 쪽이 맞다는 것은
상하한가 검산과 랭킹 `basePrice` 두 경로로 확인됐다.

**유력한 설명은 거래소 차이다.** 캔들은 KRX 정규장 종가이고 기준가는 넥스트레이드
(NXT) 애프터마켓까지 반영한 최종가로 보인다. 근거:

- 시장 캘린더 문서가 "통합 모드 (KRX+NXT) 기준" 이라고 명시한다
- `KrMarketDetail` 이 `nxtSupported`, `krxTradingSuspended`, `nxtTradingSuspended`
  로 두 거래소를 구분해서 다룬다

확정하지는 못했다. `candles`·`prices` 어디에도 거래소를 고르는 파라미터가 없어
"통합 종가로 달라" 고 요청할 방법이 없기 때문이다.

`RankingPrice` 모델이 등락률을 `(lastPrice - basePrice) / basePrice` 로 정의하며,
`changeRate` 는 소수 4자리 소수비율(`0.0382`)이라 앱 표시는 3.82% 가 된다.
우리는 `61,000 / 1,593,000 = 3.8292%` 를 3.83% 로 보여주므로 0.01%p 더 정밀하다.

### 랭킹으로 대조하기

```
GET /api/v1/rankings?type=MARKET_TRADING_AMOUNT&marketCountry=KR&duration=realtime&count=100
```

`RankingType`: `MARKET_TRADING_AMOUNT`, `MARKET_TRADING_VOLUME`, `TOP_GAINERS`,
`TOP_LOSERS`, `TOSS_SECURITIES_TRADING_AMOUNT`, `TOSS_SECURITIES_TRADING_VOLUME`.
`TOP_GAINERS`/`TOP_LOSERS` 는 `basePrice` 가 duration 시작 시점 기준가다.

## 지수 (코스피·코스닥)

| 기능 | 엔드포인트 | 파라미터 |
| --- | --- | --- |
| 지수 현재가 | `GET /api/v1/market-indicators/prices` | `symbols` (쉼표 구분, 최대 200) |
| 지수 일봉 | `GET /api/v1/market-indicators/{symbol}/candles` | `interval` 필수(1m·1d), `count` 최대 200 |

심볼은 `KOSPI`, `KOSDAQ` 문자열이다.

`MarketIndicatorPriceResponse` 는 `symbol`, `timestamp`, `lastPrice` 뿐이다.
종목 시세와 마찬가지로 **등락률·전일 종가를 주지 않는다.**

`MarketIndicatorCandle` 은 종목 캔들과 같은 구조다 — `timestamp`, `openPrice`,
`highPrice`, `lowPrice`, `closePrice`, `volume`.

지수에는 가격제한폭이 없어 기준가를 역산할 수 없다. 전일 종가는 일봉에서 구한다.
지수는 정규장에서 산출되므로 넥스트장 때문에 어긋날 여지도 없다.

## 오류

일반 엔드포인트:

```json
{ "error": { "requestId": "...", "code": "...", "message": "...", "data": {} } }
```

OAuth 엔드포인트는 표준 형식이라 `error` 가 문자열이다:

```json
{ "error": "invalid_client", "error_description": "..." }
```

`client._raise_for_error()` 가 두 형태를 모두 처리한다.

## Rate limit

| 그룹 | 제한 | 비고 |
| --- | --- | --- |
| AUTH | 5 req/s | 토큰 캐싱 필수 |
| ORDER | 10 req/s | 09:00–09:10 KST 동일 |
| ORDER_INFO | 6 req/s | 09:00–09:10 KST 3 req/s 로 축소 |
| MARKET_DATA_CHART | 20 req/s | |

응답 헤더에 `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`.

## 환경

**샌드박스·모의투자 환경이 없다.** 운영 환경 하나뿐이고, 모든 호출이 실계좌에
적용된다. 이 워크플로우가 조회 전용인 이유다.

## 구현하지 않는 것

- `POST /api/v1/orders` 및 정정·취소
- `/api/v1/conditional-orders` 계열

자세한 이유는 `CLAUDE.md` 참고.
