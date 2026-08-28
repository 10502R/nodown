import io
import os

from app import create_app

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_evidence")


def _client():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    return app.test_client()


def test_evidence_index_renders_without_documents():
    client = _client()
    response = client.get("/evidence/CASE-001")
    assert response.status_code == 200
    assert "증빙자료를 모아 주세요" in response.get_data(as_text=True)


def test_sample_document_registers_via_real_file_and_extracts_fields():
    """B-1: 예시문서는 텍스트가 아니라 실제 파일(contract.pdf)을 통해 등록된다."""
    client = _client()
    response = client.post(
        "/evidence/CASE-001/sample", data={"sample_key": "contract"}, follow_redirects=True
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "contract.pdf" in body
    assert "1,200,000원" in body  # extract_fields가 계약금액을 구조화함


def test_uploading_real_sample_pdf_is_accepted():
    """B-7: 샘플 PDF가 실제 업로드 경로로 올라가는지 확인한다."""
    client = _client()
    with open(os.path.join(SAMPLE_DIR, "contract.pdf"), "rb") as f:
        data = {"label": "이용계약서", "file": (io.BytesIO(f.read()), "contract.pdf")}
        response = client.post(
            "/evidence/CASE-001/upload", data=data, content_type="multipart/form-data",
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert "이용계약서" in response.get_data(as_text=True)


def test_uploading_real_sample_image_is_accepted():
    """B-7: 샘플 이미지가 실제 업로드 경로로 올라가는지 확인한다."""
    client = _client()
    with open(os.path.join(SAMPLE_DIR, "refund_sms.png"), "rb") as f:
        data = {"label": "환불 문자", "file": (io.BytesIO(f.read()), "refund_sms.png")}
        response = client.post(
            "/evidence/CASE-001/upload", data=data, content_type="multipart/form-data",
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert "환불 문자" in response.get_data(as_text=True)


def test_upload_rejects_disallowed_extension():
    client = _client()
    data = {"label": "악성파일", "file": (io.BytesIO(b"x"), "virus.exe")}
    response = client.post(
        "/evidence/CASE-001/upload", data=data, content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "이미지(jpg/png) 또는 PDF" in response.get_data(as_text=True)


def test_manual_entry_and_delete_round_trip():
    client = _client()
    response = client.post(
        "/evidence/CASE-001/manual",
        data={"label": "직접 입력", "text": "환불 요청일: 2026.08.11"},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "환불 요청일" in body and "2026-08-11" in body

    response = client.post("/evidence/CASE-001/delete/1", follow_redirects=True)
    assert "아직 등록된 자료가 없습니다" in response.get_data(as_text=True)


def test_download_sample_serves_real_file_with_correct_type():
    client = _client()
    response = client.get("/evidence/sample/contract/download")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert len(response.data) > 1000


def test_download_sample_unknown_key_is_404():
    client = _client()
    response = client.get("/evidence/sample/does-not-exist/download")
    assert response.status_code == 404
