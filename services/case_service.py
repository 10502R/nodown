# 담당: A
# 합성 거래데이터를 읽어 거래 탐지, 가맹점 상태 모의조회, 사례 생성을 제공한다.

import json
import os
from copy import deepcopy

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

MIN_TRANSACTION_AMOUNT = 200_000
MIN_INSTALLMENT_MONTHS = 3

STATUS_LABELS = {
    "open": "정상 영업",
    "suspended": "휴업",
    "closed": "폐업",
    "unknown": "확인 불가",
}

STATUS_CODES = {
    "open": "01",
    "suspended": "02",
    "closed": "03",
    "unknown": "99",
}

# API를 호출하지 않는 MVP이므로 실행 중 생성된 사례만 메모리에 보관한다.
# 원본 합성데이터 파일을 실행 중 덮어쓰지 않아 재실행해도 결과가 오염되지 않는다.
_RUNTIME_CASES = {}


def _load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_transactions():
    """합성 카드거래 전체를 반환한다."""
    return _load_json("transactions.json")


def get_transaction(transaction_id):
    """거래 ID로 합성 거래를 찾는다."""
    return next(
        (transaction for transaction in list_transactions()
         if transaction.get("transaction_id") == transaction_id),
        None,
    )


def _normalise_status(status):
    if status in STATUS_LABELS:
        return status
    return "unknown"


def check_merchant_status(transaction_or_id):
    """국세청 API 명세를 흉내 낸 합성 가맹점 상태 응답을 만든다.

    실제 외부 API를 호출하지 않으며, 대표 시연과 테스트를 같은 입력으로
    반복할 수 있도록 거래 JSON의 상태값만 사용한다.
    """
    transaction = transaction_or_id
    if isinstance(transaction_or_id, str):
        transaction = get_transaction(transaction_or_id)
    if transaction is None:
        return None

    status = _normalise_status(transaction.get("merchant_status"))
    return {
        "businessNumber": transaction.get("business_number"),
        "statusCode": STATUS_CODES[status],
        "status": status,
        "statusLabel": STATUS_LABELS[status],
        "closedDate": transaction.get("closed_date"),
        "isSynthetic": True,
    }


def evaluate_transaction(transaction):
    """거래 한 건의 필터 조건, 상태조회 결과, 최종 탐지 결과를 계산한다."""
    status = check_merchant_status(transaction)
    amount = transaction.get("amount")
    installment_months = transaction.get("installment_months")
    remaining_balance = transaction.get("remaining_balance")
    if remaining_balance is None:
        remaining_balance = (transaction.get("remaining_installments") or 0)

    conditions = [
        {
            "key": "amount_threshold",
            "label": "결제금액 기준",
            "passed": amount is not None and amount >= MIN_TRANSACTION_AMOUNT,
            "detail": (
                f"{amount:,}원 ≥ {MIN_TRANSACTION_AMOUNT:,}원"
                if amount is not None
                else "결제금액 미확인"
            ),
        },
        {
            "key": "installment_term",
            "label": "할부기간 기준",
            "passed": (
                installment_months is not None
                and installment_months >= MIN_INSTALLMENT_MONTHS
            ),
            "detail": (
                f"{installment_months}개월 ≥ {MIN_INSTALLMENT_MONTHS}개월"
                if installment_months is not None
                else "할부기간 미확인"
            ),
        },
        {
            "key": "remaining_balance",
            "label": "잔여 할부금",
            "passed": remaining_balance > 0,
            "detail": f"{remaining_balance:,}원",
        },
        {
            "key": "long_term_service",
            "label": "장기 서비스 업종",
            "passed": transaction.get("is_long_term_service") is True,
            "detail": transaction.get("merchant_category", "업종 미확인"),
        },
    ]
    base_eligible = all(condition["passed"] for condition in conditions)
    status_check_required = base_eligible
    is_alert_target = base_eligible and status is not None and status["status"] == "closed"

    if not base_eligible:
        outcome = "제외"
        reasons = [
            f"{condition['label']}: {condition['detail']}"
            for condition in conditions
            if not condition["passed"]
        ]
    elif is_alert_target:
        outcome = "알림 대상"
        reasons = ["장기할부·잔여금 거래이며 가맹점이 폐업 상태입니다."]
    elif status["status"] in {"suspended", "unknown"}:
        outcome = "가맹점 상태 추가 확인"
        reasons = [f"가맹점 상태: {status['statusLabel']}"]
    else:
        outcome = "알림 제외"
        reasons = ["기준 거래이지만 가맹점이 정상 영업 중입니다."]

    return {
        "transaction": deepcopy(transaction),
        "status": status,
        "conditions": conditions,
        "base_eligible": base_eligible,
        "status_check_required": status_check_required,
        "is_alert_target": is_alert_target,
        "outcome": outcome,
        "reasons": reasons,
    }


def list_detection_rows():
    """탐지 화면에 표시할 전체 거래의 판정 결과를 반환한다."""
    return [evaluate_transaction(transaction) for transaction in list_transactions()]


def list_detected_cases():
    """정적으로 준비한 사례와 실행 중 생성된 사례를 합쳐 반환한다."""
    cases = _load_json("demo_cases.json")
    cases.extend(_RUNTIME_CASES.values())
    return deepcopy(cases)


def get_case(case_id):
    """사례 ID로 사례를 찾는다."""
    return next(
        (case for case in list_detected_cases() if case.get("case_id") == case_id),
        None,
    )


def create_case(transaction_id):
    """알림 대상 거래를 사례로 변환한다.

    이미 준비된 대표 사례는 기존 case_id를 재사용한다. 신규 사례는 메모리에만
    추가되며, API 응답을 통해 다음 화면으로 넘길 수 있다.
    """
    transaction = get_transaction(transaction_id)
    if transaction is None:
        return None, "거래를 찾을 수 없습니다."

    evaluation = evaluate_transaction(transaction)
    if not evaluation["is_alert_target"]:
        return None, "알림 대상 거래가 아니므로 사례를 생성할 수 없습니다."

    existing_case = next(
        (
            case for case in list_detected_cases()
            if case.get("transaction_id") == transaction_id
            or case.get("case_id") == transaction.get("case_id")
        ),
        None,
    )
    if existing_case is not None:
        return existing_case, None

    case_number = len(list_detected_cases()) + 1
    case_id = f"CASE-{case_number:03d}"
    status = evaluation["status"] or {}
    case = {
        **deepcopy(transaction),
        "case_id": case_id,
        "merchant_status": status.get("status", "unknown"),
        "merchant_status_label": status.get("statusLabel", "확인 불가"),
        "service_used_after_closure": None,
        "service_discontinued": None,
        "refund_completed": None,
        "replacement_service_offered": None,
        "consumer_fault": None,
        "evidence_files": [],
    }
    _RUNTIME_CASES[case_id] = case
    return deepcopy(case), None
