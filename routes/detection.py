# 담당: A
# 거래 탐지, 가맹점 상태 확인, 사례 생성, 규칙 엔진, 카드사 알림 연결점

from flask import Blueprint, abort, jsonify, render_template, request, url_for

from services import case_service, rule_service

# 기존 화면 URL(/detection/)과 명세의 API URL(/api/cases)을 함께 제공하기 위해
# Blueprint 자체에는 prefix를 두지 않고 각 라우트에 명시한다.
detection_bp = Blueprint("detection", __name__)


@detection_bp.route("/detection/")
def index():
    rows = case_service.list_detection_rows()
    cases = case_service.list_detected_cases()
    return render_template("detection.html", rows=rows, cases=cases)


@detection_bp.route("/detection/<case_id>")
def case_detail(case_id):
    case = case_service.get_case(case_id)
    if case is None:
        abort(404)
    verdict = rule_service.evaluate(case)
    return render_template("detection.html", case=case, verdict=verdict)


@detection_bp.route("/api/merchant-status/<transaction_id>")
@detection_bp.route("/detection/api/merchant-status/<transaction_id>")
def merchant_status(transaction_id):
    status = case_service.check_merchant_status(transaction_id)
    if status is None:
        return jsonify({"error": "거래를 찾을 수 없습니다."}), 404
    return jsonify(status)


@detection_bp.route("/api/cases", methods=["POST"])
@detection_bp.route("/detection/api/cases", methods=["POST"])
def create_case():
    payload = request.get_json(silent=True) or request.form
    transaction_id = payload.get("transactionId") or payload.get("transaction_id")
    if not transaction_id:
        return jsonify({"error": "transactionId가 필요합니다."}), 400

    case, error = case_service.create_case(transaction_id)
    if error:
        transaction = case_service.get_transaction(transaction_id)
        evaluation = case_service.evaluate_transaction(transaction) if transaction else None
        return jsonify({
            "error": error,
            "reasons": evaluation["reasons"] if evaluation else [],
            "isSynthetic": True,
        }), 400

    return jsonify({
        "caseId": case["case_id"],
        "caseUrl": url_for("detection.case_detail", case_id=case["case_id"]),
        "isSynthetic": True,
        "case": case,
    }), 201
