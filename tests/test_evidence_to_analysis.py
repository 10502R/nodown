# B→C 연동: B가 세션에 쌓은 증빙(routes/evidence.py)이 C-1 AI 입력 형식
# {"case", "documents", "extractedFields", "rawTexts"}으로 조립되는지 확인한다.
# llm_service.py의 실제 OpenAI 호출 분기는 API 키가 있어야 타므로, 여기서는
# 입력 조립 로직(ocr_service.to_ai_input, llm_service._build_evidence_context)과
# 라우트가 세션 증빙을 실제로 넘기는지까지만 검증한다.

import json

from app import create_app
from services import llm_service, ocr_service

_DOCUMENTS = [
    {
        "id": 1,
        "label": "이용계약서",
        "source_type": "sample",
        "filename": "contract.pdf",
        "ocr_status": "sample",
        "raw_text": "헬스장 이용계약서\n계약일: 2026.03.02\n계약금액: 1,200,000원",
        "fields": ocr_service.extract_fields("계약일: 2026.03.02\n계약금액: 1,200,000원"),
    },
    {
        "id": 2,
        "label": "환불 요청 문자",
        "source_type": "manual",
        "filename": None,
        "ocr_status": "manual",
        "raw_text": "환불 요청일: 2026.08.11",
        "fields": ocr_service.extract_fields("환불 요청일: 2026.08.11"),
    },
]


def test_to_ai_input_builds_c1_document_and_field_shape():
    ai_input = ocr_service.to_ai_input(_DOCUMENTS)

    assert ai_input["documents"][0]["documentId"] == "DOC-001"
    assert ai_input["documents"][0]["type"] == "contract"
    assert ai_input["documents"][0]["isSynthetic"] is True
    assert ai_input["documents"][1]["type"] == "sms"
    assert ai_input["documents"][1]["isSynthetic"] is False

    assert ai_input["extractedFields"]["contractAmount"] == 1_200_000
    assert ai_input["extractedFields"]["refundRequestDate"] == "2026-08-11"
    assert len(ai_input["rawTexts"]) == 2


def test_build_evidence_context_uses_real_evidence_when_present():
    case = {"case_id": "CASE-001", "merchant_name": "올데이 피트니스"}
    context = llm_service._build_evidence_context(case, _DOCUMENTS)

    payload = json.loads(context)
    assert payload["case"]["case_id"] == "CASE-001"
    assert payload["documents"][0]["label"] == "이용계약서"
    assert payload["extractedFields"]["contractAmount"] == 1_200_000


def test_build_evidence_context_falls_back_to_static_fixture_without_evidence():
    """B의 자료가 없는 사례는 기존 동작(정적 예시 입력)을 그대로 유지한다."""
    context = llm_service._build_evidence_context(None, None)
    assert context  # 빈 문자열이 아니어야 함(파일이 없을 때만 빈 문자열)


def test_analysis_route_accepts_real_case_and_session_evidence_without_error():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()

    client.post(
        "/evidence/CASE-001/sample", data={"sample_key": "contract"}, follow_redirects=True
    )

    response = client.get("/analysis/CASE-001")
    assert response.status_code == 200
    assert "올데이 피트니스" in response.get_data(as_text=True)
