import pytest

from services import ocr_service


@pytest.fixture(autouse=True)
def _isolate_from_real_clova_credentials(monkeypatch):
    """테스트는 .env에 실제 CLOVA 키가 있어도 실제 API를 호출하면 안 된다.

    실제 키로 호출하면 네트워크에 의존하고 API 사용량이 소모되며, 키가 없거나
    네트워크가 없는 환경에서는 테스트가 깨진다. 개별 테스트가 필요하면
    monkeypatch로 직접 값을 다시 설정해 명시적으로 검증한다.
    """
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_API_URL", None)
    monkeypatch.setattr(ocr_service, "CLOVA_OCR_SECRET_KEY", None)
