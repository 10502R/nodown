# 담당: C
# LLM(OpenAI) 호출, 거래/이용내역 시간순 분석, 모순·누락 탐지, 제출자료 초안 생성.
#
# 주의: LLM은 법적 권리나 할부항변 인정 여부를 최종 판단하지 않는다.
# 판정(3단계)은 services.rule_service의 규칙 엔진만 담당한다.

import copy
import json
import os
from openai import OpenAI

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        _client = OpenAI(api_key=api_key)
    return _client


def _load_prompt(filename, **kwargs):
    path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        template = f.read()
    return template.format(**kwargs)


def _load_fixture_result():
    """data/analysis-result.fixture.json 데이터를 로드하여 dict로 반환"""
    fixture_path = os.path.join(DATA_DIR, "analysis-result.fixture.json")
    if os.path.exists(fixture_path):
        try:
            with open(fixture_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[llm_service] 픽스처 로드 실패: {e}")
    return {
        "timeline": [],
        "confirmedFacts": ["증빙 데이터를 불러오는 중입니다."],
        "userClaims": [],
        "unresolvedItems": [],
        "contradictions": ["확인된 모순 없음"],
        "missingEvidence": [],
        "followUpQuestions": [],
        "submissionSummary": "분석 데이터를 준비 중입니다."
    }


def _build_evidence_context(case, evidence, answers=None):
    """AI에 넘길 증빙 컨텍스트를 만든다.

    evidence(B가 세션에 쌓은 문서 목록)가 있으면 C-1 형식
    {"case", "documents", "extractedFields", "rawTexts"}으로 실제 자료를 조립한다.
    없으면(해당 사례에 아직 B의 자료가 없으면) 기존처럼 정적 예시 입력을 쓴다.

    answers(소비자가 7번 섹션에서 저장한 추가 확인 질문 답변)가 있으면 두 경우 모두
    "followUpAnswers" 키로 함께 실어 보낸다. 소비자 답변은 객관적 증빙이 아니므로
    프롬프트(analysis_prompt.txt)에서 confirmedFacts가 아닌 userClaims 수준으로만
    취급하도록 안내한다.
    """
    if evidence:
        try:
            from services import ocr_service

            ai_input = ocr_service.to_ai_input(evidence)
        except Exception:
            ai_input = {"documents": [], "extractedFields": {}, "rawTexts": []}
        payload = {"case": case or {}, **ai_input}
        if answers:
            payload["followUpAnswers"] = answers
        return json.dumps(payload, ensure_ascii=False, indent=2)

    input_path = os.path.join(DATA_DIR, "analysis_input.fixture.json")
    if os.path.exists(input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            raw = f.read()
        if answers:
            try:
                payload = json.loads(raw)
                payload["followUpAnswers"] = answers
                return json.dumps(payload, ensure_ascii=False, indent=2)
            except (ValueError, TypeError):
                return raw
        return raw
    return ""


def _apply_answers_to_fixture(result, answers):
    """API 키가 없거나 호출이 실패해 픽스처로 폴백할 때도, 저장된 답변이 있으면
    최소한으로 반영한다. 새로운 사실을 만들어내지 않도록 소비자 답변은
    userClaims(주장) 수준으로만 추가하고, 보충 설명은 submissionSummary 끝에
    참고용 한 줄로 덧붙인다.
    """
    if not answers:
        return result

    result = copy.deepcopy(result)
    answer_label = {"yes": "예", "no": "아니오", "unknown": "모르겠음"}

    claims = []
    for item in answers.get("answers") or []:
        question = (item.get("question") or "").strip()
        answer = item.get("answer")
        if not question or answer not in answer_label:
            continue
        claims.append(
            "추가 확인 질문 '{0}'에 대해 소비자는 '{1}'라고 답변하였다.".format(
                question, answer_label[answer]
            )
        )
    if claims:
        result["userClaims"] = (result.get("userClaims") or []) + claims

    extra_note = (answers.get("extra_note") or "").strip()
    if extra_note:
        summary = result.get("submissionSummary") or ""
        result["submissionSummary"] = "{0}\n\n소비자가 추가로 설명한 내용: {1}".format(
            summary, extra_note
        ).strip()

    return result


def analyze_case(case_id="CASE-001", case=None, evidence=None, answers=None) -> dict:
    """
    사례의 거래/이용 내역 및 증빙을 분석하여 C-2 8개 키 구조의 dict 반환.
    API 키 미설정 또는 오류 시 Fixture 목업을 안전하게 반환합니다.

    case: A의 사례 정보(dict). evidence: B가 세션에 쌓은 증빙 문서 목록.
    answers: 소비자가 7번 "추가 확인 질문" 섹션에서 저장한 답변
    ({"answers": [{"question": ..., "answer": "yes"|"no"|"unknown"}], "extra_note": "..."}).

    evidence와 answers가 둘 다 None으로 들어오면(즉 services/report_service.py처럼
    case_id만으로 호출한 경우) 요청 컨텍스트가 있을 때 세션에서 두 값을 직접 찾아
    채운다. 이렇게 하면 D의 호출부(report_service.build_analysis)를 바꾸지 않아도
    같은 사례의 증빙·답변이 결과 화면·제출자료에도 그대로 반영된다.
    셋 다 없으면 정적 예시 입력으로 동작한다(하위 호환).
    """
    if evidence is None and answers is None:
        try:
            from flask import has_request_context, session

            if has_request_context():
                evidence = session.get("evidence:{0}".format(case_id))
                answers = session.get("followup_answers:{0}".format(case_id))
        except RuntimeError:
            # 요청 컨텍스트 밖(스크립트/배치 호출 등)에서는 세션을 읽을 수 없으므로
            # 조용히 무시하고 기존 동작(정적 예시 입력)을 그대로 따른다.
            pass

    client = _get_client()

    # 1. API 키가 없으면 목업 데이터 반환 (현재 개발 단계용)
    if client is None:
        return _apply_answers_to_fixture(_load_fixture_result(), answers)

    # 2. 실제 OpenAI API 호출 시도
    try:
        prompt_text = _load_prompt("analyze_evidence.txt")
        if not prompt_text:
            prompt_text = _load_prompt("analysis_prompt.txt")

        evidence_context = _build_evidence_context(case, evidence, answers)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": f"다음 증빙 자료를 분석해줘:\n{evidence_context}"}
            ],
            temperature=0.1,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[llm_service] API 호출 또는 파싱 에러 (Fallback 실행): {e}")
        return _apply_answers_to_fixture(_load_fixture_result(), answers)


def generate_report_content(case_id="CASE-001"):
    """할부항변 제출자료 초안 텍스트를 생성한다."""
    try:
        from services import case_service
        case = case_service.get_case(case_id)
    except Exception:
        case = None

    client = _get_client()
    if client is None or case is None:
        return _load_fixture_result().get("submissionSummary", "")

    prompt = _load_prompt("report_prompt.txt", case=case)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content