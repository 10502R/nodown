# OCR/사용자 입력으로 모인 evidence 데이터를 할부항변 신청서 서식용
# 컨텍스트로 변환하는 순수 함수. LLM을 호출하지 않고 파일도 쓰지 않는다.
# 입력 스키마는 docs/evidence_schema.md 참고.

import re
from datetime import datetime

from services import ocr_service

# 신청서 인쇄물의 체크박스 문구와 반드시 같은 글자여야 한다(templates/submission_form.html).
ATTACHMENT_OPTIONS = [
    "이용계약서 사본", "카드 결제내역", "가맹점과 주고받은 문자·메신저", "환불 요청 기록",
    "출석·예약·이용 기록", "휴·폐업 안내문", "사업자 상태조회 결과",
]
REASON_MERCHANT_CLOSED = "부도/폐업/연락불가"
REASON_SERVICE_NOT_PROVIDED = "서비스 미제공"

# (출력 키, evidence 안 경로, 값 종류)
# 값 종류: "text"(그대로) | "date"(YYYY.MM.DD) | "amount"(콤마 포함 문자열) | "number"(그대로)
_FIELD_SPECS = [
    ("issuer.name", ("issuer", "name"), "text"),
    ("issuer.dept", ("issuer", "dept"), "text"),

    ("merchant.name", ("merchant", "name"), "text"),
    ("merchant.bizNo", ("merchant", "bizNo"), "text"),
    ("merchant.address", ("merchant", "address"), "text"),

    ("applicant.name", ("applicant", "name"), "text"),
    ("applicant.birth", ("applicant", "birth"), "date"),
    ("applicant.address", ("applicant", "address"), "text"),
    ("applicant.phone", ("applicant", "phone"), "text"),
    ("applicant.cardNoMasked", ("applicant", "cardNoMasked"), "text"),
    ("applicant.agentName", ("applicant", "agentName"), "text"),

    ("transaction.date", ("transaction", "date"), "date"),
    ("transaction.merchantName", ("transaction", "merchantName"), "text"),
    ("transaction.category", ("transaction", "category"), "text"),
    ("transaction.itemName", ("transaction", "itemName"), "text"),
    ("transaction.amount", ("transaction", "amount"), "amount"),
    ("transaction.installmentMonths", ("transaction", "installmentMonths"), "number"),
    ("transaction.paidAmount", ("transaction", "paidAmount"), "amount"),
    ("transaction.remainingAmount", ("transaction", "remainingAmount"), "amount"),
    ("transaction.remainingMonths", ("transaction", "remainingMonths"), "number"),
    ("transaction.billingDay", ("transaction", "billingDay"), "number"),
    ("transaction.channel", ("transaction", "channel"), "text"),

    ("timeline.contractDate", ("timeline", "contractDate"), "date"),
    ("timeline.serviceStartDate", ("timeline", "serviceStartDate"), "date"),
    ("timeline.serviceStopDate", ("timeline", "serviceStopDate"), "date"),
    ("timeline.merchantNoticeDate", ("timeline", "merchantNoticeDate"), "date"),
    ("timeline.refundRequestDate", ("timeline", "refundRequestDate"), "date"),
    ("timeline.merchantResponse", ("timeline", "merchantResponse"), "text"),
]

# 배열 값 전체를 하나의 필드로 감싸는 항목들 (출력 키, evidence 안 경로).
_ARRAY_FIELD_SPECS = [
    ("reasonTypes", ("reasonTypes",)),
    ("attachments", ("attachments",)),
]



def _get_field(evidence, path):
    """evidence에서 path가 가리키는 {"value", "source"} 필드를 읽는다.

    경로가 없거나 형식이 어긋나면 (None, "unverified")로 취급한다
    (값을 추측해서 채우지 않는다).
    """
    node = evidence
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None, "unverified"
        node = node[key]
    if not isinstance(node, dict):
        return None, "unverified"
    return node.get("value"), node.get("source") or "unverified"


def _format_amount(value):
    try:
        return "{:,}".format(int(value))
    except (TypeError, ValueError):
        return str(value)


def _format_date(value):
    if not value:
        return ""
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%Y.%m.%d")
        except ValueError:
            return value
    return str(value)


def _format_value(value, value_type):
    if value_type == "amount":
        return _format_amount(value)
    if value_type == "date":
        return _format_date(value)
    return value


def _months_between(start, stop):
    """두 ISO 날짜 사이의 개월 수를 대략 계산한다(실제 이용 기간 서술용)."""
    try:
        start_dt = datetime.strptime(str(start)[:10], "%Y-%m-%d")
        stop_dt = datetime.strptime(str(stop)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None
    days = (stop_dt - start_dt).days
    if days <= 0:
        return None
    return max(1, round(days / 30))


def _verified(evidence, path):
    value, source = _get_field(evidence, path)
    if source == "unverified" or value in (None, ""):
        return None
    return value


def _build_statement(evidence):
    """해당 건의 계약·이용·중단·환불 정보를 시간 순 설명체 문장으로 종합한다.

    4번 항목 서술란의 안내 문구(본인 사용 여부, 계약 체결일, 서비스 시행일,
    가맹점 해지 통보일, 가맹점과의 분쟁 내용 등)를 그대로 따른다. 확인되지
    않은 항목은 추측해서 채우지 않고 문장 자체를 뺀다.
    """
    lines = []

    contract_date = _verified(evidence, ("timeline", "contractDate"))
    if contract_date:
        merchant_name = _verified(evidence, ("transaction", "merchantName"))
        amount = _verified(evidence, ("transaction", "amount"))
        months = _verified(evidence, ("transaction", "installmentMonths"))
        detail = "{0}에서 ".format(merchant_name) if merchant_name else ""
        if amount:
            detail += "{0}원".format(_format_amount(amount))
            detail += "({0}개월 할부)".format(months) if months else ""
            detail += " 조건으로 계약을 체결하였습니다."
        else:
            detail += "계약을 체결하였습니다."
        lines.append("{0}에 {1}".format(_format_date(contract_date), detail))

    start_date = _verified(evidence, ("timeline", "serviceStartDate"))
    if start_date:
        lines.append("{0}부터 서비스 이용을 시작하였습니다.".format(_format_date(start_date)))

    stop_date = _verified(evidence, ("timeline", "serviceStopDate"))
    if stop_date:
        duration = _months_between(start_date, stop_date) if start_date else None
        if duration:
            lines.append(
                "{0}에 서비스가 중단되었습니다(실제 이용 기간 약 {1}개월).".format(_format_date(stop_date), duration)
            )
        else:
            lines.append("{0}에 서비스가 중단되었습니다.".format(_format_date(stop_date)))

    used_after_closure = _verified(evidence, ("situation", "usedAfterClosure"))
    if used_after_closure is not None:
        lines.append(
            "가맹점 중단 이후에도 서비스를 일부 이용하였습니다."
            if used_after_closure
            else "가맹점 중단 이후로는 서비스를 이용하지 못했습니다."
        )

    notice_date = _verified(evidence, ("timeline", "merchantNoticeDate"))
    if notice_date:
        lines.append("{0}에 가맹점으로부터 중단 안내를 받았습니다.".format(_format_date(notice_date)))

    refund_date = _verified(evidence, ("timeline", "refundRequestDate"))
    if refund_date:
        lines.append("{0}에 가맹점에 환불을 요청하였습니다.".format(_format_date(refund_date)))

    response = _verified(evidence, ("timeline", "merchantResponse"))
    if response:
        lines.append("가맹점의 답변은 다음과 같습니다: {0}.".format(response))

    replacement_offered = _verified(evidence, ("situation", "replacementServiceOffered"))
    if replacement_offered is not None:
        lines.append(
            "대체 지점 이용 안내를 받았습니다." if replacement_offered else "대체 지점 이용 안내를 받지 못했습니다."
        )

    return lines


def build_form_context(evidence):
    """evidence 데이터를 신청서 서식용 컨텍스트 dict로 변환한다.

    순수 함수다: evidence를 읽기만 하고, 파일을 쓰거나 다른 서비스를
    호출하지 않는다.
    """
    evidence = evidence or {}
    context = {}
    unverified_fields = []

    for output_key, path, value_type in _FIELD_SPECS:
        value, source = _get_field(evidence, path)
        if source == "unverified":
            context[output_key] = ""
            unverified_fields.append(output_key)
            continue
        context[output_key] = _format_value(value, value_type) if value is not None else ""

    for output_key, path in _ARRAY_FIELD_SPECS:
        value, source = _get_field(evidence, path)
        if source == "unverified" or value is None:
            context[output_key] = []
            unverified_fields.append(output_key)
        else:
            context[output_key] = list(value)

    context["statement"] = _build_statement(evidence)
    context["unverifiedFields"] = unverified_fields
    return context


def _tokenize(text):
    return set(token for token in re.split(r"[\s,/·]+", text) if len(token) >= 2)


def _find_option_match(value, options):
    """value가 신청서 체크박스 문구(option) 중 하나를 가리키는지 느슨하게 찾는다.

    B가 모은 문서 라벨은 신청서 문구와 글자가 완전히 같지 않을 수 있어
    (예: "환불 요청 문자" vs "환불 요청 기록") 부분 포함, 없으면 낱말 겹침으로
    한 번 더 본다. 못 찾으면 None — 이 경우 호출자가 "기타"로 남긴다.
    """
    for option in options:
        if value in option or option in value:
            return option

    value_tokens = _tokenize(value)
    best_option, best_score = None, 0
    for option in options:
        score = len(_tokenize(option) & value_tokens)
        if score > best_score:
            best_option, best_score = option, score
    return best_option


def normalize_to_options(raw_values, options):
    """raw_values 각 항목을 알려진 체크박스 문구로 맞출 수 있으면 그 문구로 바꾼다.

    맞는 문구를 못 찾은 항목은 원문 그대로 남겨 둔다(서식의 "기타" 칸에 쓰인다).
    """
    normalized = []
    for raw in raw_values or []:
        raw = (raw or "").strip()
        if not raw:
            continue
        normalized.append(_find_option_match(raw, options) or raw)
    return normalized


def _wrapped(value, source):
    """확인된 값이 없으면 무조건 unverified로 내린다(추측 금지)."""
    if value is None or value == "":
        return {"value": None, "source": "unverified"}
    return {"value": value, "source": source}


def build_evidence_from_case(case, documents=None):
    """A의 사례 데이터와 B가 모은 증빙 문서에서 build_form_context용 evidence를 만든다.

    이 앱에 아직 없는 항목(카드사 정보, 신청인 개인정보, 신청 사유 선택 등)은
    임의로 채우지 않고 unverified로 둔다 — build_form_context가 그대로
    빈칸 처리와 unverifiedFields 기록을 맡는다.
    """
    case = case or {}
    documents = documents or []

    ocr_fields, _ = ocr_service.aggregate_fields(documents)
    attachment_labels = normalize_to_options(
        [doc.get("label") for doc in documents if doc.get("label")], ATTACHMENT_OPTIONS
    )

    amount = case.get("amount")
    remaining_amount = case.get("remaining_balance")
    paid_amount = (
        amount - remaining_amount
        if isinstance(amount, (int, float)) and isinstance(remaining_amount, (int, float))
        else None
    )

    # 신청 사유는 임의로 고르지 않고, A가 이미 확인한 가맹점 상태·상황 응답에서만
    # 뽑는다(폐업이 확인됐거나, 서비스가 끊겼고 대체 서비스도 없었던 경우).
    reason_types = []
    if case.get("merchant_status") == "closed":
        reason_types.append(REASON_MERCHANT_CLOSED)
    if case.get("service_discontinued") and not case.get("replacement_service_offered"):
        if REASON_SERVICE_NOT_PROVIDED not in reason_types:
            reason_types.append(REASON_SERVICE_NOT_PROVIDED)

    replacement_offered = ocr_fields.get("replacementServiceOffered")
    replacement_source = "ocr"
    if replacement_offered is None:
        replacement_offered = case.get("replacement_service_offered")
        replacement_source = "user"

    used_after_closure = case.get("service_used_after_closure")

    return {
        "issuer": {
            "name": _wrapped(None, "unverified"),
            "dept": _wrapped(None, "unverified"),
        },
        "merchant": {
            "name": _wrapped(case.get("merchant_name"), "user"),
            "bizNo": _wrapped(case.get("business_number"), "user"),
            "address": _wrapped(None, "unverified"),
        },
        "applicant": {
            "name": _wrapped(None, "unverified"),
            "birth": _wrapped(None, "unverified"),
            "address": _wrapped(None, "unverified"),
            "phone": _wrapped(None, "unverified"),
            "cardNoMasked": _wrapped(None, "unverified"),
            "agentName": _wrapped(None, "unverified"),
        },
        "transaction": {
            "date": _wrapped(case.get("purchase_date"), "user"),
            "merchantName": _wrapped(case.get("merchant_name"), "user"),
            "category": _wrapped(case.get("merchant_category"), "user"),
            "itemName": _wrapped(None, "unverified"),
            "amount": _wrapped(amount, "user"),
            "installmentMonths": _wrapped(case.get("installment_months"), "user"),
            "paidAmount": _wrapped(paid_amount, "user"),
            "remainingAmount": _wrapped(remaining_amount, "user"),
            "remainingMonths": _wrapped(case.get("remaining_installments"), "user"),
            "billingDay": _wrapped(None, "unverified"),
            "channel": _wrapped(None, "unverified"),
        },
        "reasonTypes": _wrapped(reason_types or None, "user"),
        "timeline": {
            "contractDate": _wrapped(ocr_fields.get("contractDate") or case.get("purchase_date"), "ocr"),
            "serviceStartDate": _wrapped(ocr_fields.get("serviceStartDate"), "ocr"),
            "serviceStopDate": _wrapped(ocr_fields.get("serviceStopDate") or case.get("closed_date"), "ocr"),
            "merchantNoticeDate": _wrapped(None, "unverified"),
            "refundRequestDate": _wrapped(ocr_fields.get("refundRequestDate"), "ocr"),
            "merchantResponse": _wrapped(None, "unverified"),
        },
        "situation": {
            "replacementServiceOffered": _wrapped(replacement_offered, replacement_source),
            "usedAfterClosure": _wrapped(used_after_closure, "user"),
        },
        "attachments": _wrapped(attachment_labels or None, "user"),
    }
