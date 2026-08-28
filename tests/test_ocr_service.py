from services.ocr_service import (
    FIELD_KEYS,
    SAMPLE_DOCUMENTS,
    allowed_file,
    extract_fields,
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
