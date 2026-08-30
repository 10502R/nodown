# C-10: llm_service 8키 검증·contradictions 정규화·픽스처 폴백·시나리오별 mock 응답.
# 실제 OpenAI API는 호출하지 않는다.

import json
from unittest.mock import MagicMock

import pytest

from services import llm_service

_REQUIRED_LIST_KEYS = llm_service._REQUIRED_LIST_KEYS
_REQUIRED_STR_KEY = llm_service._REQUIRED_STR_KEY
_NO_CONTRADICTION = llm_service._NO_CONTRADICTION_TEXT
_SENTINEL_DATE = "2099-01-01"
_FORBIDDEN_DEFINITE_PHRASES = ("환불 확정", "항변권 성립", "항변 인정", "환불 인정")


def _empty_analysis(**overrides):
    """C-2 형식을 만족하는 최소 mock JSON."""
    data = {
        "timeline": [],
        "confirmedFacts": [],
        "userClaims": [],
        "unresolvedItems": [],
        "contradictions": [_NO_CONTRADICTION],
        "missingEvidence": [],
        "followUpQuestions": [],
        "submissionSummary": "요약 초안",
    }
    data.update(overrides)
    return data


def _assert_c2_keys_and_types(result):
    """공통: 8키 존재·타입과 _source 존재."""
    for key in _REQUIRED_LIST_KEYS:
        assert key in result, "missing key: {0}".format(key)
        assert isinstance(result[key], list), "{0} must be list".format(key)
    assert isinstance(result[_REQUIRED_STR_KEY], str)
    assert "_source" in result


def _mock_openai_returning(monkeypatch, payload):
    """chat.completions.create가 payload(JSON dict 또는 raw 문자열)를 돌려주게 한다."""

    class _Message:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.message = _Message(content)

    class _Completions:
        def create(self, **kwargs):
            if isinstance(payload, dict):
                content = json.dumps(payload, ensure_ascii=False)
            else:
                content = payload
            return MagicMock(choices=[_Choice(content)])

    fake_client = MagicMock()
    fake_client.chat.completions = _Completions()
    monkeypatch.setattr(llm_service, "_get_client", lambda: fake_client)
    return fake_client


# --- 단위: 검증 헬퍼 -------------------------------------------------------


def test_is_valid_analysis_shape_rejects_missing_key():
    data = _empty_analysis()
    del data["contradictions"]
    assert llm_service._is_valid_analysis_shape(data) is False


def test_is_valid_analysis_shape_rejects_wrong_submission_summary_type():
    data = _empty_analysis(submissionSummary=["not", "a", "string"])
    assert llm_service._is_valid_analysis_shape(data) is False


def test_normalize_analysis_fills_empty_contradictions():
    data = _empty_analysis(contradictions=[])
    normalized = llm_service._normalize_analysis(data)
    assert normalized["contradictions"] == [_NO_CONTRADICTION]


def test_normalize_analysis_fills_missing_contradictions():
    data = _empty_analysis()
    del data["contradictions"]
    normalized = llm_service._normalize_analysis(data)
    assert normalized["contradictions"] == [_NO_CONTRADICTION]


def test_normalize_analysis_preserves_existing_contradictions():
    data = _empty_analysis(contradictions=["계약기간이 자료마다 다름"])
    normalized = llm_service._normalize_analysis(data)
    assert normalized["contradictions"] == ["계약기간이 자료마다 다름"]


# --- 단위: analyze_case 폴백·성공 경로 (mock) --------------------------------


def test_analyze_case_missing_key_falls_back_to_fixture(monkeypatch):
    invalid = _empty_analysis()
    del invalid["followUpQuestions"]
    _mock_openai_returning(monkeypatch, invalid)

    result = llm_service.analyze_case("CASE-001")

    assert result["_source"] == "fixture"
    _assert_c2_keys_and_types(result)
    assert result["confirmedFacts"]  # analysis-result.fixture.json 내용


def test_analyze_case_wrong_type_falls_back_to_fixture(monkeypatch):
    invalid = _empty_analysis(submissionSummary=["list", "not", "str"])
    _mock_openai_returning(monkeypatch, invalid)

    result = llm_service.analyze_case("CASE-001")

    assert result["_source"] == "fixture"
    _assert_c2_keys_and_types(result)


def test_analyze_case_success_sets_source_ai_and_normalizes_empty_contradictions(monkeypatch):
    valid = _empty_analysis(contradictions=[])
    _mock_openai_returning(monkeypatch, valid)

    result = llm_service.analyze_case("CASE-001", case={"case_id": "CASE-001"})

    assert result["_source"] == "ai"
    _assert_c2_keys_and_types(result)
    assert result["contradictions"] == [_NO_CONTRADICTION]
    assert result["submissionSummary"] == "요약 초안"


def test_analyze_case_no_api_key_returns_fixture_source(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(llm_service, "_client", None)

    result = llm_service.analyze_case("CASE-001")

    assert result["_source"] == "fixture"
    _assert_c2_keys_and_types(result)


# --- C-10 시나리오 (mock JSON을 시나리오별로 다르게) -------------------------


def test_scenario_1_sufficient_evidence(monkeypatch):
    mock = _empty_analysis(
        timeline=[{"date": "2026-03-02", "event": "계약 및 결제", "source": "이용계약서"}],
        confirmedFacts=["계약서상 결제금액 1,200,000원으로 기재되어 있다."],
    )
    _mock_openai_returning(monkeypatch, mock)

    result = llm_service.analyze_case("CASE-SC1", case={"case_id": "CASE-SC1"})

    _assert_c2_keys_and_types(result)
    assert result["_source"] == "ai"
    assert result["timeline"]
    assert result["confirmedFacts"]


def test_scenario_2_no_refund_request_record(monkeypatch):
    mock = _empty_analysis(
        missingEvidence=["환불 요청 문자·메일·통화 기록"],
        confirmedFacts=["서비스 중단 안내문상 2026-08-10 폐업이 기재되어 있다."],
    )
    _mock_openai_returning(monkeypatch, mock)

    result = llm_service.analyze_case("CASE-SC2", case={"case_id": "CASE-SC2"})

    _assert_c2_keys_and_types(result)
    assert result["_source"] == "ai"
    assert any("환불" in item for item in result["missingEvidence"])


def test_scenario_3_already_refunded_no_definitive_phrases_in_confirmed_facts(monkeypatch):
    mock = _empty_analysis(
        confirmedFacts=["카드 명세서에 취소·환불 반영 여부는 자료에서 확인되지 않는다."],
        userClaims=["이미 환불받았다고 설명한다."],
        unresolvedItems=["실제 카드 취소 내역 확인 필요"],
    )
    _mock_openai_returning(monkeypatch, mock)

    result = llm_service.analyze_case("CASE-SC3", case={"case_id": "CASE-SC3"})

    _assert_c2_keys_and_types(result)
    assert result["_source"] == "ai"
    joined = " ".join(result["confirmedFacts"])
    for phrase in _FORBIDDEN_DEFINITE_PHRASES:
        assert phrase not in joined


def test_scenario_4_alternative_branch_available(monkeypatch):
    mock = _empty_analysis(
        unresolvedItems=["다른 지점에서 이용 가능한지 여부는 확인되지 않는다."],
        userClaims=["다른 지점 이용 안내를 받았다고 설명한다."],
    )
    _mock_openai_returning(monkeypatch, mock)

    result = llm_service.analyze_case("CASE-SC4", case={"case_id": "CASE-SC4"})

    _assert_c2_keys_and_types(result)
    assert result["_source"] == "ai"
    branch_related = (
        any("지점" in item or "대체" in item for item in result["unresolvedItems"])
        or any("지점" in item or "대체" in item for item in result["userClaims"])
        or any("지점" in item or "대체" in item for item in result["contradictions"])
    )
    assert branch_related


def test_scenario_5_contract_user_input_contradiction(monkeypatch):
    mock = _empty_analysis(
        contradictions=["계약서상 이용기간과 소비자가 입력한 기간이 다름"],
    )
    _mock_openai_returning(monkeypatch, mock)

    result = llm_service.analyze_case("CASE-SC5", case={"case_id": "CASE-SC5"})

    _assert_c2_keys_and_types(result)
    assert result["_source"] == "ai"
    assert result["contradictions"] != [_NO_CONTRADICTION]
    assert _NO_CONTRADICTION not in result["contradictions"][0]


def test_scenario_6_amount_installment_criteria_no_fabricated_sentinel(monkeypatch):
    mock = _empty_analysis(
        confirmedFacts=["결제금액 120,000원·3개월 할부로 사례 정보에 기재되어 있다."],
        unresolvedItems=["할부항변 금액·기간 기준 충족 여부 추가 확인 필요"],
    )
    _mock_openai_returning(monkeypatch, mock)

    result = llm_service.analyze_case("CASE-SC6", case={"case_id": "CASE-SC6"})

    _assert_c2_keys_and_types(result)
    assert result["_source"] == "ai"
    joined = " ".join(result["confirmedFacts"])
    assert _SENTINEL_DATE not in joined
