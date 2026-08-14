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
| 매수 가능 금액 | `GET /api/v1/buying-power` | 계좌 헤더 |
| 현재가 | `GET /api/v1/prices` | `symbols` (쉼표 구분, 최대 200) |
| 전종목 마스터 | `GET /api/v1/stocks/all` | `market` 필수, `status` 기본 ACTIVE |

`market` 허용값: `KOSPI`, `KOSDAQ`, `NYSE`, `NASDAQ`, `AMEX`, `KR_ETC`, `US_ETC`.

## 응답 껍데기

인증 엔드포인트를 제외한 모든 응답은 `{"result": ...}` 로 감싸여 온다.
`client.get()` 이 이 껍데기를 벗겨서 반환한다.

금액·수량·수익률은 **문자열**로 온다. (`"lastPrice": "71500"`)

### 확인된 필드

`GET /api/v1/accounts` → `result: []`
`accountSeq`, `accountNumber`, `accountName`, `accountType`, `status`, `currency`

`GET /api/v1/holdings` → `result: {holdings: [], summary: {}}`
holdings 항목: `symbol`, `quantity`, `purchasePrice`, `evaluationPrice`,
`evaluationAmount`, `profitLoss`, `profitLossRate`, `currency`
summary: `totalEvaluationAmount`, `totalPurchaseAmount`, `totalProfitLoss`,
`totalProfitLossRate`

`GET /api/v1/prices` → `result: []`
`symbol`, `timestamp`, `lastPrice`, `currency`

`GET /api/v1/stocks/all` → `result: []`
`symbol`, `name`, `securityType`, `isCommonShare`, `isinCode`

### 미확인 필드

`GET /api/v1/buying-power` — 응답 스키마를 확인하지 못했다. `accounts.py` 가
`amount` 를 가정하고 있으니 첫 실호출 때 실제 응답을 찍어보고 고칠 것.

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
