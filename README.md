# nodown

장기할부 서비스 중단 피해를 선제 탐지하고, 소비자의 할부항변 자료 준비를 돕는 Flask MVP다.

## 빠른 시작

PowerShell에서 실행한다.

    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m pytest -q
    python app.py

브라우저에서 http://127.0.0.1:5000/ 을 연다.

## 주요 화면

전체 흐름은 아래 순서로 이어진다.

- 서비스 소개: /
- 거래 탐지: /detection/
- 카드사 앱 알림: /demo/card-app
- 소비자 상황 확인: /case/CASE-001
- 자료 입력: /evidence/
- AI 분석: /analysis/
- 결과: /case/CASE-001/result
- 제출자료: /case/CASE-001/submission

## 담당별 지침

- A(거래 탐지·규칙): docs/A_담당_구현지침.md
- D(사용자 흐름·결과·배포): docs/D_담당_구현지침.md

공통 레이아웃과 디자인 규칙은 templates/base.html, templates/_ui.html,
static/css/style.css에 있다. 새 화면을 만들 때는 이 세 파일을 그대로 사용한다.

## 주의

- 화면 시연 데이터는 모두 합성 데이터다.
- 실제 카드사 거래 API와 실제 가맹점 상태 API는 연결하지 않는다.
- API 키는 .env에만 설정한다.
- 규칙 엔진은 법적 최종 판단을 하지 않으며 최종 인정 여부는 카드사가 결정한다.
