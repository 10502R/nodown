# 담당: C
# LLM 호출, 시간순 분석, 모순/누락 탐지, 제출자료 내용 생성

from flask import Blueprint, render_template, request
from services import llm_service

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")


@analysis_bp.route("/", methods=["GET"])
@analysis_bp.route("/<case_id>", methods=["GET"])
def index(case_id="CASE-001"):
    """
    분석 대시보드 메인 화면.
    기본 접속 시에도 8개 카드 UI를 바로 확인할 수 있도록 서비스를 호출하여 렌더링합니다.
    """
    analysis_data = llm_service.analyze_case(case_id)
    case_info = {"case_id": case_id, "merchant_name": "올데이 피트니스"}
    
    return render_template(
        "analysis.html",
        analysis_result=analysis_data,
        case=case_info
    )


@analysis_bp.route("/run", methods=["POST"])
def run():
    """사례 ID 재조회 및 재분석 실행 엔드포인트"""
    case_id = request.form.get("case_id", "CASE-001")
    analysis_data = llm_service.analyze_case(case_id)
    case_info = {"case_id": case_id, "merchant_name": "올데이 피트니스"}
    
    return render_template(
        "analysis.html",
        analysis_result=analysis_data,
        case=case_info
    )