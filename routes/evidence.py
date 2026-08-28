# 담당: B
# 소비자 상황 확인 이후 증빙자료를 모으는 화면이다(B-2).
# 예시문서 선택 / 파일 업로드(OCR) / 문자 내용 직접 입력을 모두 받아 세션에
# 사례별로 쌓고, 문서별 핵심 항목과 출처를 화면에 구조화해 보여준다(B-4, B-5).
#
# OCR 실패나 API 키 미설정에도 자료 입력 화면 자체는 끝까지 동작해야 하므로
# (B-3) 실패는 예외로 던지지 않고 상태값으로 다뤄 화면에 안내만 표시한다.

import os

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from services import ocr_service

evidence_bp = Blueprint("evidence", __name__, url_prefix="/evidence")

DEFAULT_CASE_ID = "CASE-001"

PRIVACY_NOTES = [
    "이 화면은 공모전 시연용으로, 실제 개인정보가 아닌 합성 문서만 사용합니다.",
    "카드번호·주민등록번호 등 민감정보가 포함된 문서는 업로드하지 마세요.",
    "업로드한 파일은 서버에 장기간 보관하지 않으며 시연 세션 동안만 유지됩니다.",
]


def _evidence_key(case_id):
    return "evidence:{0}".format(case_id)


def _documents(case_id):
    return session.get(_evidence_key(case_id)) or []


def _save_documents(case_id, documents):
    session[_evidence_key(case_id)] = documents


def _next_doc_id(documents):
    return (max((doc.get("id", 0) for doc in documents), default=0)) + 1


def _add_document(case_id, *, label, source_type, filename, ocr_status, raw_text):
    documents = _documents(case_id)
    documents.append({
        "id": _next_doc_id(documents),
        "label": label,
        "source_type": source_type,
        "filename": filename,
        "ocr_status": ocr_status,
        "raw_text": raw_text,
        "fields": ocr_service.extract_fields(raw_text),
    })
    _save_documents(case_id, documents)


def _load_case(case_id):
    try:
        from services import case_service

        return case_service.get_case(case_id)
    except Exception:
        return None


@evidence_bp.route("/", methods=["GET"])
@evidence_bp.route("/<case_id>", methods=["GET"])
def index(case_id=DEFAULT_CASE_ID):
    documents = _documents(case_id)
    fields, field_sources = ocr_service.aggregate_fields(documents)

    if any(doc.get("ocr_status") == "ok" for doc in documents):
        source = ocr_service.SOURCE_OCR
    elif any(doc.get("source_type") in ("upload", "manual") for doc in documents):
        source = ocr_service.SOURCE_USER_INPUT
    else:
        source = ocr_service.SOURCE_FIXTURE

    return render_template(
        "evidence.html",
        case_id=case_id,
        case=_load_case(case_id),
        documents=documents,
        fields=fields,
        field_sources=field_sources,
        field_labels=ocr_service.FIELD_LABELS,
        field_keys=ocr_service.FIELD_KEYS,
        sample_documents=ocr_service.SAMPLE_DOCUMENTS,
        allowed_extensions=sorted(ocr_service.ALLOWED_EXTENSIONS),
        max_file_size_mb=ocr_service.MAX_FILE_SIZE_BYTES // (1024 * 1024),
        privacy_notes=PRIVACY_NOTES,
        source=source,
        error=request.args.get("error"),
        active_step=4,
    )


@evidence_bp.route("/upload", methods=["POST"])
@evidence_bp.route("/<case_id>/upload", methods=["POST"])
def upload(case_id=DEFAULT_CASE_ID):
    file = request.files.get("file")
    label = (request.form.get("label") or "").strip() or "업로드 문서"

    if not file or not file.filename:
        return redirect(url_for("evidence.index", case_id=case_id, error="업로드할 파일을 선택해 주세요."))

    if not ocr_service.allowed_file(file.filename):
        return redirect(url_for(
            "evidence.index", case_id=case_id,
            error="이미지(jpg/png) 또는 PDF 파일만 업로드할 수 있습니다.",
        ))

    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > ocr_service.MAX_FILE_SIZE_BYTES:
        return redirect(url_for(
            "evidence.index", case_id=case_id,
            error="파일 크기는 {0}MB를 넘을 수 없습니다.".format(
                ocr_service.MAX_FILE_SIZE_BYTES // (1024 * 1024)
            ),
        ))

    text, status = ocr_service.extract_text(file)
    _add_document(
        case_id, label=label, source_type="upload", filename=file.filename,
        ocr_status=status, raw_text=text,
    )

    if status == "not_configured":
        return redirect(url_for(
            "evidence.index", case_id=case_id,
            error="OCR 연동이 아직 설정되지 않아 파일만 등록했습니다. 문자 내용을 직접 입력해 주세요.",
        ))
    if status == "failed":
        return redirect(url_for(
            "evidence.index", case_id=case_id,
            error="문서 인식에 실패했습니다. 다시 업로드하거나 문자 내용을 직접 입력해 주세요.",
        ))
    return redirect(url_for("evidence.index", case_id=case_id, uploaded=1))


@evidence_bp.route("/manual", methods=["POST"])
@evidence_bp.route("/<case_id>/manual", methods=["POST"])
def manual(case_id=DEFAULT_CASE_ID):
    text = (request.form.get("text") or "").strip()
    label = (request.form.get("label") or "").strip() or "직접 입력"

    if not text:
        return redirect(url_for("evidence.index", case_id=case_id, error="입력할 내용을 작성해 주세요."))

    _add_document(
        case_id, label=label, source_type="manual", filename=None,
        ocr_status="manual", raw_text=text,
    )
    return redirect(url_for("evidence.index", case_id=case_id, added=1))


@evidence_bp.route("/sample", methods=["POST"])
@evidence_bp.route("/<case_id>/sample", methods=["POST"])
def sample(case_id=DEFAULT_CASE_ID):
    """예시문서를 실제 파일 업로드와 같은 경로(OCR 호출)로 등록한다(B-1, B-3).

    CLOVA 키가 설정돼 있으면 실제로 그 파일을 OCR에 태운다. 키가 없거나 실패하면
    우리가 직접 만든 파일의 알려진 내용으로 대신한다 — 다른 사용자의 업로드에
    임의로 값을 채우는 것과 달리, 이 파일의 실제 내용을 우리가 알고 있기 때문이다.
    """
    key = request.form.get("sample_key")
    sample_doc = ocr_service.SAMPLE_DOCUMENTS.get(key)
    if sample_doc is None:
        return redirect(url_for("evidence.index", case_id=case_id, error="선택한 예시문서를 찾을 수 없습니다."))

    file_storage = ocr_service.open_sample_file_storage(key)
    status = "not_configured"
    text = None
    if file_storage is not None:
        try:
            text, status = ocr_service.extract_text(file_storage)
        finally:
            file_storage.close()

    if status != "ok":
        text, status = sample_doc["text"], "sample"

    _add_document(
        case_id, label=sample_doc["label"], source_type="sample",
        filename=sample_doc.get("file"), ocr_status=status, raw_text=text,
    )
    return redirect(url_for("evidence.index", case_id=case_id, added=1))


@evidence_bp.route("/sample/<key>/download")
def download_sample(key):
    """예시문서 원본 파일을 내려받는다. 파일 업로드 경로를 직접 테스트할 때 씀."""
    path = ocr_service.sample_file_path(key)
    if path is None:
        abort(404)
    return send_from_directory(
        ocr_service.SAMPLE_EVIDENCE_DIR, os.path.basename(path), as_attachment=True
    )


@evidence_bp.route("/<case_id>/delete/<int:doc_id>", methods=["POST"])
def delete(case_id, doc_id):
    documents = [doc for doc in _documents(case_id) if doc.get("id") != doc_id]
    _save_documents(case_id, documents)
    return redirect(url_for("evidence.index", case_id=case_id, deleted=1))
