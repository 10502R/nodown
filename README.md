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

- 거래 탐지: /detection/
- 사례 상세: /detection/CASE-001
- 증빙자료: /evidence/
- 분석: /analysis/
- 결과: /result/CASE-001

## A 담당 지침

A의 구현 범위, 데이터 계약, API, 테스트 체크리스트는 docs/A_담당_구현지침.md에 정리되어 있다.

## 주의

- 화면 시연 데이터는 모두 합성 데이터다.
- 실제 카드사 거래 API와 실제 가맹점 상태 API는 연결하지 않는다.
- API 키는 .env에만 설정한다.
- 규칙 엔진은 법적 최종 판단을 하지 않으며 최종 인정 여부는 카드사가 결정한다.
