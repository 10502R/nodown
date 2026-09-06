# B→A 연동: routes/evidence.py에 쌓인 증빙이 A의 규칙 엔진 입력(case_service/
# rule_service)에 실제로 반영되는지 확인한다. case_service.py와 rule_service.py는
# 건드리지 않고 report_service.apply_evidence()가 세션 증빙을 case에 병합한다.

from app import create_app

# CASE-002는 demo_cases.json 기준 evidence_files가 빈 배열이라
# 증빙 등록 전/후 차이를 관찰하기에 적합하다.
CASE_ID = "CASE-002"


def _client():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    return app.test_client()


def test_verdict_condition_flips_to_passed_after_evidence_is_registered():
    client = _client()

    before = client.get("/case/{0}/result".format(CASE_ID)).get_data(as_text=True)
    failed_header_idx = before.find("충족하지 않은 조건")
    evidence_idx_before = before.find("증빙자료 확보 여부")
    assert failed_header_idx != -1 and evidence_idx_before > failed_header_idx, (
        "증빙 등록 전에는 '증빙자료 확보 여부'가 미충족 목록에 있어야 한다"
    )

    response = client.post(
        "/evidence/{0}/sample".format(CASE_ID),
        data={"sample_key": "contract"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    after = client.get("/case/{0}/result".format(CASE_ID)).get_data(as_text=True)
    assert "충족하지 않은 조건" not in after, "증빙 등록 후에는 미충족 조건이 없어야 한다"
    assert "증빙자료 확보 여부" in after


def test_submission_attachments_reflect_registered_evidence_not_fixture():
    client = _client()

    before = client.get("/case/{0}/submission".format(CASE_ID)).get_data(as_text=True)
    assert "헬스장 이용계약서(합성)" in before  # 고정 fixture 첨부 목록

    client.post(
        "/evidence/{0}/sample".format(CASE_ID),
        data={"sample_key": "contract"},
        follow_redirects=True,
    )

    after = client.get("/case/{0}/submission".format(CASE_ID)).get_data(as_text=True)
    assert "헬스장 이용계약서(합성)" not in after
    assert "이용계약서 (contract.pdf)" in after


def test_situation_answer_takes_priority_over_evidence_for_replacement_flag():
    """소비자가 상황 확인에서 이미 답했다면 증빙에서 추출된 값으로 덮어쓰지 않는다."""
    client = _client()

    # '다른 지점에서 정상 이용 중이에요' -> replacement_service_offered = True
    client.post(
        "/case/{0}/situation".format(CASE_ID),
        data={"situation": "normal_use"},
        follow_redirects=True,
    )
    # closure_notice 문서는 '대체 서비스: 없음' -> replacementServiceOffered = False
    client.post(
        "/evidence/{0}/sample".format(CASE_ID),
        data={"sample_key": "closure_notice"},
        follow_redirects=True,
    )

    body = client.get("/case/{0}/result".format(CASE_ID)).get_data(as_text=True)
    assert "대체 서비스 미제공 여부" in body
    # 상황 확인 답변(True)이 유지됐다면 '대체 서비스 제공됨'을 근거로 미충족 처리된다.
    assert "충족하지 않은 조건" in body
