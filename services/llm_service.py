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

# C-2 출력 형식: 반드시 있어야 하는 8개 키와 타입.
_REQUIRED_LIST_KEYS = (
    "timeline",
    "confirmedFacts",
    "userClaims",
    "unresolvedItems",
    "contradictions",
    "missingEvidence",
    "followUpQuestions",
)
_REQUIRED_STR_KEY = "submissionSummary"
_NO_CONTRADICTION_TEXT = "확인된 모순 없음"


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
    # analysis_prompt.txt 등에는 JSON 예시 { "timeline": ... } 중괄호가 있어
    # template.format(**kwargs)를 쓰면 KeyError가 난다. {case} 플레이스홀더만 치환한다.
    if "case" in kwargs:
        case_value = kwargs["case"]
        if isinstance(case_value, dict):
            case_text = json.dumps(case_value, ensure_ascii=False, indent=2)
        elif case_value is None:
            case_text = ""
        else:
            case_text = str(case_value)
        template = template.replace("{case}", case_text)
    return template


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


def _is_valid_analysis_shape(data):
    """LLM이 반환한 JSON이 C-2 형식(list 7개 + str 1개, 총 8개 키)을 만족하는지 검사한다.

    키가 없거나 타입이 다르면 False. 내부용 키(예: "_source")는 이 8키 검사
    대상이 아니므로 여기서는 보지도, 지우지도 않는다.
    """
    if not isinstance(data, dict):
        return False
    for key in _REQUIRED_LIST_KEYS:
        if not isinstance(data.get(key), list):
            return False
    return isinstance(data.get(_REQUIRED_STR_KEY), str)


def _normalize_analysis(data):
    """검증을 통과한 분석 결과(또는 신뢰할 수 있는 픽스처)를 화면에 보이기 좋은
    형태로 다듬는다. 현재는 contradictions 하나만 다룬다: None이거나 빈 배열이면
    표준 문구로 채우고, 이미 모순 내용이 있는 리스트는 그대로 둔다(새로 만들거나
    지우지 않음).
    """
    if not data.get("contradictions"):
        data["contradictions"] = [_NO_CONTRADICTION_TEXT]
    return data


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
    userClaims(주장) 수준으로만 추가한다.

    submissionSummary에도 반영해야 templates/submission.html(제출자료 초안)에
    실제로 보인다 — submission.html은 userClaims를 보지 않고 submissionSummary만
    report_service._sections_from_summary로 절 단위로 나눠 쓰기 때문이다. 라디오
    답변(예/아니오/모르겠음)은 "질문: 답변" 목록 문단으로, 자유 서술(extra_note)은
    별도 문단으로 나눠 붙여서 각각 새 절이 되게 한다.
    """
    if not answers:
        result = _normalize_analysis(result)
        result["_source"] = "fixture"
        return result

    result = copy.deepcopy(result)
    result = _normalize_analysis(result)
    answer_label = {"yes": "예", "no": "아니오", "unknown": "모르겠음"}

    answer_items = [
        item for item in (answers.get("answers") or [])
        if (item.get("question") or "").strip() and item.get("answer") in answer_label
    ]

    claims = [
        "추가 확인 질문 '{0}'에 대해 소비자는 '{1}'라고 답변했습니다.".format(
            item["question"].strip(), answer_label[item["answer"]]
        )
        for item in answer_items
    ]
    if claims:
        result["userClaims"] = (result.get("userClaims") or []) + claims

    summary = result.get("submissionSummary") or ""

    if answer_items:
        answer_lines = ["추가 확인 질문에 대한 소비자 답변:"]
        answer_lines += [
            "- {0}: {1}".format(item["question"].strip(), answer_label[item["answer"]])
            for item in answer_items
        ]
        summary = "{0}\n\n{1}".format(summary, "\n".join(answer_lines)).strip()

    extra_note = (answers.get("extra_note") or "").strip()
    if extra_note:
        summary = "{0}\n\n소비자가 추가로 설명한 내용: {1}".format(summary, extra_note).strip()

    result["submissionSummary"] = summary
    result["_source"] = "fixture"
    return result


def _append_extra_note(result, answers):
    """실제 AI 응답에도 소비자 보충 설명을 빠뜨리지 않고 붙인다.

    모델이 followUpAnswers를 무시해도 7번 칸에 적은 글이 제출 요약에 남게 한다.
    이미 같은 문장이 있으면 중복해서 붙이지 않는다.
    """
    extra_note = ((answers or {}).get("extra_note") or "").strip()
    if not extra_note:
        return result
    summary = result.get("submissionSummary") or ""
    if extra_note in summary:
        return result
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

    반환 dict에는 내부용 "_source" 키("ai" 또는 "fixture")가 함께 실려 있다.
    답변 병합으로 폴백(fixture) 결과의 값이 원본 fixture와 달라져도
    services/report_service.build_analysis가 출처를 "실제 AI 분석 결과"로
    잘못 표시하지 않도록, 값 비교 대신 이 플래그로 출처를 판정하게 하기 위함이다.
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
        prompt_text = _load_prompt("analyze_evidence.txt", case=case)
        if not prompt_text:
            prompt_text = _load_prompt("analysis_prompt.txt", case=case)

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
        parsed = json.loads(response.choices[0].message.content)
        if not _is_valid_analysis_shape(parsed):
            raise ValueError(
                "LLM 응답이 C-2 형식(8개 키/타입)을 만족하지 않습니다: {0!r}".format(
                    sorted(parsed.keys()) if isinstance(parsed, dict) else type(parsed)
                )
            )
        parsed = _normalize_analysis(parsed)
        parsed["_source"] = "ai"
        return _append_extra_note(parsed, answers)
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