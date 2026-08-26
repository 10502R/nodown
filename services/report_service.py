# 담당: D
# 최종 결과 화면 데이터 구성 및 제출자료 다운로드 파일 생성.

import os
import tempfile

from services import case_service, llm_service, rule_service

REPORTS_DIR = os.path.join(tempfile.gettempdir(), "nodown_reports")


def build_result(case_id):
    case = case_service.get_case(case_id)
    if case is None:
        return None

    verdict = rule_service.evaluate(case)
    return {
        "case": case,
        "verdict": verdict,
    }


def build_report_file(case_id):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    content = llm_service.generate_report_content(case_id) or ""

    file_path = os.path.join(REPORTS_DIR, f"{case_id}_report.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path
