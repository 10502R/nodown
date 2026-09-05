# 프로젝트 개발 가이드

## 프로젝트 개요

장기할부 서비스 중단 피해 선제 탐지 및 할부항변 준비 지원 서비스다.
헬스장·필라테스·학원 등 장기 할부 결제 후 가맹점이 폐업한 경우,
카드사가 잠재적 피해 거래를 먼저 탐지하고 소비자의 자료 준비를 지원한다.

## 스택

- 백엔드: Python Flask + Jinja2
- 프론트: HTML/CSS + Vanilla JavaScript + Bootstrap
- 데이터: JSON 합성데이터
- 외부 연동: LLM API, CLOVA OCR API
- 판정: Python 규칙 엔진
- 배포: Render 또는 Vercel

## 폴더 구조

- app.py, requirements.txt, .env
- routes/: 화면 및 API Blueprint
- services/: 거래·OCR·분석·결과 처리
- templates/: Jinja2 화면
- static/: CSS 및 JavaScript
- data/: 합성 거래·사례 데이터
- prompts/: 분석 프롬프트
- tests/: pytest 테스트
- docs/: 역할별 구현 지침

## 역할별 담당

| 역할 | 담당 업무 | 담당 파일 |
| --- | --- | --- |
| A | 거래 탐지, 가맹점 상태 확인, 사례 생성, 규칙 엔진 | routes/detection.py, services/case_service.py, services/rule_service.py |
| B | 소비자 상황 확인, 파일 업로드, OCR, 핵심정보 추출 | routes/evidence.py, services/ocr_service.py |
| C | 분석 API, 시간순 분석, 모순·누락 탐지, 제출자료 내용 | routes/analysis.py, services/llm_service.py, prompts/ |
| D | 전체 디자인, 최종 결과, 제출자료 다운로드, 화면 연결, 배포 | routes/result.py, services/report_service.py, templates/, static/ |

## 공통 규칙

- app.py, requirements.txt는 팀 합의 없이 변경하지 않는다.
- MVP는 실제 카드사 거래 API 대신 합성 거래데이터를 사용한다.
- API 키는 .env에서만 읽고 클라이언트 코드에 노출하지 않는다.
- 규칙 엔진은 확률·위험점수를 만들지 않고 조건과 근거를 그대로 보여준다.
- 최종 인정 여부는 카드사가 결정한다는 안내를 결과 화면에 표시한다.
- 화면·데이터 필드명을 바꿀 때는 다른 담당자에게 먼저 알린다.

## 제출자료 생성 규칙

- 증빙으로 확인되지 않은 값은 절대 추측해서 채우지 않는다. 공란으로 둔다.
- 모든 필드는 source를 가진다: "ocr" | "user" | "unverified"
- unverified 필드는 서식 본문에 출력하지 않고 "추가 확인 항목"으로만 노출한다.
- OCR 폴백이 사용된 경우 fallback_used: true를 컨텍스트에 전달한다.
- 이 모듈은 LLM을 호출하지 않는다. 이미 확정된 데이터를 서식에 배치만 한다.

## 설치와 실행

PowerShell:

    cd nodown
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m pytest -q
    python app.py

A 담당 세부 완료 기준은 docs/A_담당_구현지침.md를 참고한다.
