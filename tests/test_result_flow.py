# 담당: D
# 8/29 완료 목표 검증: 소개 → 앱 알림 → 상황 선택 → 결과 → 제출자료 흐름이
# 예비 데이터만으로 끊기지 않고 동작하는지 확인한다.

import json
import os

import pytest

from app import create_app
from services import report_service

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    with app.test_client() as test_client:
        yield test_client


def test_예비_픽스처가_모두_존재한다():
    for name in [
        "case.fixture.json",
        "rule-result.fixture.json",
        "submission-draft.fixture.json",
        "analysis-result.fixture.json",
    ]:
        path = os.path.join(DATA_DIR, name)
        assert os.path.exists(path), name
        with open(path, encoding="utf-8") as f:
            json.load(f)


def test_소개화면과_앱알림이_열린다(client):
    assert client.get("/").status_code == 200
    assert client.get("/demo/card-app").status_code == 200


def test_알림에서_상황확인_화면으로_이어진다(client):
    response = client.get("/case/CASE-001")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for choice in report_service.SITUATION_CHOICES:
        assert choice["label"] in body


def test_이용불가_선택은_자료입력_흐름으로_남는다(client):
    response = client.post("/case/CASE-001/situation", data={"situation": "unusable"})
    assert response.status_code == 302
    assert "/case/CASE-001" in response.headers["Location"]
    assert "/guidance" not in response.headers["Location"]


def test_환불완료_선택은_안내화면으로_종료된다(client):
    response = client.post(
        "/case/CASE-001/situation", data={"situation": "refunded"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "할부항변 대상이 아닙니다" in response.get_data(as_text=True)


def test_선택한_상황이_새로고침해도_유지된다(client):
    client.post("/case/CASE-001/situation", data={"situation": "unusable"})
    body = client.get("/case/CASE-001").get_data(as_text=True)
    assert "서비스를 이용하지 못하고 있어요" in body
    assert "자료 입력으로 이동" in body


def test_결과화면이_판정과_근거와_주의문구를_보여준다(client):
    response = client.get("/case/CASE-001/result")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "기본요건" in body
    assert "충족한 조건" in body
    assert "최종 판정은 카드사가 결정합니다." in body
    assert "자동 접수나 결제취소는 수행하지 않습니다." in body


def test_결과화면이_데이터_출처를_표시한다(client):
    body = client.get("/case/CASE-001/result").get_data(as_text=True)
    assert "데이터 출처" in body


def test_제출자료_확인과_수정과_되돌리기(client):
    assert client.get("/case/CASE-001/submission").status_code == 200

    client.post("/case/CASE-001/submission", data={"section-s1": "소비자가 직접 고친 문장이다."})
    body = client.get("/case/CASE-001/submission").get_data(as_text=True)
    assert "소비자가 직접 고친 문장이다." in body

    client.post("/case/CASE-001/submission/reset")
    body = client.get("/case/CASE-001/submission").get_data(as_text=True)
    assert "소비자가 직접 고친 문장이다." not in body


def test_제출자료를_파일로_내려받는다(client):
    response = client.get("/case/CASE-001/download")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "할부항변" in text
    assert "최종 인정 여부는 카드사가 심사합니다." in text


def test_인쇄화면이_열린다(client):
    response = client.get("/case/CASE-001/print")
    assert response.status_code == 200
    assert "인쇄" in response.get_data(as_text=True)


def test_기존_result_경로는_새_경로로_이동한다(client):
    response = client.get("/result/CASE-001")
    assert response.status_code == 302
    assert "/case/CASE-001/result" in response.headers["Location"]


def test_없는_사례는_오류화면을_보여준다(client):
    response = client.get("/case/CASE-999/nope")
    assert response.status_code == 404
    assert "처음 화면으로" in response.get_data(as_text=True)


def test_A와_C가_없어도_예비_데이터로_결과가_만들어진다(monkeypatch):
    """다른 담당자의 서비스가 실패해도 D 화면은 값을 채워야 한다."""

    def boom(*args, **kwargs):
        raise RuntimeError("아직 구현되지 않음")

    monkeypatch.setattr("services.case_service.get_case", boom)
    monkeypatch.setattr("services.rule_service.evaluate", boom)
    monkeypatch.setattr("services.llm_service.analyze_case", boom)

    result = report_service.build_result("CASE-001")
    assert result is not None
    assert result["case_source"] == report_service.SOURCE_FIXTURE
    assert result["verdict_source"] == report_service.SOURCE_FIXTURE
    assert result["verdict"]["verdict"]
    assert result["draft"]["sections"]


def test_상황선택이_규칙엔진_입력에_반영된다():
    case, _ = report_service.load_case("CASE-001")
    merged = report_service.apply_situation(case, "refunded")
    assert merged["refund_completed"] is True
    assert merged["situation_label"] == "전액 환불받았어요"


def test_AI가_연결되지_않으면_제출자료_출처가_예비데이터로_표시된다():
    """API 키 없이 예비 결과를 쓰는 동안 화면이 '실제 AI 결과'라고 말하면 안 된다."""
    result = report_service.build_result("CASE-001")
    assert result["draft"]["source"] == result["analysis_source"]
