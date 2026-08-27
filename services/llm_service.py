# 담당: C
# LLM(OpenAI) 호출, 거래/이용내역 시간순 분석, 모순·누락 탐지, 제출자료 초안 생성.
#
# 주의: LLM은 법적 권리나 할부항변 인정 여부를 최종 판단하지 않는다.
# 판정(3단계)은 services.rule_service의 규칙 엔진만 담당한다.

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


def analyze_case(case_id="CASE-001") -> dict:
    """
    사례의 거래/이용 내역 및 증빙을 분석하여 C-2 8개 키 구조의 dict 반환.
    API 키 미설정 또는 오류 시 Fixture 목업을 안전하게 반환합니다.
    """
    client = _get_client()
    
    # 1. API 키가 없으면 목업 데이터 반환 (현재 개발 단계용)
    if client is None:
        return _load_fixture_result()

    # 2. 실제 OpenAI API 호출 시도
    try:
        prompt_text = _load_prompt("analyze_evidence.txt")
        if not prompt_text:
            prompt_text = _load_prompt("analysis_prompt.txt")

        # 입력 데이터 준비
        input_path = os.path.join(DATA_DIR, "analysis_input.fixture.json")
        evidence_context = ""
        if os.path.exists(input_path):
            with open(input_path, "r", encoding="utf-8") as f:
                evidence_context = f.read()

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
        return _load_fixture_result()


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