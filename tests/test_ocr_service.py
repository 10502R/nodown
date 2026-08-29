import base64
import io

from werkzeug.datastructures import FileStorage

from services import ocr_service
from services.ocr_service import (
    FIELD_KEYS,
    SAMPLE_DOCUMENTS,
    allowed_file,
    extract_fields,
    extract_text,
)


def test_extract_fields_reads_labeled_contract_values():
    fields = extract_fields(SAMPLE_DOCUMENTS["contract"]["text"])
    assert fields["contractDate"] == "2026-03-02"
    assert fields["contractAmount"] == 1_200_000
    assert fields["serviceStartDate"] == "2026-03-02"


def test_extract_fields_reads_refund_request_date():
    fields = extract_fields(SAMPLE_DOCUMENTS["refund_sms"]["text"])
    assert fields["refundRequestDate"] == "2026-08-11"


def test_extract_fields_reads_stop_date_and_replacement_flag():
    fields = extract_fields(SAMPLE_DOCUMENTS["closure_notice"]["text"])
    assert fields["serviceStopDate"] == "2026-08-10"
    assert fields["replacementServiceOffered"] is False


def test_extract_fields_leaves_missing_values_as_none_not_guessed():
    fields = extract_fields("아무 정보도 없는 문서입니다.")
    assert all(fields[key] is None for key in FIELD_KEYS)


def test_extract_fields_handles_empty_input():
    assert extract_fields("") == {key: None for key in FIELD_KEYS}
    assert extract_fields(None) == {key: None for key in FIELD_KEYS}


def test_allowed_file_accepts_known_extensions_case_insensitively():
    assert allowed_file("contract.PDF") is True
    assert allowed_file("photo.jpg") is True


def test_allowed_file_rejects_unknown_extension_or_missing_name():
    assert allowed_file("malware.exe") is False
    assert allowed_file("") is False
    assert allowed_file(None) is False


def test_extract_text_without_configured_keys_returns_not_configured(monkeypatch):
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_API_URL", None)
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_SECRET_KEY", None)

    file_storage = FileStorage(stream=io.BytesIO(b"x"), filename="contract.pdf")
    text, status = extract_text(file_storage)

    assert text is None
    assert status == "not_configured"


def test_extract_text_sends_base64_image_json_and_secret_header(monkeypatch):
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_API_URL", "https://example.com/ocr")
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_SECRET_KEY", "secret-key")

    captured = {}
    file_bytes = b"fake-image-bytes"

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "images": [
                    {
                        "inferResult": "SUCCESS",
                        "fields": [{"inferText": "계약일: 2026.03.02"}],
                    }
                ]
            }

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(ocr_service.requests, "post", _fake_post)

    file_storage = FileStorage(stream=io.BytesIO(file_bytes), filename="contract.jpeg")
    text, status = extract_text(file_storage)

    assert status == "ok"
    assert text == "계약일: 2026.03.02"
    assert captured["url"] == "https://example.com/ocr"
    assert captured["headers"]["X-OCR-SECRET"] == "secret-key"

    payload = captured["json"]
    assert payload["version"] == "V2"
    assert "requestId" in payload and "timestamp" in payload
    image = payload["images"][0]
    assert image["format"] == "jpg"
    assert image["name"] == "evidence"
    assert base64.b64decode(image["data"]) == file_bytes


def test_extract_text_joins_same_line_words_with_space_and_breaks_on_line_break(monkeypatch):
    """CLOVA는 단어 단위로 fields를 쪼개 돌려주므로, lineBreak=False인 조각은
    띄어쓰기로 이어붙이고 lineBreak=True에서만 줄을 바꿔 사람이 읽기 좋게 만든다."""
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_API_URL", "https://example.com/ocr")
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_SECRET_KEY", "secret-key")

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "images": [
                    {
                        "inferResult": "SUCCESS",
                        "fields": [
                            {"inferText": "서비스", "lineBreak": False},
                            {"inferText": "중단", "lineBreak": False},
                            {"inferText": "안내", "lineBreak": True},
                            {"inferText": "중단일:", "lineBreak": False},
                            {"inferText": "2026.08.10", "lineBreak": True},
                        ],
                    }
                ]
            }

    monkeypatch.setattr(
        ocr_service.requests, "post",
        lambda url, headers=None, json=None, timeout=None: _FakeResponse(),
    )

    file_storage = FileStorage(stream=io.BytesIO(b"x"), filename="closure_notice.png")
    text, status = extract_text(file_storage)

    assert status == "ok"
    assert text == "서비스 중단 안내\n중단일: 2026.08.10"


def test_extract_text_skips_failed_images_and_returns_failed_if_no_text(monkeypatch):
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_API_URL", "https://example.com/ocr")
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_SECRET_KEY", "secret-key")

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"images": [{"inferResult": "FAILURE", "fields": [{"inferText": "무시됨"}]}]}

    monkeypatch.setattr(
        ocr_service.requests, "post",
        lambda url, headers=None, json=None, timeout=None: _FakeResponse(),
    )

    file_storage = FileStorage(stream=io.BytesIO(b"x"), filename="contract.pdf")
    text, status = extract_text(file_storage)

    assert text is None
    assert status == "failed"
