# 담당: A
# 거래 탐지, 가맹점 상태 확인, 사례 생성, 규칙 엔진, 카드사 알림

from flask import Blueprint, render_template

from services import case_service, rule_service

detection_bp = Blueprint("detection", __name__, url_prefix="/detection")


@detection_bp.route("/")
def index():
    cases = case_service.list_detected_cases()
    return render_template("detection.html", cases=cases)


@detection_bp.route("/<case_id>")
def case_detail(case_id):
    case = case_service.get_case(case_id)
    verdict = rule_service.evaluate(case) if case else None
    return render_template("detection.html", case=case, verdict=verdict)
