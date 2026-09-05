# 증빙 데이터 스키마 (신청서 자동 작성용)

`services/form_context.py`가 입력으로 받는 evidence JSON의 구조를 정의한다.
이 스키마는 할부항변 신청서 서식을 자동으로 채우기 위한 것으로, B가 문서별로
쌓는 원본 evidence 세션 구조(`docs/B_담당_구현지침.md`의 `contractDate`,
`fields` 등)와는 별개다. 여러 문서·입력에서 모인 값을 신청서 항목 단위로
한 번 더 정리한 상위 계층 데이터라고 보면 된다.

## 필드 래퍼 형식

가장 안쪽 필드는 항상 다음 형태의 객체다.

```json
{"value": "<실제 값>", "source": "ocr" | "user" | "unverified"}
```

- `ocr`: CLOVA OCR로 추출된 값
- `user`: 사용자가 화면에서 직접 입력하거나 선택한 값
- `unverified`: 어떤 증빙으로도 확인되지 않은 값. `value`는 `null`이거나
  비어 있어도 되며, 어차피 신청서 컨텍스트에서는 무시된다.

경로가 아예 없거나 형식이 어긋난 필드도 `unverified`와 동일하게 취급한다
(값을 추측해서 채우지 않는다).

## 최상위 구조

```json
{
  "issuer": {
    "name": {"value": "...", "source": "user"},
    "dept": {"value": "...", "source": "user"}
  },
  "merchant": {
    "name": {"value": "...", "source": "ocr"},
    "bizNo": {"value": "...", "source": "unverified"},
    "address": {"value": "...", "source": "ocr"}
  },
  "applicant": {
    "name": {"value": "...", "source": "user"},
    "birth": {"value": "1990-01-01", "source": "user"},
    "address": {"value": "...", "source": "user"},
    "phone": {"value": "...", "source": "user"},
    "cardNoMasked": {"value": "...", "source": "user"},
    "agentName": {"value": "...", "source": "unverified"}
  },
  "transaction": {
    "date": {"value": "2026-03-02", "source": "ocr"},
    "merchantName": {"value": "...", "source": "ocr"},
    "category": {"value": "...", "source": "user"},
    "itemName": {"value": "...", "source": "ocr"},
    "amount": {"value": 1200000, "source": "ocr"},
    "installmentMonths": {"value": 12, "source": "ocr"},
    "paidAmount": {"value": 500000, "source": "ocr"},
    "remainingAmount": {"value": 700000, "source": "ocr"},
    "remainingMonths": {"value": 7, "source": "ocr"},
    "billingDay": {"value": 15, "source": "user"},
    "channel": {"value": "신용카드", "source": "user"}
  },
  "reasonTypes": {"value": ["서비스중단", "환불거부"], "source": "user"},
  "timeline": {
    "contractDate": {"value": "2026-03-02", "source": "ocr"},
    "serviceStartDate": {"value": "2026-03-02", "source": "ocr"},
    "serviceStopDate": {"value": "2026-08-10", "source": "ocr"},
    "merchantNoticeDate": {"value": "2026-08-10", "source": "ocr"},
    "refundRequestDate": {"value": "2026-08-11", "source": "user"},
    "merchantResponse": {"value": "환불 거부", "source": "user"}
  },
  "attachments": {"value": ["이용계약서", "환불 요청 문자"], "source": "user"}
}
```

`reasonTypes`, `attachments`는 각각 배열 값 전체를 하나의 필드로 감싼다
(배열 안 원소마다 개별 source를 두지 않는다).

`statement`(시간순 서술)에 "대체 지점 이용 안내를 받았는지"와 "가맹점 중단
이후 본인이 서비스를 이용했는지" 두 줄을 더하려면 다음 필드를 추가로 넣을 수
있다(둘 다 선택 항목, 없으면 그 문장만 빠진다).

```json
"situation": {
  "replacementServiceOffered": {"value": false, "source": "user"},
  "usedAfterClosure": {"value": false, "source": "user"}
}
```

날짜 값(`applicant.birth`, `transaction.date`, `timeline.*Date`)은 항상
`YYYY-MM-DD` ISO 형식 문자열로 넣는다. `form_context.py`가 서식용
`YYYY.MM.DD` 표기로 변환한다.

## form_context.py가 만드는 출력과의 대응

입력의 각 필드는 출력 컨텍스트의 같은 이름 키로 그대로 대응한다
(`issuer.name` → `issuer.name`, `transaction.amount` → `transaction.amount` 등).
다음 두 가지만 입력에 직접 대응하는 키가 없는 파생 값이다.

- `statement`: 본인 사용 여부, 계약 체결일, 서비스 시행일, 가맹점 해지
  통보일, 가맹점과의 분쟁 내용(환불 요청 경과와 회신) 등을 시간순 설명체
  문장(예: "...계약을 체결하였습니다.")으로 종합한 배열이다(4번 항목
  서술란의 안내 문구를 그대로 따른다). `timeline`의 날짜와
  `transaction.merchantName` / `amount` / `installmentMonths`,
  `situation.usedAfterClosure`, `situation.replacementServiceOffered`를
  사용해 만든다. `unverified`이거나 값이 없는 항목은 해당 문장만 빼며,
  추측으로 채우지 않는다.
- `unverifiedFields`: 이번 변환에서 `unverified`로 판정되어 빈 문자열/빈
  배열로 대체된 출력 키 이름 목록.

## 규칙 요약

- `source`가 `"unverified"`인 값은 출력 컨텍스트에서 빈 문자열(배열 필드는
  빈 배열)로 바뀌고, 해당 출력 키 이름이 `unverifiedFields`에 들어간다.
- 없는 필드·경로도 `unverified`와 동일하게 처리한다.
- 금액(`transaction.amount`, `transaction.paidAmount`,
  `transaction.remainingAmount`)은 콤마 포함 문자열로 포맷한다(`"1,200,000"`).
- 날짜는 `YYYY.MM.DD`로 포맷한다.
- `form_context.py`는 LLM을 호출하지 않고, 이미 모인 값을 서식 자리에
  배치만 하는 순수 함수다. 디스크에 파일을 쓰지 않는다.
- `reasonTypes`, `attachments`의 값이 신청서 체크박스 문구와 글자가 완전히
  같아야 그 칸이 ■로 표시된다(`templates/submission_form.html`이 문자열을
  그대로 비교한다). 다른 표현으로 들어오면 서식의 "기타" 칸에 원문 그대로
  들어간다. `services/form_context.py::build_evidence_from_case`는 A의
  사례·B의 증빙 문서에서 evidence를 만들 때 이 문구 맞추기
  (`normalize_to_options`, 신청 사유는 확인된 사례 상태에서만 고르기)를
  대신 해 준다.
