from app import create_app


def test_detection_screen_shows_all_synthetic_transactions():
    client = create_app().test_client()

    response = client.get("/detection/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "올데이 피트니스" in body
    assert "사례 생성" in body
    assert "합성 데이터 시연" in body


def test_case_creation_api_returns_case_url():
    client = create_app().test_client()

    response = client.post("/api/cases", json={"transactionId": "TX-1003"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["caseId"] == "CASE-001"
    assert body["caseUrl"] == "/detection/CASE-001"
    assert body["isSynthetic"] is True


def test_prepared_case_detail_continues_to_situation_confirm():
    client = create_app().test_client()

    response = client.get("/detection/CASE-001")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "/case/CASE-001" in body
    assert "상황 확인으로 이동" in body
    assert "증빙자료 입력으로 이동" not in body


def test_case_creation_api_rejects_normal_business():
    client = create_app().test_client()

    response = client.post("/api/cases", json={"transactionId": "TX-1005"})

    assert response.status_code == 400
    assert "알림 대상 거래" in response.get_json()["error"]
