# 담당: A
# 할부항변 기본요건 판정 규칙 엔진.
#
# 중요: 위험점수/확률을 임의로 생성하지 않는다. 오직 조건의 충족 여부를
# 평가하고, 최종 인정 여부는 카드사가 결정한다.

VERDICT_LIKELY = "기본요건 충족 가능성 있음"
VERDICT_NEEDS_MORE_INFO = "추가자료 확인 필요"
VERDICT_UNLIKELY = "기본요건 충족 어려움"

MIN_TRANSACTION_AMOUNT = 200_000
MIN_INSTALLMENT_MONTHS = 3

CONDITION_LABELS = {
    "merchant_closed": "가맹점 폐업 여부",
    "installment_remaining": "남은 할부금 존재 여부",
    "service_unused": "서비스 중단 후 미이용 여부",
    "has_evidence": "증빙자료 확보 여부",
    "amount_threshold": "결제금액 기준",
    "installment_term": "할부기간 기준",
    "refund_not_completed": "환불 미완료 여부",
    "replacement_not_offered": "대체 서비스 미제공 여부",
    "consumer_not_at_fault": "소비자 귀책 없음",
}


def _condition_value(case, key):
    """값이 없으면 None을 유지해 자료 부족과 미충족을 구분한다."""
    return case[key] if key in case else None


def _service_unused(case):
    if "service_used_after_closure" in case:
        value = case.get("service_used_after_closure")
        return None if value is None else value is False
    if "service_discontinued" in case:
        value = case.get("service_discontinued")
        return None if value is None else value is True
    return None


def _remaining_installment_condition(case):
    if "remaining_balance" in case:
        value = case.get("remaining_balance")
        return None if value is None else value > 0
    if "remaining_installments" in case:
        value = case.get("remaining_installments")
        return None if value is None else value > 0
    return None


def _check_conditions(case):
    """case 딕셔너리의 필드를 바탕으로 조건별 충족 여부를 계산한다.

    초기 스켈레톤과의 호환을 위해 최소 필드만 있는 사례는 기본 4개 조건을
    평가한다. 확장 필드가 하나라도 들어오면 MVP의 전체 조건을 평가하며,
    누락된 확장 필드는 None(추가 확인 필요)으로 남긴다.
    """
    conditions = {
        "merchant_closed": (
            None
            if "merchant_status" not in case or case.get("merchant_status") is None
            else case.get("merchant_status") == "closed"
        ),
        "installment_remaining": _remaining_installment_condition(case),
        "service_unused": _service_unused(case),
        "has_evidence": (
            None
            if "evidence_files" not in case
            else bool(case.get("evidence_files"))
        ),
    }

    extended_keys = {
        "amount",
        "installment_months",
        "refund_completed",
        "replacement_service_offered",
        "consumer_fault",
    }
    if extended_keys.intersection(case):
        amount = _condition_value(case, "amount")
        term = _condition_value(case, "installment_months")
        refund_completed = _condition_value(case, "refund_completed")
        replacement_offered = _condition_value(case, "replacement_service_offered")
        consumer_fault = _condition_value(case, "consumer_fault")

        conditions.update(
            {
                "amount_threshold": (
                    None if amount is None else amount >= MIN_TRANSACTION_AMOUNT
                ),
                "installment_term": (
                    None if term is None else term >= MIN_INSTALLMENT_MONTHS
                ),
                "refund_not_completed": (
                    None if refund_completed is None else refund_completed is False
                ),
                "replacement_not_offered": (
                    None
                    if replacement_offered is None
                    else replacement_offered is False
                ),
                "consumer_not_at_fault": (
                    None if consumer_fault is None else consumer_fault is False
                ),
            }
        )

    return conditions


def _status_text(value):
    if value is True:
        return "충족"
    if value is False:
        return "미충족"
    return "추가 확인 필요"


def evaluate(case):
    """동일한 입력에 동일한 3단계 판정과 근거를 반환한다."""
    if case is None:
        return {
            "verdict": VERDICT_NEEDS_MORE_INFO,
            "conditions": {},
            "condition_items": [],
            "missing_conditions": [],
            "failed_conditions": [],
            "final_decision_notice": "최종 판정은 카드사가 결정합니다.",
        }

    conditions = _check_conditions(case)
    missing = [key for key, value in conditions.items() if value is None]
    failed = [key for key, value in conditions.items() if value is False]

    if missing:
        verdict = VERDICT_NEEDS_MORE_INFO
    elif not failed:
        verdict = VERDICT_LIKELY
    elif (
        conditions.get("merchant_closed")
        and conditions.get("installment_remaining")
        and not conditions.get("has_evidence")
    ):
        verdict = VERDICT_NEEDS_MORE_INFO
    else:
        verdict = VERDICT_UNLIKELY

    condition_items = [
        {
            "key": key,
            "label": CONDITION_LABELS.get(key, key),
            "value": value,
            "status": _status_text(value),
        }
        for key, value in conditions.items()
    ]

    return {
        "verdict": verdict,
        "conditions": conditions,
        "condition_items": condition_items,
        "missing_conditions": [CONDITION_LABELS.get(key, key) for key in missing],
        "failed_conditions": [CONDITION_LABELS.get(key, key) for key in failed],
        "final_decision_notice": "최종 판정은 카드사가 결정합니다.",
    }
