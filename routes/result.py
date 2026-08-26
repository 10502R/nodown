# 담당: D
# 전체 디자인, 최종 결과, 제출자료 내려받기, 화면 연결, 배포

from flask import Blueprint, render_template, send_file

from services import report_service

result_bp = Blueprint("result", __name__, url_prefix="/result")


@result_bp.route("/<case_id>")
def index(case_id):
    result = report_service.build_result(case_id)
    return render_template("result.html", result=result)


@result_bp.route("/<case_id>/download")
def download(case_id):
    file_path = report_service.build_report_file(case_id)
    return send_file(file_path, as_attachment=True)
