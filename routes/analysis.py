# 담당: C
# LLM 호출, 시간순 분석, 모순/누락 탐지, 제출자료 내용 생성

from flask import Blueprint, render_template, request

from services import llm_service

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")


@analysis_bp.route("/", methods=["GET"])
def index():
    return render_template("analysis.html")


@analysis_bp.route("/run", methods=["POST"])
def run():
    case_id = request.form.get("case_id")
    analysis = llm_service.analyze_case(case_id)
    return render_template("analysis.html", analysis=analysis)
