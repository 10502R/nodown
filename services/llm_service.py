# 담당: C
# LLM(OpenAI) 호출, 거래/이용내역 시간순 분석, 모순·누락 탐지, 제출자료 초안 생성.
#
# 주의: LLM은 법적 권리나 할부항변 인정 여부를 최종 판단하지 않는다.
# 판정(3단계)은 services.rule_service의 규칙 엔진만 담당한다.

import os

from openai import OpenAI

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        _client = OpenAI(api_key=api_key)
    return _client


def _load_prompt(filename, **kwargs):
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, encoding="utf-8") as f:
        template = f.read()
    return template.format(**kwargs)


def analyze_case(case_id):
    """사례의 거래/이용 내역을 시간순으로 분석하여 모순/누락 사항을 찾아낸다."""
    from services import case_service

    case = case_service.get_case(case_id)
    if case is None:
        return None

    prompt = _load_prompt("analysis_prompt.txt", case=case)
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def generate_report_content(case_id):
    """할부항변 제출자료 초안 텍스트를 생성한다."""
    from services import case_service

    case = case_service.get_case(case_id)
    if case is None:
        return None

    prompt = _load_prompt("report_prompt.txt", case=case)
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
