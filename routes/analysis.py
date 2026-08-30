# 담당: C
# LLM 호출, 시간순 분석, 모순/누락 탐지, 제출자료 내용 생성

from flask import Blueprint, redirect, render_template, request, session, url_for

from services import llm_service

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")

_ANSWER_VALUES = {"yes", "no", "unknown"}


def _evidence_documents(case_id):
    """B가 자료 입력 화면에서 세션에 쌓은 증빙 문서 목록을 읽는다(B→C 연동)."""
    return session.get("evidence:{0}".format(case_id))


def _saved_followup_answers(case_id):
    """7번 섹션에서 저장한 추가 확인 질문 답변을 세션에서 읽는다."""
    return session.get("followup_answers:{0}".format(case_id))


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
        case_id,
        case=case,
        evidence=_evidence_documents(case_id),
        answers=_saved_followup_answers(case_id),
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
        case=case,
        active_step=5,
        saved_answers=_saved_followup_answers(case_id)
    )


@analysis_bp.route("/run", methods=["POST"])
def run():
    """사례 ID 재조회 및 재분석 실행 엔드포인트"""
    case_id = request.form.get("case_id", "CASE-001")
    analysis_data, case = _run_analysis(case_id)

    return render_template(
        "analysis.html",
        analysis_result=analysis_data,
        case=case,
        active_step=5,
        saved_answers=_saved_followup_answers(case_id)
    )


@analysis_bp.route("/<case_id>/followup-answers", methods=["POST"])
def save_followup_answers(case_id):
    """7번 '추가 확인 질문' 섹션의 예/아니오/모르겠음 답변과 보충 설명을 세션에 저장한다.

    질문 문구(followup_{n}_text)를 답변(followup_{n})과 함께 저장해 두어,
    다음 번 AI 분석 호출 시 llm_service.analyze_case가 질문 텍스트 기준으로
    다시 매칭할 수 있게 한다.
    """
    answers = []
    index = 1
    while True:
        question_text = request.form.get("followup_{0}_text".format(index))
        if question_text is None:
            break
        answer_value = request.form.get("followup_{0}".format(index))
        if answer_value in _ANSWER_VALUES:
            answers.append({"question": question_text, "answer": answer_value})
        index += 1

    extra_note = (request.form.get("followup_extra_note") or "").strip()

    session["followup_answers:{0}".format(case_id)] = {
        "answers": answers,
        "extra_note": extra_note,
    }

    return redirect(url_for("analysis.index", case_id=case_id, saved=1))
