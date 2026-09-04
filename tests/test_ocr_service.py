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
    mask_pii,
)


def test_extract_fields_reads_labeled_contract_values():
    fields = extract_fields(SAMPLE_DOCUMENTS["contract"]["text"])
    assert fields["contractDate"] == "2026-03-02"
    assert fields["contractAmount"] == 1_200_000
    assert fields["serviceStartDate"] == "2026-03-02"


def test_extract_fields_reads_refund_request_date():
    fields = extract_fields(SAMPLE_DOCUMENTS["refund_sms"]["text"])
    assert fields["refundRequestDate"] == "2026-08-11"


def test_extract_fields_reads_stop_date():
    fields = extract_fields(SAMPLE_DOCUMENTS["closure_notice"]["text"])
    assert fields["serviceStopDate"] == "2026-08-10"


def test_extract_fields_reads_replacement_service_flag():
    fields = extract_fields("서비스 중단일: 2026.08.10\n대체 서비스: 없음")
    assert fields["replacementServiceOffered"] is False

    fields = extract_fields("대체 서비스: 제공")
    assert fields["replacementServiceOffered"] is True


def test_extract_fields_reads_korean_style_dates():
    text = "환불 요청일: 2026년 08월 11일"
    fields = extract_fields(text)
    assert fields["refundRequestDate"] == "2026-08-11"


def test_extract_fields_reads_korean_style_dates_with_spaces_around_units():
    text = "서비스 중단일: 2026 년 08 월 10 일"
    fields = extract_fields(text)
    assert fields["serviceStopDate"] == "2026-08-10"


def test_extract_fields_reads_total_usage_fee_as_contract_amount():
    text = "총 이용대금\n금 1,200,000원 (신용카드 12개월 할부)"
    fields = extract_fields(text)
    assert fields["contractAmount"] == 1_200_000


def test_extract_fields_reads_iyongaesiil_as_service_start_date():
    text = "(이용개시일: 2026년 03월 02일)"
    fields = extract_fields(text)
    assert fields["serviceStartDate"] == "2026-03-02"


def test_extract_fields_fills_service_dates_from_contract_period_when_unlabeled():
    text = "계약기간\n2026년 03월 02일 ~ 2027년 03월 01일 (이용개시일: 2026년 03월 02일)"
    fields = extract_fields(text)
    assert fields["serviceStartDate"] == "2026-03-02"
    assert fields["serviceEndDate"] == "2027-03-01"


def test_extract_fields_prefers_explicit_label_over_contract_period_fallback():
    text = "서비스 시작일: 2026.05.01\n계약기간\n2026년 03월 02일 ~ 2027년 03월 01일"
    fields = extract_fields(text)
    assert fields["serviceStartDate"] == "2026-05-01"
    assert fields["serviceEndDate"] == "2027-03-01"


def test_extract_fields_reads_signature_date_as_contract_date_when_unlabeled():
    text = "☑ 본인은 위 내용과 이용약관에 모두 동의합니다.\n2026 년 03 월 02 일"
    fields = extract_fields(text)
    assert fields["contractDate"] == "2026-03-02"


def test_extract_fields_prefers_explicit_contract_date_label_over_signature_date():
    text = "계약일: 2026.01.01\n동의합니다.\n2026년 03월 02일"
    fields = extract_fields(text)
    assert fields["contractDate"] == "2026-01-01"


def test_extract_fields_reads_chat_date_divider_near_refund_mention_as_refund_request_date():
    """환불 요청일 라벨이 없는 채팅 캡처에서도, 날짜 뒤 근처에 환불 요청 언급이 있으면 인식한다."""
    text = (
        "2026년 8월 11일 화요일\n"
        "안녕하세요, 올데이 피트니스 회원\n"
        "김민준입니다. 회원권 환불 요청\n"
        "드립니다."
    )
    fields = extract_fields(text)
    assert fields["refundRequestDate"] == "2026-08-11"


def test_extract_fields_prefers_explicit_refund_request_label_over_chat_date_divider():
    text = "환불 요청일: 2026.08.13\n2026년 8월 11일 화요일\n환불 요청 드립니다."
    fields = extract_fields(text)
    assert fields["refundRequestDate"] == "2026-08-13"


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


def test_mask_pii_masks_resident_registration_number():
    text = "이름: 홍길동\n주민등록번호: 900101-1234567"
    masked = mask_pii(text)
    assert "900101-1234567" not in masked
    assert "[주민등록번호 가림]" in masked


def test_mask_pii_masks_card_number_with_or_without_separators():
    assert "[카드번호 가림]" in mask_pii("카드번호 1234-5678-9012-3456 결제")
    assert "[카드번호 가림]" in mask_pii("카드번호 1234567890123456 결제")


def test_mask_pii_masks_phone_number():
    assert "[전화번호 가림]" in mask_pii("연락처: 010-1234-5678")
    assert "[전화번호 가림]" in mask_pii("연락처: 01012345678")


def test_mask_pii_masks_landline_numbers_too():
    assert "[전화번호 가림]" in mask_pii("사업자 연락처: 02-2345-6789")
    assert "[전화번호 가림]" in mask_pii("연락처: 031-123-4567")


def test_mask_pii_leaves_unrelated_text_and_business_registration_number_untouched():
    """사업자등록번호(3-2-5자리)는 카드번호, 주민등록번호 패턴과 자릿수가 달라 가려지지 않아야 한다."""
    text = "사업자등록번호: 000-00-00003 (합성 번호)"
    assert mask_pii(text) == text


def test_mask_pii_does_not_affect_field_extraction():
    text = "계약일: 2026.03.02\n주민등록번호: 900101-1234567\n계약금액: 1,200,000원"
    masked = mask_pii(text)
    fields = extract_fields(masked)
    assert fields["contractDate"] == "2026-03-02"
    assert fields["contractAmount"] == 1_200_000


def test_mask_pii_handles_empty_input():
    assert mask_pii("") == ""
    assert mask_pii(None) is None
