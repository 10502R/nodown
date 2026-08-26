from services.rule_service import (
    VERDICT_LIKELY,
    VERDICT_NEEDS_MORE_INFO,
    VERDICT_UNLIKELY,
    evaluate,
)


def test_all_conditions_met_returns_likely():
    case = {
        "merchant_status": "closed",
        "remaining_installments": 5,
        "service_used_after_closure": False,
        "evidence_files": ["contract.pdf"],
    }
    assert evaluate(case)["verdict"] == VERDICT_LIKELY


def test_missing_info_returns_needs_more_info():
    case = {
        "merchant_status": "closed",
        "remaining_installments": 5,
        "service_used_after_closure": None,
        "evidence_files": [],
    }
    assert evaluate(case)["verdict"] == VERDICT_NEEDS_MORE_INFO


def test_merchant_open_returns_unlikely():
    case = {
        "merchant_status": "open",
        "remaining_installments": 0,
        "service_used_after_closure": True,
        "evidence_files": [],
    }
    assert evaluate(case)["verdict"] == VERDICT_UNLIKELY
