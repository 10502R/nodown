# 담당: B
# CLOVA OCR API를 호출해 업로드된 증빙자료(계약서, 결제내역 등)에서 텍스트를 추출한다.

import os

import requests

CLOVA_OCR_API_URL = os.environ.get("CLOVA_OCR_API_URL")
CLOVA_OCR_SECRET_KEY = os.environ.get("CLOVA_OCR_SECRET_KEY")


def extract_text(file_storage):
    """업로드된 파일에서 텍스트를 추출한다.

    file_storage: Flask request.files의 FileStorage 객체
    반환: 추출된 텍스트/필드 딕셔너리 (실패 시 None)
    """
    if not CLOVA_OCR_API_URL or not CLOVA_OCR_SECRET_KEY:
        return None

    files = {"file": (file_storage.filename, file_storage.stream, file_storage.mimetype)}
    headers = {"X-OCR-SECRET": CLOVA_OCR_SECRET_KEY}

    response = requests.post(CLOVA_OCR_API_URL, headers=headers, files=files, timeout=30)
    response.raise_for_status()
    return response.json()
