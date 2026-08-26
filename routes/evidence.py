# 담당: B
# 소비자 상황 확인, 파일 업로드, OCR, 핵심정보 추출

from flask import Blueprint, render_template, request

from services import ocr_service

evidence_bp = Blueprint("evidence", __name__, url_prefix="/evidence")


@evidence_bp.route("/", methods=["GET"])
def index():
    return render_template("evidence.html")


@evidence_bp.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    extracted = ocr_service.extract_text(file) if file else None
    return render_template("evidence.html", extracted=extracted)
