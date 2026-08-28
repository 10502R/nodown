# 담당: C
# LLM 호출, 시간순 분석, 모순/누락 탐지, 제출자료 내용 생성

from flask import Blueprint, render_template, request, session

from services import llm_service

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")


def _evidence_documents(case_id):
    """B가 자료 입력 화면에서 세션에 쌓은 증빙 문서 목록을 읽는다(B→C 연동)."""
    return session.get("evidence:{0}".format(case_id))


def _load_case(case_id):
    try:
        from services import case_service

        case = case_service.get_case(case_id)
        if case is not None:
            return case
    except Exception:
        pass
    return {"case_id": case_id, "merchant_name": "올데이 피트니스"}


def _run_analysis(case_id):
    case = _load_case(case_id)
    analysis_data = llm_service.analyze_case(
        case_id, case=case, evidence=_evidence_documents(case_id)
    )
    return analysis_data, case


@analysis_bp.route("/", methods=["GET"])
@analysis_bp.route("/<case_id>", methods=["GET"])
def index(case_id="CASE-001"):
    """
    분석 대시보드 메인 화면.
    기본 접속 시에도 8개 카드 UI를 바로 확인할 수 있도록 서비스를 호출하여 렌더링합니다.
    """
    analysis_data, case = _run_analysis(case_id)

    return render_template(
        "analysis.html",
        analysis_result=analysis_data,
        case=case
    )


@analysis_bp.route("/run", methods=["POST"])
def run():
    """사례 ID 재조회 및 재분석 실행 엔드포인트"""
    case_id = request.form.get("case_id", "CASE-001")
    analysis_data, case = _run_analysis(case_id)

    return render_template(
        "analysis.html",
        analysis_result=analysis_data,
        case=case
    )
