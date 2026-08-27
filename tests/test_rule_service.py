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


def test_representative_case_checks_extended_conditions():
    case = {
        "merchant_status": "closed",
        "amount": 1_200_000,
        "installment_months": 12,
        "remaining_installments": 7,
        "service_used_after_closure": False,
        "refund_completed": False,
        "replacement_service_offered": False,
        "consumer_fault": False,
        "evidence_files": ["contract.pdf"],
    }

    result = evaluate(case)

    assert result["verdict"] == VERDICT_LIKELY
    assert result["missing_conditions"] == []
    assert result["failed_conditions"] == []
    assert len(result["condition_items"]) == 9


def test_extended_missing_field_needs_more_info():
    case = {
        "merchant_status": "closed",
        "amount": 1_200_000,
        "installment_months": 12,
        "remaining_balance": 700_000,
        "service_discontinued": None,
        "refund_completed": False,
        "replacement_service_offered": None,
        "consumer_fault": None,
        "evidence_files": [],
    }

    result = evaluate(case)

    assert result["verdict"] == VERDICT_NEEDS_MORE_INFO
    assert "서비스 중단 후 미이용 여부" in result["missing_conditions"]
