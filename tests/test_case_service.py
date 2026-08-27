from services import case_service


def test_synthetic_transactions_cover_filter_scenarios():
    transactions = case_service.list_transactions()

    assert len(transactions) == 12
    assert {transaction["merchant_status"] for transaction in transactions} >= {
        "open",
        "suspended",
        "closed",
        "unknown",
    }
    assert any(not transaction["is_long_term_service"] for transaction in transactions)
    assert any(transaction["remaining_balance"] == 0 for transaction in transactions)


def test_only_closed_long_term_transaction_is_alert_target():
    rows = case_service.list_detection_rows()
    targets = [row for row in rows if row["is_alert_target"]]

    assert [row["transaction"]["transaction_id"] for row in targets] == [
        "TX-1003",
        "TX-1006",
        "TX-1007",
        "TX-1009",
    ]
    assert all(row["outcome"] == "알림 대상" for row in targets)
    assert not next(row for row in rows if row["transaction"]["transaction_id"] == "TX-1005")["is_alert_target"]
    assert next(row for row in rows if row["transaction"]["transaction_id"] == "TX-1012")["outcome"] == "가맹점 상태 추가 확인"


def test_merchant_status_has_synthetic_api_shape():
    status = case_service.check_merchant_status("TX-1003")

    assert status["statusCode"] == "03"
    assert status["statusLabel"] == "폐업"
    assert status["isSynthetic"] is True


def test_create_case_reuses_prepared_case_and_rejects_open_business():
    case, error = case_service.create_case("TX-1003")
    assert error is None
    assert case["case_id"] == "CASE-001"

    rejected, error = case_service.create_case("TX-1005")
    assert rejected is None
    assert "생성할 수 없습니다" in error
