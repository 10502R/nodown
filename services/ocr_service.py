# 담당: B
# CLOVA OCR API로 업로드된 증빙자료(계약서, 결제내역 등)에서 텍스트를 추출하고,
# 그 텍스트에서 할부항변 판단에 필요한 핵심 항목을 구조화한다(B-3, B-4).
#
# 주의: 텍스트에 명시되지 않은 값은 임의로 채우지 않고 None(미확인)으로 둔다.

import mimetypes
import os
import re

import requests
from werkzeug.datastructures import FileStorage

CLOVA_OCR_API_URL = os.environ.get("CLOVA_OCR_API_URL")
CLOVA_OCR_SECRET_KEY = os.environ.get("CLOVA_OCR_SECRET_KEY")

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB (B-2 파일 크기 확인)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SAMPLE_EVIDENCE_DIR = os.path.join(DATA_DIR, "sample_evidence")

# 화면 배지에 쓰는 출처 라벨. templates/_ui.html의 source_badge가
# "실제 OCR 결과"를 이미 badge-source-ocr 색상으로 매핑해 두었다.
SOURCE_OCR = "실제 OCR 결과"
SOURCE_USER_INPUT = "실제 사용자 입력"
SOURCE_FIXTURE = "예비 데이터"

FIELD_KEYS = [
    "contractDate",
    "contractAmount",
    "serviceStartDate",
    "serviceEndDate",
    "refundRequestDate",
    "serviceStopDate",
    "replacementServiceOffered",
]

FIELD_LABELS = {
    "contractDate": "계약일",
    "contractAmount": "계약금액",
    "serviceStartDate": "서비스 시작일",
    "serviceEndDate": "서비스 종료일",
    "refundRequestDate": "환불 요청일",
    "serviceStopDate": "서비스 중단일",
    "replacementServiceOffered": "대체 서비스 제공 여부",
}

# B-1. 대표 시연에서 파일 없이 바로 고를 수 있는 합성 증빙자료.
# CASE-001 합성 사례(계약금액 1,200,000원, 폐업일 2026-08-10)와 값을 맞췄다.
# "file"은 data/sample_evidence/의 실제 이미지·PDF 파일명이다. "text"는 그 파일에
# 적힌 내용과 동일한 정답 텍스트로, CLOVA 키가 없어 실제 OCR을 못 돌릴 때만
# 대신 사용한다(임의 추정이 아니라 우리가 직접 만든 파일의 알려진 내용이기 때문).
SAMPLE_DOCUMENTS = {
    "contract": {
        "label": "이용계약서",
        "file": "contract.pdf",
        "text": (
            "헬스장 이용계약서\n\n"
            "계약일: 2026.03.02\n"
            "계약금액: 1,200,000원\n"
            "계약기간: 12개월\n"
            "서비스 시작일: 2026.03.02\n\n"
            "(시연용 합성 자료이며 실제 상호·개인정보를 포함하지 않습니다.)"
        ),
    },
    "refund_sms": {
        "label": "환불 요청 문자",
        "file": "refund_sms.png",
        "text": (
            "[문자 대화]\n"
            "소비자: 헬스장이 문을 닫아서 더 이상 이용을 못 하고 있어요. 환불 요청드립니다.\n"
            "환불 요청일: 2026.08.11\n\n"
            "(시연용 합성 자료)"
        ),
    },
    "closure_notice": {
        "label": "서비스 중단 안내문",
        "file": "closure_notice.png",
        "text": (
            "서비스 중단 안내\n\n"
            "시설 사정으로 2026.08.10부로 서비스를 중단합니다.\n"
            "서비스 중단일: 2026.08.10\n"
            "대체 서비스: 없음\n\n"
            "(시연용 합성 자료)"
        ),
    },
}


def sample_file_path(key):
    """예시문서의 실제 파일 경로를 돌려준다. 없으면 None."""
    doc = SAMPLE_DOCUMENTS.get(key)
    if doc is None:
        return None
    path = os.path.join(SAMPLE_EVIDENCE_DIR, doc["file"])
    return path if os.path.exists(path) else None


def open_sample_file_storage(key):
    """예시문서 파일을 실제 업로드와 동일한 FileStorage 형태로 연다(B-3 경로 재사용).

    호출자가 다 쓴 뒤 닫아야 한다.
    """
    path = sample_file_path(key)
    if path is None:
        return None
    content_type, _ = mimetypes.guess_type(path)
    return FileStorage(
        stream=open(path, "rb"),
        filename=os.path.basename(path),
        content_type=content_type or "application/octet-stream",
    )

_DATE = r"([0-9]{4})[.\-/]([0-9]{1,2})[.\-/]([0-9]{1,2})"

_FIELD_PATTERNS = {
    "contractDate": re.compile(r"계약일\s*[:：]?\s*" + _DATE),
    "contractAmount": re.compile(r"계약\s*금액\s*[:：]?\s*([0-9][0-9,]*)\s*원"),
    "serviceStartDate": re.compile(r"(?:서비스|이용)\s*시작일\s*[:：]?\s*" + _DATE),
    "serviceEndDate": re.compile(r"(?:서비스|이용)\s*(?:종료일|만료일)\s*[:：]?\s*" + _DATE),
    "refundRequestDate": re.compile(r"환불\s*요청일\s*[:：]?\s*" + _DATE),
    "serviceStopDate": re.compile(r"(?:서비스\s*중단일|중단일)\s*[:：]?\s*" + _DATE),
}

_REPLACEMENT_PATTERN = re.compile(r"대체\s*서비스\s*[:：]?\s*(제공|있음|없음|미제공)")


def allowed_file(filename):
    """업로드 가능한 확장자인지 확인한다(B-2)."""
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _text_from_clova_response(payload):
    """CLOVA 일반 OCR 응답(images[].fields[].inferText)에서 줄 단위 텍스트를 만든다."""
    lines = []
    for image in payload.get("images") or []:
        for field in image.get("fields") or []:
            value = field.get("inferText")
            if value:
                lines.append(value)
    return "\n".join(lines)


def extract_text(file_storage):
    """업로드된 파일에서 전체 텍스트를 추출한다(B-3).

    file_storage: Flask request.files의 FileStorage 객체
    반환: (텍스트 또는 None, 상태)
      상태는 "ok" | "not_configured"(API 키 미설정) | "failed"(호출·인식 실패) 중 하나.
    """
    if not CLOVA_OCR_API_URL or not CLOVA_OCR_SECRET_KEY:
        return None, "not_configured"

    files = {"file": (file_storage.filename, file_storage.stream, file_storage.mimetype)}
    headers = {"X-OCR-SECRET": CLOVA_OCR_SECRET_KEY}

    try:
        response = requests.post(CLOVA_OCR_API_URL, headers=headers, files=files, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None, "failed"

    text = _text_from_clova_response(payload)
    if not text:
        return None, "failed"
    return text, "ok"


def _to_iso_date(match):
    year, month, day = match.group(1), match.group(2), match.group(3)
    return "{0}-{1:0>2}-{2:0>2}".format(year, month, day)


def extract_fields(text):
    """OCR 또는 직접 입력된 텍스트에서 핵심 항목을 구조화한다(B-4).

    값이 텍스트에 명시되지 않으면 임의로 채우지 않고 None으로 둔다.
    """
    fields = {key: None for key in FIELD_KEYS}
    if not text:
        return fields

    for key, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            continue
        fields[key] = (
            int(match.group(1).replace(",", "")) if key == "contractAmount" else _to_iso_date(match)
        )

    replacement_match = _REPLACEMENT_PATTERN.search(text)
    if replacement_match:
        fields["replacementServiceOffered"] = replacement_match.group(1) in {"제공", "있음"}

    return fields
