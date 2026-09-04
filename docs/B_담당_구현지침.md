# B 담당 구현 지침

> 이 문서는 금융 AI Challenge의 B 담당 범위와 현재 `nodown` 저장소에서의 완료 기준을 고정하기 위한 작업 지침이다.

## 1. B의 최종 책임 범위

B는 다음 흐름을 코드, 화면, 테스트까지 완료한다.

```text
사례 상세(A로부터 case_id 전달받음)
→ (D 담당) 소비자 실제 서비스 중단 여부 확인
→ 계약서, 문자, 이용기록 파일 업로드
→ CLOVA OCR 호출 및 텍스트 추출
→ 핵심정보 구조화(계약일, 금액, 기간 등)
→ 추출 결과를 C(분석 단계)로 전달
```

소비자 상황 확인 화면(`/case/<case_id>`, `templates/case_confirm.html`)은 실제로는 D 담당 `routes/result.py`가 구현했다. B는 그 화면에서 자료 입력 단계로 넘어온 이후, 즉 파일 업로드부터 담당한다.

담당 파일은 다음과 같다.

| 영역 | 파일 |
| --- | --- |
| 자료 입력 라우트(업로드, 직접입력, 예시문서) | `routes/evidence.py` |
| OCR 연동, 정보 추출 | `services/ocr_service.py` |
| 실제 합성 예시 문서(PDF, 이미지) | `data/sample_evidence/contract.pdf`, `refund_sms.png`, `closure_notice.png` |
| 자료 입력 화면 | `templates/evidence.html` |
| 테스트 | `tests/test_ocr_service.py`, `tests/test_evidence.py`, `tests/test_evidence_case_integration.py`, `tests/test_evidence_to_analysis.py` |

자료 입력 화면은 별도 JS 파일 없이 서버 렌더링(폼 제출 → 리다이렉트) 방식으로 동작한다.

`app.py`, `requirements.txt`, A, C 담당 서비스는 상의 없이 변경하지 않는다. A가 만든 `case_id`, `transaction_id`, `merchant_status`, `remaining_balance` 필드명은 그대로 사용한다.

## 2. MVP 처리 기준

소비자 상황 확인(D 담당 화면)은 4가지 선택지 중 하나로 응답받는다.

- 더 이상 서비스를 이용하지 못하고 있음(`unusable`) → 자료 입력 단계로 진행
- 이미 환불받았음(`refunded`) → 안내 종료
- 다른 지점에서 정상 이용 중임(`normal_use`) → 안내 종료
- 아직 정확히 모르겠음(`unknown`) → 자료 입력 단계로 진행

파일 업로드는 다음 조건을 지킨다.

- 파일당 10MB 이하(`ocr_service.MAX_FILE_SIZE_BYTES`)
- 한 번에 하나씩 업로드
- 허용 확장자는 pdf, png, jpg, jpeg
- 실제 개인정보가 포함된 문서를 올리지 말라는 안내문을 화면에 상시 표시
- 합성 예시 계약서, 환불 문자, 중단 안내문을 실제 파일(`data/sample_evidence/`)로 기본 제공하고, 사용자가 직접 파일을 업로드하거나 텍스트를 입력해 추가할 수 있음

OCR 키가 없거나(`not_configured`) 호출이 실패하면(`failed`), 예시문서 3종에 한해서만 우리가 이미 알고 있는 텍스트로 대체한다(다른 사용자가 올린 파일에는 임의로 값을 채우지 않는다). 이 경우 화면에는 오류 문구를 띄우고 문자 내용을 직접 입력하도록 안내한다. 데이터 출처는 실제 OCR 결과(`ocr_service.SOURCE_OCR`) / 실제 사용자 입력(`SOURCE_USER_INPUT`) / 예비 데이터(`SOURCE_FIXTURE`)로 구분해 화면에 표시한다.

## 3. 핵심정보 추출 항목

`services/ocr_service.py`는 OCR과 문서 구조 분석을 통해 다음 항목을 추출한다.

- 계약일 (`contractDate`)
- 계약금액 (`contractAmount`)
- 서비스 시작일 (`serviceStartDate`)
- 서비스 종료일 (`serviceEndDate`)
- 환불 요청일 (`refundRequestDate`)
- 서비스 중단일 (`serviceStopDate`)
- 대체 서비스 제공 여부 (`replacementServiceOffered`)

추출 실패 항목은 `null`로 두고 임의로 채우지 않는다. `null` 항목은 이후 C 단계의 "부족한 증빙 탐지"에서 사용되므로 값을 추측해 채우면 안 된다.

할부기간, 이용한 기간, 남은 기간은 OCR로 다시 추출하지 않는다. A가 만든 사례 데이터(`installment_months`, `remaining_installments` 등)에 이미 있는 값을 그대로 쓴다.

## 4. 실제 라우트

JSON API가 아니라 서버 렌더링 폼(HTML `<form>` 제출 → 302 리다이렉트) 구조다. 실패도 HTTP 상태 코드가 아니라 리다이렉트 후 쿼리 파라미터(`error=...`)와 화면 문구로 전달한다.

### 소비자 상황 확인 (D 담당, 참고용)

```text
GET  /case/<case_id>
POST /case/<case_id>/situation
Content-Type: application/x-www-form-urlencoded
```

요청 폼 필드: `situation` — `unusable` | `refunded` | `normal_use` | `unknown` 중 하나. `refunded`, `normal_use`는 안내 종료 화면(`/case/<case_id>/guidance`)으로, 나머지 두 값은 자료 입력 화면(`/evidence/<case_id>`)으로 리다이렉트한다.

### 자료 입력 (B 담당)

```text
GET  /evidence/<case_id>
POST /evidence/<case_id>/upload            (multipart/form-data — file, label)
POST /evidence/<case_id>/manual            (text, label)
POST /evidence/<case_id>/sample            (sample_key)
POST /evidence/<case_id>/delete/<doc_id>
GET  /evidence/sample/<key>/download
```

`upload`, `manual`, `sample`, `delete`는 모두 처리 후 `/evidence/<case_id>`로 리다이렉트한다. 세션에 쌓이는 문서 하나는 다음 구조다.

```json
{
  "id": 1,
  "label": "이용계약서",
  "source_type": "upload",
  "filename": "contract.pdf",
  "ocr_status": "ok",
  "raw_text": "헬스장 이용계약서\n계약일 2026.03.02\n...",
  "fields": {
    "contractDate": "2026-03-02",
    "contractAmount": 1200000,
    "serviceStartDate": "2026-03-02",
    "serviceEndDate": null,
    "refundRequestDate": null,
    "serviceStopDate": null,
    "replacementServiceOffered": null
  }
}
```

- `source_type`: `upload`(실제 업로드) | `manual`(직접 입력) | `sample`(예시문서)
- `ocr_status`: `ok` | `not_configured`(OCR 키 미설정) | `failed`(호출, 인식 실패) | `manual` | `sample`

업로드 파일이 10MB를 초과하거나 확장자(pdf/png/jpg/jpeg)가 아니면 등록하지 않고 화면에 오류 문구를 보여준다. OCR 키 미설정이나 호출 실패는 예외를 던지지 않고 문서는 등록하되 상태값으로만 구분하며, 화면에서 문자 내용을 직접 입력하도록 안내한다.

## 5. 실행 순서 (당시 계획, 완료된 기록)

아래는 2026-08-29 시점에 세운 계획이며, OCR 실제 연동까지 포함해 대부분 완료되었다. 기술적으로 부정확했던 부분만 실제 구현에 맞게 고쳤다.

### 8월 29일

- 이 지침과 A의 API 계약(`case_id`, `caseUrl`) 확인
- 담당 브랜치에서 B 파일만 수정
- 합성 예시 계약서, 대화 자료 확정, `data/sample_evidence/`에 실제 PDF, 이미지 파일로 준비

### 8월 30일

- 소비자 상황 확인 라우트 구현(실제로는 D 담당 `routes/result.py`가 구현)
- CLOVA OCR 연동(base64 이미지 + `X-OCR-SECRET` 헤더로 Invoke URL에 POST), 실패 시 예시문서 한정 대체 처리 구현
- 핵심정보 추출 결과를 evidence 화면에서 확인
- 단위 테스트 작성

### 8월 31일

- 팀원 한 명이 설치부터 화면까지 직접 실행
- 환불받음, 정상 이용 중, 중단 확인 안 됨, 중단됨 사례를 각각 확인
- 10MB 초과 파일, OCR 실패 상황도 확인
- 실행 방법, 테스트 결과, 화면 캡처 위치 기록

### 9월 1일

- C의 분석 단계로 넘어갈 evidence JSON 스키마 확정
- Flask 서버 측 세션(브라우저 sessionStorage 아님)을 통한 화면 간 데이터 전달 확인
- 대표 사례가 analysis 단계로 정상 진입하는지 통합 테스트

## 6. B 완료 체크리스트

- [x] 소비자 상황 확인 4가지 분기가 모두 동작한다. (D 담당 화면)
- [x] 환불받음, 정상 이용 중 응답 시 다음 단계로 진행되지 않는다. (D 담당 화면)
- [x] 파일 업로드가 10MB 제한, 1건씩 업로드 조건을 지킨다.
- [x] 실제 개인정보 업로드 금지 안내문이 화면에 표시된다.
- [x] OCR 추출 결과가 7개 핵심정보 항목을 모두 포함한다(실패 시 `null`).
- [x] OCR 실패 시 예시문서 3종에 한해 알려진 텍스트로 대체된다(사용자 업로드는 오류 안내로 처리).
- [x] 데이터 출처(실제 OCR 결과 / 실제 사용자 입력 / 예비 데이터)가 화면에 표시된다.
- [x] evidence 데이터가 서버 디스크에 파일로 남지 않는다(업로드 파일은 메모리 스트림으로 OCR에 바로 전달, 세션에는 추출된 텍스트, 항목만 보관).
- [x] 테스트가 통과한다.
- [x] 실제 CLOVA OCR 키로 예시문서 3종 모두 실제 API 호출까지 확인했다.

## 7. 팀원에게 넘길 때 같이 전달할 것

```text
대표 사례: CASE-001
상황 확인(D 담당): POST /case/CASE-001/situation  (form: situation=unusable)
자료 입력 화면: GET /evidence/CASE-001
업로드: POST /evidence/CASE-001/upload (multipart/form-data: file, label)
evidence 스키마: contractDate, contractAmount, serviceStartDate, serviceEndDate,
                 refundRequestDate, serviceStopDate, replacementServiceOffered
```

다음 담당자(C)는 B의 evidence 필드명을 임의로 바꾸지 않는다. 변경이 필요하면 팀에 알린다