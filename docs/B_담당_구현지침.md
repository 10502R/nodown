# B 담당 구현 지침

> 이 문서는 금융 AI Challenge의 B 담당 범위와 현재 `nodown` 저장소에서의 완료 기준을 고정하기 위한 작업 지침이다.

## 1. B의 최종 책임 범위

B는 다음 흐름을 코드·화면·테스트까지 완료한다.

```text
사례 상세(A로부터 case_id 전달받음)
→ 소비자 실제 서비스 중단 여부 확인
→ 계약서·문자·이용기록 파일 업로드
→ CLOVA OCR 호출 및 텍스트 추출
→ 핵심정보 구조화(계약일·금액·기간 등)
→ 추출 결과를 C(분석 단계)로 전달
```

담당 파일은 다음과 같다.

| 영역 | 파일 |
| --- | --- |
| 소비자 상황 확인·업로드 라우트 | `routes/evidence.py` |
| OCR 연동·정보 추출 | `services/ocr_service.py` |
| 합성 예시 문서 | `data/fallback_evidence.json` |
| 자료 확인/업로드 화면 | `templates/case_confirm.html`, `templates/evidence.html` |
| 업로드·비동기 처리 | `static/js/evidence.js` |
| 테스트 | `tests/test_ocr_service.py`, `tests/test_evidence.py` |

`app.py`, `requirements.txt`, A·C 담당 서비스는 상의 없이 변경하지 않는다. A가 만든 `case_id`, `transaction_id`, `merchant_status`, `remaining_balance` 필드명은 그대로 사용한다.

## 2. MVP 처리 기준

소비자 상황 확인은 4가지 선택지 중 하나로 응답받는다.

- 폐업 또는 서비스 중단으로 더 이상 이용하지 못하고 있음 → 자료 업로드 단계로 진행
- 이미 환불받았음 → 안내 종료
- 다른 지점이나 대체 수단으로 정상 이용 중임 → 안내 종료
- 아직 정확히 모르겠음 → 자료 업로드 단계로 진행

파일 업로드는 다음 조건을 지킨다.

- 파일당 약 3MB 이하
- 한 번에 하나씩 업로드
- 이미지 압축 적용
- 실제 개인정보가 포함된 문서를 올리지 말라는 안내문을 화면에 표시
- 합성 예시 계약서·대화 자료를 기본 제공하고, 사용자가 일부 수정하거나 자신의 테스트 파일을 추가 가능

OCR 실패 또는 API 미연결 시에는 `data/fallback_evidence.json`의 합성 응답으로 대체하고, 화면에 데이터 출처(`실제 OCR·AI 분석 결과` / `공공 API 명세 기반 합성 응답`)를 구분 표시한다.

## 3. 핵심정보 추출 항목

`services/ocr_service.py`는 OCR과 문서 구조 분석을 통해 다음 항목을 추출한다.

- 계약일 (`contract_date`)
- 계약금액 (`contract_amount`)
- 서비스 이용기간 (`service_period`)
- 할부기간 (`installment_months`)
- 이용한 기간 (`used_period_months`)
- 남은 기간 (`remaining_period_months`)
- 환불 요청일 (`refund_request_date`)
- 서비스 중단일 (`service_stop_date`)
- 대체 서비스 제안 여부 (`alternative_service_offered`)

추출 실패 항목은 `null`로 두고 임의로 채우지 않는다. `null` 항목은 이후 C 단계의 "부족한 증빙 탐지"에서 사용되므로 값을 추측해 채우면 안 된다.

## 4. API 계약

### 소비자 상황 확인

```text
POST /evidence/<case_id>/status
Content-Type: application/json
```

요청:

```json
{
  "situation": "service_unavailable"
}
```

`situation` 값은 `service_unavailable`, `refunded`, `alternative_in_use`, `unknown` 중 하나만 허용한다. `refunded`, `alternative_in_use`는 다음 단계로 진행하지 않고 종료 응답을 반환한다.

응답:

```json
{
  "caseId": "CASE-001",
  "nextStep": "upload",
  "isSynthetic": false
}
```

### 파일 업로드 및 OCR 추출

```text
POST /evidence/<case_id>/upload
Content-Type: multipart/form-data
```

응답:

```json
{
  "caseId": "CASE-001",
  "evidence": {
    "contract_date": "2026-03-02",
    "contract_amount": 1200000,
    "service_period": "12개월",
    "installment_months": 12,
    "used_period_months": 5,
    "remaining_period_months": 7,
    "refund_request_date": "2026-08-11",
    "service_stop_date": "2026-08-10",
    "alternative_service_offered": false
  },
  "source": "실제 OCR·AI 분석 결과",
  "isSynthetic": false
}
```

업로드 파일이 3MB를 초과하거나 형식이 지원되지 않으면 HTTP 400과 사유를 반환한다. OCR 호출이 실패하면 `fallback_evidence.json` 값으로 대체하고 `source`를 `"공공 API 명세 기반 합성 응답"`으로 표시한다.

## 5. 이번 주 실행 순서

현재 날짜가 2026-08-29이므로, B의 코드·문서 MVP는 8월 29~30일에 완료하고 8월 30~31일에 교차 실행, 9월 1일에 A·C·D와 통합하는 일정으로 잡는다.

### 8월 29일

- 이 지침과 A의 API 계약(`case_id`, `caseUrl`) 확인
- 담당 브랜치에서 B 파일만 수정
- 합성 예시 계약서·대화 자료 확정, `fallback_evidence.json` 작성

### 8월 30일

- 소비자 상황 확인 라우트 구현
- CLOVA OCR 연동, 실패 시 fallback 처리 구현
- 핵심정보 추출 결과를 evidence 화면에서 확인
- 단위 테스트 작성

### 8월 31일

- 팀원 한 명이 설치부터 화면까지 직접 실행
- 환불받음·정상 이용 중·중단 확인 안 됨·중단됨 사례를 각각 확인
- 3MB 초과 파일, OCR 실패 상황도 확인
- 실행 방법, 테스트 결과, 화면 캡처 위치 기록

### 9월 1일

- C의 분석 단계로 넘어갈 evidence JSON 스키마 확정
- sessionStorage를 통한 화면 간 데이터 전달 확인
- 대표 사례가 analysis 단계로 정상 진입하는지 통합 테스트

## 6. B 완료 체크리스트

- [ ] 소비자 상황 확인 4가지 분기가 모두 동작한다.
- [ ] 환불받음·정상 이용 중 응답 시 다음 단계로 진행되지 않는다.
- [ ] 파일 업로드가 3MB 제한, 1건씩 업로드 조건을 지킨다.
- [ ] 실제 개인정보 업로드 금지 안내문이 화면에 표시된다.
- [ ] OCR 추출 결과가 9개 핵심정보 항목을 모두 포함한다(실패 시 `null`).
- [ ] OCR 실패 시 fallback 데이터로 정상 대체된다.
- [ ] 데이터 출처(`isSynthetic`, `source`)가 화면에 표시된다.
- [ ] evidence 데이터가 서버 디스크에 파일로 남지 않는다.
- [ ] 테스트가 통과한다.
- [ ] 대표 화면을 팀원 한 명이 직접 실행했다.

## 7. 팀원에게 넘길 때 같이 전달할 것

```text
대표 사례: CASE-001
상황 확인 API: POST /evidence/CASE-001/status {"situation":"service_unavailable"}
업로드 API: POST /evidence/CASE-001/upload (multipart/form-data)
evidence 스키마: contract_date, contract_amount, service_period,
                 installment_months, used_period_months, remaining_period_months,
                 refund_request_date, service_stop_date, alternative_service_offered
```

다음 담당자(C)는 B의 evidence 필드명을 임의로 바꾸지 않는다. 변경이 필요하면 팀에 알린다.