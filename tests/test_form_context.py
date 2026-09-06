import copy

from services.form_context import ATTACHMENT_OPTIONS, build_evidence_from_case, build_form_context


def _full_evidence():
    """모든 필드가 확인된 evidence 표본."""
    return {
        "issuer": {
            "name": {"value": "행복카드", "source": "user"},
            "dept": {"value": "할부항변센터", "source": "user"},
        },
        "merchant": {
            "name": {"value": "올데이 피트니스", "source": "ocr"},
            "bizNo": {"value": "123-45-67890", "source": "ocr"},
            "address": {"value": "서울시 강남구 테헤란로 1", "source": "ocr"},
        },
        "applicant": {
            "name": {"value": "홍길동", "source": "user"},
            "birth": {"value": "1990-01-01", "source": "user"},
            "address": {"value": "서울시 마포구 월드컵로 2", "source": "user"},
            "phone": {"value": "010-1234-5678", "source": "user"},
            "cardNoMasked": {"value": "1234-56**-****-7890", "source": "user"},
            "agentName": {"value": "김대리", "source": "user"},
        },
        "transaction": {
            "date": {"value": "2026-03-02", "source": "ocr"},
            "merchantName": {"value": "올데이 피트니스", "source": "ocr"},
            "category": {"value": "헬스장", "source": "user"},
            "itemName": {"value": "12개월 정기 회원권", "source": "ocr"},
            "amount": {"value": 1200000, "source": "ocr"},
            "installmentMonths": {"value": 12, "source": "ocr"},
            "paidAmount": {"value": 500000, "source": "ocr"},
            "remainingAmount": {"value": 700000, "source": "ocr"},
            "remainingMonths": {"value": 7, "source": "ocr"},
            "billingDay": {"value": 15, "source": "user"},
            "channel": {"value": "신용카드", "source": "user"},
        },
        "reasonTypes": {"value": ["서비스중단", "환불거부"], "source": "user"},
        "timeline": {
            "contractDate": {"value": "2026-03-02", "source": "ocr"},
            "serviceStartDate": {"value": "2026-03-02", "source": "ocr"},
            "serviceStopDate": {"value": "2026-08-10", "source": "ocr"},
            "merchantNoticeDate": {"value": "2026-08-10", "source": "ocr"},
            "refundRequestDate": {"value": "2026-08-11", "source": "user"},
            "merchantResponse": {"value": "환불 거부", "source": "user"},
        },
        "attachments": {
            "value": ["이용계약서", "환불 요청 문자"],
            "source": "user",
        },
    }


def test_build_form_context_all_verified():
    context = build_form_context(_full_evidence())

    assert context["issuer.name"] == "행복카드"
    assert context["merchant.bizNo"] == "123-45-67890"
    assert context["applicant.birth"] == "1990.01.01"
    assert context["transaction.date"] == "2026.03.02"
    assert context["transaction.amount"] == "1,200,000"
    assert context["transaction.paidAmount"] == "500,000"
    assert context["transaction.remainingAmount"] == "700,000"
    assert context["transaction.installmentMonths"] == 12
    assert context["reasonTypes"] == ["서비스중단", "환불거부"]
    assert context["attachments"] == ["이용계약서", "환불 요청 문자"]
    assert context["unverifiedFields"] == []

    assert context["statement"] == [
        "2026.03.02에 올데이 피트니스에서 1,200,000원(12개월 할부) 조건으로 계약을 체결하였습니다.",
        "2026.03.02부터 서비스 이용을 시작하였습니다.",
        "2026.08.10에 서비스가 중단되었습니다(실제 이용 기간 약 5개월).",
        "2026.08.10에 가맹점으로부터 중단 안내를 받았습니다.",
        "2026.08.11에 가맹점에 환불을 요청하였습니다.",
        "가맹점의 답변은 다음과 같습니다: 환불 거부.",
        "미도래 7회 잔여 할부금 700,000원에 대해 납부 거절을 신청합니다.",
    ]


def test_build_form_context_with_unverified_fields():
    evidence = copy.deepcopy(_full_evidence())
    evidence["merchant"]["bizNo"] = {"value": None, "source": "unverified"}
    evidence["applicant"]["agentName"] = {"value": None, "source": "unverified"}
    evidence["timeline"]["merchantNoticeDate"] = {"value": None, "source": "unverified"}

    context = build_form_context(evidence)

    assert context["merchant.bizNo"] == ""
    assert context["applicant.agentName"] == ""
    assert context["timeline.merchantNoticeDate"] == ""
    assert set(context["unverifiedFields"]) == {
        "merchant.bizNo",
        "applicant.agentName",
        "timeline.merchantNoticeDate",
    }

    # 다른 필드는 그대로 채워진다.
    assert context["merchant.name"] == "올데이 피트니스"
    assert context["applicant.name"] == "홍길동"

    # unverified인 중단 안내일은 문장에서 빠지고 나머지 순서는 그대로 유지된다.
    assert context["statement"] == [
        "2026.03.02에 올데이 피트니스에서 1,200,000원(12개월 할부) 조건으로 계약을 체결하였습니다.",
        "2026.03.02부터 서비스 이용을 시작하였습니다.",
        "2026.08.10에 서비스가 중단되었습니다(실제 이용 기간 약 5개월).",
        "2026.08.11에 가맹점에 환불을 요청하였습니다.",
        "가맹점의 답변은 다음과 같습니다: 환불 거부.",
        "미도래 7회 잔여 할부금 700,000원에 대해 납부 거절을 신청합니다.",
    ]


def test_build_form_context_with_missing_and_fallback_fields():
    """OCR 실패로 값이 아예 없거나 evidence에 경로 자체가 빠진, 폴백이 섞인 경우."""
    evidence = copy.deepcopy(_full_evidence())

    # OCR 인식 실패로 값 없이 unverified만 내려온 경우.
    evidence["merchant"]["address"] = {"value": "", "source": "unverified"}

    # 이 문서에서는 해당 항목 자체가 추출되지 않아 경로가 아예 없는 경우.
    del evidence["timeline"]["merchantResponse"]
    del evidence["applicant"]["agentName"]

    # attachments도 아직 첨부가 없어 통째로 빠진 경우.
    del evidence["attachments"]

    context = build_form_context(evidence)

    assert context["merchant.address"] == ""
    assert context["applicant.agentName"] == ""
    assert context["timeline.merchantResponse"] == ""
    assert context["attachments"] == []
    assert set(context["unverifiedFields"]) >= {
        "merchant.address",
        "applicant.agentName",
        "timeline.merchantResponse",
        "attachments",
    }

    # 값이 있는 필드는 여전히 정상적으로 채워진다.
    assert context["transaction.amount"] == "1,200,000"
    assert context["reasonTypes"] == ["서비스중단", "환불거부"]

    # merchantResponse가 없어도 날짜 기반 문장은 그대로 만들어지고,
    # 응답 문장만 빠진다.
    assert context["statement"] == [
        "2026.03.02에 올데이 피트니스에서 1,200,000원(12개월 할부) 조건으로 계약을 체결하였습니다.",
        "2026.03.02부터 서비스 이용을 시작하였습니다.",
        "2026.08.10에 서비스가 중단되었습니다(실제 이용 기간 약 5개월).",
        "2026.08.10에 가맹점으로부터 중단 안내를 받았습니다.",
        "2026.08.11에 가맹점에 환불을 요청하였습니다.",
        "미도래 7회 잔여 할부금 700,000원에 대해 납부 거절을 신청합니다.",
    ]


def _closed_merchant_case():
    return {
        "case_id": "CASE-001",
        "merchant_name": "올데이 피트니스",
        "merchant_category": "헬스장/피트니스",
        "amount": 1200000,
        "installment_months": 12,
        "remaining_installments": 7,
        "remaining_balance": 700000,
        "business_number": "000-00-00003",
        "purchase_date": "2026-03-02",
        "merchant_status": "closed",
        "closed_date": "2026-08-10",
        "service_discontinued": True,
        "replacement_service_offered": False,
    }


def test_build_evidence_from_case_derives_reason_types_from_confirmed_status():
    evidence = build_evidence_from_case(_closed_merchant_case(), documents=None)
    context = build_form_context(evidence)

    assert context["reasonTypes"] == ["부도/폐업/연락불가", "서비스 미제공"]
    assert "reasonTypes" not in context["unverifiedFields"]
    assert context["merchant.bizNo"] == "000-00-00003"
    assert "대체 지점 이용 안내를 받지 못했습니다." in context["statement"]
    assert context["statement"][-1] == (
        "미도래 7회 잔여 할부금 700,000원에 대해 납부 거절을 신청합니다."
    )


def test_build_form_context_appends_extra_note_before_claim():
    context = build_form_context(
        _full_evidence(),
        extra_note="매니저가 환불은 본사에서만 가능하다고 했습니다.\n내용증명은 아직 보내지 못했습니다.",
    )

    assert context["statement"][-3] == "매니저가 환불은 본사에서만 가능하다고 했습니다."
    assert context["statement"][-2] == "내용증명은 아직 보내지 못했습니다."
    assert context["statement"][-1] == (
        "미도래 7회 잔여 할부금 700,000원에 대해 납부 거절을 신청합니다."
    )


def test_build_form_context_ignores_blank_extra_note():
    context = build_form_context(_full_evidence(), extra_note="   \n  ")
    assert context["statement"][-1] == (
        "미도래 7회 잔여 할부금 700,000원에 대해 납부 거절을 신청합니다."
    )
    assert all("본사" not in line for line in context["statement"])


def test_build_form_context_appends_followup_answers_before_extra_note():
    context = build_form_context(
        _full_evidence(),
        followup_answers={
            "answers": [
                {"question": "환불·양도를 받지 못했습니까?", "answer": "yes"},
                {"question": "중단 이후 이용하지 못했습니까?", "answer": "no"},
                {"question": "내용증명을 보냈습니까?", "answer": "unknown"},
                {"question": "빈 질문", "answer": "maybe"},
            ],
            "extra_note": "매니저가 환불은 본사에서만 가능하다고 했습니다.",
        },
    )

    assert "환불·양도를 받지 못했습니까?: 예" in context["statement"]
    assert "중단 이후 이용하지 못했습니까?: 아니오" in context["statement"]
    assert "내용증명을 보냈습니까?: 모르겠음" in context["statement"]
    assert "빈 질문: maybe" not in context["statement"]
    assert context["statement"][-2] == "매니저가 환불은 본사에서만 가능하다고 했습니다."
    assert context["statement"][-1] == (
        "미도래 7회 잔여 할부금 700,000원에 대해 납부 거절을 신청합니다."
    )


def test_build_evidence_from_case_includes_used_after_closure_when_confirmed():
    case = _closed_merchant_case()
    case["service_used_after_closure"] = False

    evidence = build_evidence_from_case(case, documents=None)
    context = build_form_context(evidence)

    assert "가맹점 중단 이후로는 서비스를 이용하지 못했습니다." in context["statement"]


def test_build_evidence_from_case_does_not_guess_reason_when_merchant_is_open():
    case = _closed_merchant_case()
    case["merchant_status"] = "active"
    case["service_discontinued"] = False

    evidence = build_evidence_from_case(case, documents=None)
    context = build_form_context(evidence)

    assert context["reasonTypes"] == []
    assert "reasonTypes" in context["unverifiedFields"]


def test_build_evidence_from_case_normalizes_document_labels_to_checkbox_wording():
    documents = [
        {"label": "이용계약서"},
        {"label": "환불 요청 문자"},
        {"label": "손글씨 메모"},
    ]
    evidence = build_evidence_from_case(_closed_merchant_case(), documents=documents)
    context = build_form_context(evidence)

    assert "이용계약서 사본" in context["attachments"]
    assert "환불 요청 기록" in context["attachments"]
    assert "손글씨 메모" in context["attachments"]
    # 정규화된 값은 실제 서식 체크박스 문구와 정확히 일치해야 체크(■)된다.
    assert set(context["attachments"]) & set(ATTACHMENT_OPTIONS) == {
        "이용계약서 사본",
        "환불 요청 기록",
    }
