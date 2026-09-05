# 담당: D
# 서비스 소개 → 앱 알림 → 소비자 상황 확인 → 결과 → 제출자료로 이어지는
# 사용자 흐름 전체를 담당한다.
#
# Blueprint에 url_prefix를 두지 않고 각 라우트에 경로를 적는다. 역할 문서가 정한
# /demo/card-app, /case/<case_id> 경로와 기존 /result/<case_id> 경로를 함께
# 제공해야 하기 때문이다. app.py는 팀 공통 파일이라 수정하지 않는다.

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from services import report_service

result_bp = Blueprint("result", __name__)

DEFAULT_CASE_ID = "CASE-001"


def _situation_key(case_id):
    """선택한 상황을 세션에 두어 새로고침해도 화면이 유지되게 한다."""
    return session.get("situation:{0}".format(case_id))


def _overrides(case_id):
    return session.get("draft:{0}".format(case_id))


def _evidence_documents(case_id):
    """B가 자료 입력 화면에서 세션에 쌓은 증빙 문서 목록을 읽는다(B→A 연동)."""
    return session.get("evidence:{0}".format(case_id))


# --- 카드사 앱 알림 시뮬레이션(D-3) -------------------------------------

@result_bp.route("/demo/card-app")
def card_app():
    cases, source = report_service.list_alert_cases()
    return render_template("card_app.html", cases=cases, source=source, active_step=2)


# --- 소비자 상황 확인(D-4) ----------------------------------------------

@result_bp.route("/case/<case_id>")
def case_confirm(case_id):
    case, source = report_service.load_case(case_id)
    if case is None:
        abort(404)

    selected = _situation_key(case_id)
    return render_template(
        "case_confirm.html",
        case=case,
        source=source,
        choices=report_service.SITUATION_CHOICES,
        selected=selected,
        situation=report_service.get_situation(selected),
        active_step=3,
    )


@result_bp.route("/case/<case_id>/situation", methods=["POST"])
def choose_situation(case_id):
    key = request.form.get("situation")
    situation = report_service.get_situation(key)
    if situation is None:
        return redirect(url_for("result.case_confirm", case_id=case_id))

    session["situation:{0}".format(case_id)] = key

    if situation["next"] == "end":
        return redirect(url_for("result.case_guidance", case_id=case_id))
    # 선택 결과와 다음 행동은 상황 확인 화면에 덧붙이지 않고 별도 화면으로 넘긴다.
    return redirect(url_for("result.case_next", case_id=case_id))


@result_bp.route("/case/<case_id>/next")
def case_next(case_id):
    """상황을 고른 다음 무엇을 할지 보여주는 화면이다."""
    case, source = report_service.load_case(case_id)
    if case is None:
        abort(404)

    situation = report_service.get_situation(_situation_key(case_id))
    if situation is None:
        return redirect(url_for("result.case_confirm", case_id=case_id))
    if situation["next"] == "end":
        return redirect(url_for("result.case_guidance", case_id=case_id))

    return render_template(
        "case_next.html", case=case, source=source, situation=situation,
        active_step=3,
    )


@result_bp.route("/case/<case_id>/guidance")
def case_guidance(case_id):
    case, source = report_service.load_case(case_id)
    if case is None:
        abort(404)

    situation = report_service.get_situation(_situation_key(case_id))
    return render_template(
        "case_guidance.html", case=case, source=source, situation=situation,
        active_step=3,
    )


# --- 결과 화면(D-5) ------------------------------------------------------

@result_bp.route("/case/<case_id>/result")
def case_result(case_id):
    result = report_service.build_result(
        case_id,
        situation_key=_situation_key(case_id),
        overrides=_overrides(case_id),
        evidence=_evidence_documents(case_id),
    )
    if result is None:
        abort(404)
    return render_template("result.html", result=result, active_step=6)


# --- 제출자료 확인·내려받기(D-6) ----------------------------------------

@result_bp.route("/case/<case_id>/submission")
def submission(case_id):
    result = report_service.build_result(
        case_id,
        situation_key=_situation_key(case_id),
        overrides=_overrides(case_id),
        evidence=_evidence_documents(case_id),
    )
    if result is None:
        abort(404)
    return render_template(
        "submission.html",
        result=result,
        draft=result["draft"],
        preview=report_service.render_submission_text(result["draft"]),
        active_step=7,
    )


@result_bp.route("/case/<case_id>/submission", methods=["POST"])
def save_submission(case_id):
    """소비자가 고친 본문을 세션에 저장한다. 서버에 사례를 남기지 않는다."""
    edits = {
        key[len("section-"):]: value
        for key, value in request.form.items()
        if key.startswith("section-")
    }
    session["draft:{0}".format(case_id)] = edits
    return redirect(url_for("result.submission", case_id=case_id, saved=1))


@result_bp.route("/case/<case_id>/submission/reset", methods=["POST"])
def reset_submission(case_id):
    session.pop("draft:{0}".format(case_id), None)
    return redirect(url_for("result.submission", case_id=case_id))


@result_bp.route("/case/<case_id>/download")
def download(case_id):
    file_path = report_service.build_report_file(
        case_id,
        situation_key=_situation_key(case_id),
        overrides=_overrides(case_id),
        evidence=_evidence_documents(case_id),
    )
    return send_file(
        file_path,
        as_attachment=True,
        download_name="{0}_submission_draft.txt".format(case_id),
        mimetype="text/plain; charset=utf-8",
    )


@result_bp.route("/case/<case_id>/print")
def print_view(case_id):
    """인쇄·PDF 저장용 화면. 브라우저 인쇄로 PDF를 만든다."""
    result = report_service.build_result(
        case_id,
        situation_key=_situation_key(case_id),
        overrides=_overrides(case_id),
        evidence=_evidence_documents(case_id),
    )
    if result is None:
        abort(404)
    return render_template("submission_print.html", result=result, draft=result["draft"])


# --- 기존 경로 호환 ------------------------------------------------------

@result_bp.route("/result/<case_id>")
def index(case_id):
    return redirect(url_for("result.case_result", case_id=case_id))


@result_bp.route("/result/<case_id>/download")
def legacy_download(case_id):
    return redirect(url_for("result.download", case_id=case_id))


@result_bp.route("/demo/start")
def demo_start():
    """소개 화면의 `대표 시나리오 시작` 버튼이 누르는 진입점이다."""
    session.pop("situation:{0}".format(DEFAULT_CASE_ID), None)
    session.pop("draft:{0}".format(DEFAULT_CASE_ID), None)
    session.pop("evidence:{0}".format(DEFAULT_CASE_ID), None)
    return redirect(url_for("result.card_app"))


# --- 공통 오류 화면(D-1) -------------------------------------------------
# app.py를 수정하지 않기 위해 Blueprint의 app_errorhandler로 등록한다.

@result_bp.app_errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        code=404,
        title="화면을 찾을 수 없습니다",
        message="주소가 바뀌었거나 사례번호가 올바르지 않습니다. 처음 화면에서 다시 시작해 주세요.",
    ), 404


@result_bp.app_errorhandler(500)
def server_error(error):
    return render_template(
        "error.html",
        code=500,
        title="처리 중 문제가 발생했습니다",
        message="잠시 후 다시 시도해 주세요. 문제가 계속되면 처음 화면에서 대표 시나리오를 다시 실행해 주세요.",
    ), 500
