# 담당: D
# 사용자 흐름 전체를 잇는 서비스 계층이다.
#
# 이 모듈의 원칙은 하나다: A(사례·규칙), B(OCR), C(AI)의 기능이 아직 없거나
# 실패해도 D의 화면은 예비 데이터(data/*.fixture.json)로 끝까지 동작해야 한다.
# 그래서 모든 조회 함수는 (데이터, 출처라벨) 형태로 반환하고, 화면은 그 출처를
# 그대로 표시한다. 심사위원이 어떤 값이 실제 기능이고 어떤 값이 예비 데이터인지
# 화면에서 바로 구분할 수 있게 하기 위함이다.

import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
REPORTS_DIR = os.path.join(tempfile.gettempdir(), "nodown_reports")

# 데이터 출처 표시(D-7)
SOURCE_SYNTHETIC_TRANSACTION = "합성 카드거래"
SOURCE_MOCK_API = "API 명세 기반 합성 응답"
SOURCE_USER_INPUT = "실제 사용자 입력"
SOURCE_RULE_ENGINE = "규칙 엔진 판정"
SOURCE_AI = "실제 AI 분석 결과"
SOURCE_FIXTURE = "예비 데이터"

FINAL_DECISION_NOTICE = "최종 판정은 카드사가 결정합니다."

# 결과 화면 주의문구(D-5)
DISCLAIMERS = [
    "이 서비스는 AI로 자료를 정리할 뿐 최종 법률 판단을 하지 않습니다.",
    "할부항변 인정 여부는 카드사가 심사하여 결정합니다.",
    "자동 접수나 결제취소는 수행하지 않습니다.",
    "화면에 표시되는 거래·문서는 모두 시연용 합성데이터입니다.",
]

# 소비자 상황 확인 화면의 선택지와 분기(D-4)
SITUATION_CHOICES = [
    {
        "key": "unusable",
        "label": "더 이상 서비스를 이용하지 못하고 있음",
        "next": "evidence",
        "guidance": "할부항변 기본요건을 확인할 수 있는 상황입니다. 계약서와 환불 요청 기록을 준비해 주세요.",
        "answers": {
            "service_discontinued": True,
            "service_used_after_closure": False,
            "refund_completed": False,
            "replacement_service_offered": False,
            "consumer_fault": False,
        },
    },
    {
        "key": "refunded",
        "label": "이미 환불받았음",
        "next": "end",
        "guidance": (
            "이미 환불이 완료된 거래는 할부항변 대상이 아닙니다. "
            "카드 명세서에서 취소·환불 내역이 실제로 반영되었는지 확인해 주세요."
        ),
        "answers": {"refund_completed": True},
    },
    {
        "key": "normal_use",
        "label": "다른 지점에서 정상 이용 중임",
        "next": "end",
        "guidance": (
            "대체 서비스를 정상적으로 이용 중이라면 할부항변 대상이 아닙니다. "
            "이용 조건이 계약과 다르다면 가맹점에 먼저 확인해 주세요."
        ),
        "answers": {"replacement_service_offered": True, "service_used_after_closure": True},
    },
    {
        "key": "unknown",
        "label": "정확히 모르겠음",
        "next": "evidence",
        "guidance": (
            "다음 세 가지를 먼저 확인해 주세요. "
            "1) 가맹점에서 환불·대체 서비스 안내를 받았는지 "
            "2) 카드 명세서에 취소 내역이 있는지 "
            "3) 최근에 시설을 이용한 적이 있는지. "
            "확인이 어려우면 가지고 있는 자료를 먼저 올려 주세요."
        ),
        "answers": {},
    },
]

SITUATION_BY_KEY = {choice["key"]: choice for choice in SITUATION_CHOICES}


def _load_fixture(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def get_situation(key):
    return SITUATION_BY_KEY.get(key)


# --- 사례 ---------------------------------------------------------------

def load_case(case_id):
    """사례 한 건을 A의 서비스에서 읽고, 실패하면 예비 사례를 사용한다."""
    try:
        from services import case_service

        case = case_service.get_case(case_id)
        if case is not None:
            return deepcopy(case), SOURCE_SYNTHETIC_TRANSACTION
    except Exception:
        pass

    fixture = _load_fixture("case.fixture.json")
    if fixture is None:
        return None, SOURCE_FIXTURE

    case = deepcopy(fixture)
    case["case_id"] = case_id or case.get("case_id")
    return case, SOURCE_FIXTURE


def list_alert_cases():
    """앱 알림 시뮬레이션에 띄울 사례 목록을 만든다."""
    try:
        from services import case_service

        cases = case_service.list_detected_cases()
        if cases:
            return deepcopy(cases), SOURCE_SYNTHETIC_TRANSACTION
    except Exception:
        pass

    fixture = _load_fixture("case.fixture.json")
    return ([deepcopy(fixture)] if fixture else []), SOURCE_FIXTURE


def apply_situation(case, situation_key):
    """소비자가 고른 상황을 사례에 덮어써 규칙 엔진 입력으로 넘긴다."""
    if case is None:
        return None

    situation = SITUATION_BY_KEY.get(situation_key)
    if situation is None:
        return case

    merged = deepcopy(case)
    merged.update(deepcopy(situation["answers"]))
    merged["situation_key"] = situation_key
    merged["situation_label"] = situation["label"]
    return merged


def _evidence_display_name(document):
    label = document.get("label") or "증빙자료"
    filename = document.get("filename")
    if filename and filename not in label:
        return "{0} ({1})".format(label, filename)
    return label


def apply_evidence(case, documents):
    """B가 모은 증빙자료를 사례에 반영한다(B→A 연동).

    규칙 엔진의 '증빙자료 확보 여부' 조건이 실제 등록된 자료를 보도록
    evidence_files를 채운다. 소비자가 상황 확인에서 이미 답한 값이 있으면
    그 값을 우선하고, 비어 있을 때만 증빙에서 추출된 값으로 채운다.
    """
    if case is None or not documents:
        return case

    merged = deepcopy(case)
    merged["evidence_files"] = [_evidence_display_name(doc) for doc in documents]

    if merged.get("replacement_service_offered") is None:
        for doc in documents:
            value = (doc.get("fields") or {}).get("replacementServiceOffered")
            if value is not None:
                merged["replacement_service_offered"] = value
                break

    return merged


# --- 규칙 판정 ----------------------------------------------------------

def build_verdict(case):
    """A의 규칙 엔진을 호출하고, 실패하면 예비 판정 결과를 사용한다."""
    try:
        from services import rule_service

        verdict = rule_service.evaluate(case)
        if verdict and verdict.get("condition_items"):
            return verdict, SOURCE_RULE_ENGINE
    except Exception:
        pass

    fixture = _load_fixture("rule-result.fixture.json")
    if fixture is None:
        return {
            "verdict": "추가자료 확인 필요",
            "condition_items": [],
            "missing_conditions": [],
            "failed_conditions": [],
            "final_decision_notice": FINAL_DECISION_NOTICE,
        }, SOURCE_FIXTURE
    return deepcopy(fixture), SOURCE_FIXTURE


def verdict_tone(verdict_text):
    """판정 문구를 화면 색상 등급으로 바꾼다."""
    if not verdict_text:
        return "secondary"
    if "가능성 있음" in verdict_text:
        return "success"
    if "어려움" in verdict_text:
        return "danger"
    return "warning"


def split_conditions(verdict):
    """판정 근거를 충족·미충족·미확인으로 나눈다(D-5)."""
    items = (verdict or {}).get("condition_items") or []
    return {
        "passed": [item for item in items if item.get("value") is True],
        "failed": [item for item in items if item.get("value") is False],
        "unknown": [item for item in items if item.get("value") is None],
    }


# --- AI 분석 ------------------------------------------------------------

def build_analysis(case_id):
    """C의 분석 결과를 읽고, 실패하면 예비 분석 결과를 사용한다."""
    fixture = _load_fixture("analysis-result.fixture.json") or {}
    try:
        from services import llm_service

        analysis = llm_service.analyze_case(case_id)
        if analysis:
            # [C 수정 전 원본 — report_service.py 원작성자 D] 아래 줄로 대체됨
            # llm_service는 키가 없으면 같은 예비 데이터를 반환하므로 값을 비교해
            # 실제 AI 결과인지 예비 결과인지 구분한다.
            # source = SOURCE_FIXTURE if analysis == fixture else SOURCE_AI
            #
            # [C 추가] llm_service가 반환하는 _source 플래그로 출처를 판정한다.
            # 폴백(fixture) 응답이 답변 병합(7번 "추가 확인 질문" 저장값 반영)으로
            # fixture와 값이 달라져도 출처가 "실제 AI 분석 결과"로 잘못 표시되지
            # 않도록 하기 위함이다. 아래 원본 비교식(analysis == fixture)은
            # _source가 없는 이전 반환값과의 하위호환용으로만 남겨둔다.
            source_flag = analysis.pop("_source", None)
            if source_flag == "ai":
                source = SOURCE_AI
            elif source_flag == "fixture":
                source = SOURCE_FIXTURE
            else:
                source = SOURCE_FIXTURE if analysis == fixture else SOURCE_AI
            return deepcopy(analysis), source
    except Exception:
        pass

    return deepcopy(fixture), SOURCE_FIXTURE


# --- 제출자료 초안 ------------------------------------------------------

def build_submission_draft(case_id, case=None, analysis=None, overrides=None,
                           analysis_source=None):
    """제출자료 초안을 절 단위로 만든다.

    C의 submissionSummary가 있으면 그 문단을 절로 나눠 쓰고, 없으면 예비
    초안을 쓴다. overrides는 소비자가 화면에서 직접 고친 본문이다.
    """
    fixture = _load_fixture("submission-draft.fixture.json") or {"sections": [], "attachments": []}
    draft = deepcopy(fixture)
    draft["case_id"] = case_id

    if analysis is None:
        analysis, analysis_source = build_analysis(case_id)
    elif analysis_source is None:
        # 호출자가 출처를 알려주지 않으면 예비 데이터인지 직접 확인한다.
        fixture_analysis = _load_fixture("analysis-result.fixture.json") or {}
        analysis_source = SOURCE_FIXTURE if analysis == fixture_analysis else SOURCE_AI
    summary = (analysis or {}).get("submissionSummary") or ""

    sections = _sections_from_summary(summary)
    if sections:
        draft["sections"] = sections
        draft["source"] = analysis_source
    else:
        draft["source"] = SOURCE_FIXTURE

    if case:
        draft["merchant_name"] = case.get("merchant_name")
        if case.get("evidence_files"):
            draft["attachments"] = list(case["evidence_files"])

    if overrides:
        for section in draft["sections"]:
            edited = overrides.get(section["key"])
            if edited is not None and edited.strip():
                section["body"] = edited.strip()
                section["edited"] = True
        draft["source"] = SOURCE_USER_INPUT

    draft["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return draft


def _sections_from_summary(summary):
    """`거래정보: ...` 형태의 문단을 절 목록으로 바꾼다."""
    sections = []
    for index, paragraph in enumerate(p.strip() for p in (summary or "").split("\n\n")):
        if not paragraph:
            continue
        first_line = paragraph.split("\n", 1)[0]
        if ":" in first_line:
            heading, body = paragraph.split(":", 1)
            heading, body = heading.strip(), body.strip()
        else:
            heading, body = "항목 {0}".format(index + 1), paragraph
        sections.append({"key": "s{0}".format(index + 1), "heading": heading, "body": body})
    return sections


def render_submission_text(draft):
    """내려받기·인쇄용 평문을 만든다."""
    lines = [
        draft.get("title", "할부항변권 행사 요청서(초안)"),
        "사례번호: {0}".format(draft.get("case_id", "")),
        "작성일시: {0}".format(draft.get("generated_at", "")),
        "",
        "※ 이 문서는 제출 준비용 초안입니다. 최종 인정 여부는 카드사가 심사합니다.",
        "※ 시연용 합성데이터로 작성된 문서입니다.",
        "",
    ]
    for section in draft.get("sections", []):
        lines.append("[{0}]".format(section["heading"]))
        lines.append(section["body"])
        lines.append("")

    attachments = draft.get("attachments") or []
    if attachments:
        lines.append("[첨부자료]")
        lines.extend("- {0}".format(item) for item in attachments)
        lines.append("")

    return "\n".join(lines)


# --- 화면 데이터 조립 ---------------------------------------------------

def build_result(case_id, situation_key=None, overrides=None, evidence=None):
    """결과 화면 한 장에 필요한 값을 모두 모은다.

    evidence는 B가 세션에 쌓은 증빙 문서 목록이다(routes/result.py가 전달).
    """
    case, case_source = load_case(case_id)
    if case is None:
        return None

    case = apply_situation(case, situation_key) or case
    case = apply_evidence(case, evidence) or case
    verdict, verdict_source = build_verdict(case)
    analysis, analysis_source = build_analysis(case_id)
    draft = build_submission_draft(
        case_id, case=case, analysis=analysis, overrides=overrides,
        analysis_source=analysis_source,
    )

    return {
        "case": case,
        "case_source": case_source,
        "verdict": verdict,
        "verdict_source": verdict_source,
        "verdict_tone": verdict_tone(verdict.get("verdict")),
        "conditions": split_conditions(verdict),
        "analysis": analysis,
        "analysis_source": analysis_source,
        "draft": draft,
        "situation": SITUATION_BY_KEY.get(situation_key),
        "disclaimers": DISCLAIMERS,
        "final_decision_notice": verdict.get("final_decision_notice", FINAL_DECISION_NOTICE),
    }


def build_report_file(case_id, situation_key=None, overrides=None, evidence=None):
    """제출자료 초안을 파일로 저장하고 경로를 돌려준다."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    result = build_result(
        case_id, situation_key=situation_key, overrides=overrides, evidence=evidence
    )
    content = render_submission_text(result["draft"]) if result else ""

    file_path = os.path.join(REPORTS_DIR, "{0}_submission_draft.txt".format(case_id))
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path
