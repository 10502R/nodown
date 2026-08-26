# 담당: A
# 할부항변 기본요건 판정 규칙 엔진.
#
# 중요: 위험점수/확률을 임의로 생성하지 않는다. 오직 아래 3단계 문자열 중 하나만 반환하며,
# 각 조건의 충족/부족 여부를 있는 그대로 함께 보여준다. 최종 인정 여부는 카드사가 결정한다.

VERDICT_LIKELY = "기본요건 충족 가능성 있음"
VERDICT_NEEDS_MORE_INFO = "추가자료 확인 필요"
VERDICT_UNLIKELY = "기본요건 충족 어려움"


def _check_conditions(case):
    """case 딕셔너리의 필드를 바탕으로 각 요건의 충족 여부(bool/None)를 계산한다.
    None은 '자료 부족으로 판단 불가'를 의미한다.
    """
    return {
        "merchant_closed": case.get("merchant_status") == "closed",
        "installment_remaining": (case.get("remaining_installments") or 0) > 0,
        "service_unused": case.get("service_used_after_closure") is False,
        "has_evidence": bool(case.get("evidence_files")),
    }


def evaluate(case):
    conditions = _check_conditions(case)

    if any(v is None for v in conditions.values()):
        verdict = VERDICT_NEEDS_MORE_INFO
    elif all(conditions.values()):
        verdict = VERDICT_LIKELY
    elif conditions["merchant_closed"] and conditions["installment_remaining"] and not conditions["has_evidence"]:
        verdict = VERDICT_NEEDS_MORE_INFO
    else:
        verdict = VERDICT_UNLIKELY

    return {
        "verdict": verdict,
        "conditions": conditions,
        "final_decision_notice": "최종 판정은 카드사가 결정합니다.",
    }
