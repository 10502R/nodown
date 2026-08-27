# D 담당 구현 지침 (사용자 흐름·결과·배포)

8월 29일 목표인 `각 기능이 예비 데이터로 독립 작동`까지 구현한 내용을 정리한다.
A·B·C의 기능이 없거나 실패해도 D의 화면은 `data/*.fixture.json`만으로 끝까지 동작한다.

## 1. 화면과 URL

| 단계 | URL | 템플릿 | 담당 |
| --- | --- | --- | --- |
| 서비스 소개 | `/` | `templates/index.html` | D |
| 거래 탐지 | `/detection/` | `templates/detection.html` | A |
| 카드사 앱 알림 | `/demo/card-app` | `templates/card_app.html` | D |
| 소비자 상황 확인 | `/case/<case_id>` | `templates/case_confirm.html` | D |
| 대상 아님 안내 | `/case/<case_id>/guidance` | `templates/case_guidance.html` | D |
| 자료 입력 | `/evidence/` | `templates/evidence.html` | B |
| AI 분석 | `/analysis/` | `templates/analysis.html` | C |
| 결과 | `/case/<case_id>/result` | `templates/result.html` | D |
| 제출자료 | `/case/<case_id>/submission` | `templates/submission.html` | D |
| 인쇄·PDF | `/case/<case_id>/print` | `templates/submission_print.html` | D |
| 내려받기 | `/case/<case_id>/download` | — | D |
| 시나리오 시작 | `/demo/start` | — | D |

기존 `/result/<case_id>`와 `/result/<case_id>/download`는 새 주소로 넘어가도록 남겨 두었다.

## 2. 공통 UI 규칙 (D-1)

다른 팀원은 새 색상값이나 배지를 직접 만들지 말고 아래를 쓴다.

- 레이아웃: `templates/base.html`을 `{% extends %}` 한다.
- 공통 조각: `{% from "_ui.html" import source_badge, step_bar, notice, nav_buttons %}`
  - `source_badge(출처문자열)` — 데이터 출처 배지
  - `step_bar(단계번호)` — 진행 단계 표시
  - `nav_buttons(prev_url, prev_label, next_url, next_label)` — 이전·다음 버튼
- 단계 표시를 띄우려면 `render_template(..., active_step=N)`을 넘긴다. (1 탐지 → 7 제출자료)
- 색상·여백·카드·모바일 규격: `static/css/style.css`의 `--nd-*` 변수와 `.nd-card`, `.nd-kv` 사용.
- 로딩·오류: `window.nodown.showLoading(문구)`, `window.nodown.showError(제목, 내용)`.
  링크나 폼에 `data-loading="문구"`를 붙이면 자동으로 로딩 화면이 뜬다.
- 404·500 화면은 `templates/error.html`로 통일했다.

## 3. 데이터 출처 표시 (D-7)

`services/report_service.py`의 상수를 쓴다.

| 상수 | 화면 표시 |
| --- | --- |
| `SOURCE_SYNTHETIC_TRANSACTION` | 합성 카드거래 |
| `SOURCE_MOCK_API` | API 명세 기반 합성 응답 |
| `SOURCE_USER_INPUT` | 실제 사용자 입력 |
| `SOURCE_AI` | 실제 AI 분석 결과 |
| `SOURCE_RULE_ENGINE` | 규칙 엔진 판정 |
| `SOURCE_FIXTURE` | 예비 데이터 |

조회 함수는 모두 `(데이터, 출처)`를 함께 반환한다. API 키가 없어 예비 결과가 나온
경우에는 `실제 AI 분석 결과`가 아니라 `예비 데이터`로 표시된다.

## 4. 소비자 상황 분기 (D-4)

| 선택지 | 규칙 엔진에 넣는 값 | 다음 화면 |
| --- | --- | --- |
| 더 이상 서비스를 이용하지 못하고 있음 | 중단 O, 이용 X, 환불 X, 대체 X, 귀책 X | 자료 입력 |
| 이미 환불받았음 | 환불 완료 O | 안내 후 종료 |
| 다른 지점에서 정상 이용 중임 | 대체 서비스 O, 이용 O | 안내 후 종료 |
| 정확히 모르겠음 | 값을 채우지 않음(미확인 유지) | 확인사항 안내 후 자료 입력 |

선택값과 제출자료 수정본은 브라우저 세션에만 저장한다. 서버에 사례를 남기지 않으며
새로고침해도 화면이 유지된다.

## 5. 심사위원용 검증 절차 (D-9)

| 단계 | 조작 | 예상 결과 |
| --- | --- | --- |
| 1 | 배포 URL 접속 | 서비스 소개 화면. 상단에 시연용 합성데이터 안내 띠가 보인다. |
| 2 | `대표 시나리오 시작` 클릭 | 카드사 앱 알림 화면. 알림 카드 2건이 보인다. |
| 3 | `거래 탐지` 메뉴 클릭 | 합성 거래 12건과 조건별 통과·제외 사유가 보인다. |
| 4 | 앱 알림 카드 클릭 | CASE-001 상황 확인 화면. 거래정보와 선택지 4개가 보인다. |
| 5 | `더 이상 서비스를 이용하지 못하고 있음` 선택 | 선택이 저장되고 자료 입력 이동 버튼이 나타난다. |
| 6 | 자료 입력 화면에서 예시문서 선택 | OCR 또는 예비 결과로 계약일·금액·기간이 표시된다. |
| 7 | AI 분석 실행 | 시간순 정리, 확인된 사실, 모순·누락 항목이 표시된다. |
| 8 | 결과 화면 확인 | 3단계 판정, 충족·미충족·미확인 조건, 주의문구가 보인다. |
| 9 | 제출자료 확인 후 내려받기 | 초안을 수정할 수 있고 텍스트 파일과 인쇄·PDF 저장이 동작한다. |

비교 시나리오는 `이미 환불받았음`을 선택해 안내 후 종료되는 화면(단계 5 대체)과
CASE-002(증빙 없음 → `추가자료 확인 필요`)로 확인한다.

## 6. 전체 연결 테스트 (D-10)

`tests/test_result_flow.py`가 아래를 자동으로 확인한다.

- 소개 → 앱 알림 → 상황 확인 → 결과 → 제출자료가 모두 200으로 열리는지
- 상황 선택이 분기(자료 입력 / 안내 종료)대로 이동하는지
- 새로고침해도 선택한 상황이 유지되는지
- 제출자료 수정·되돌리기·내려받기·인쇄가 동작하는지
- 없는 주소에서 오류 화면이 뜨는지
- A·C의 서비스가 예외를 던져도 예비 데이터로 결과가 만들어지는지

실행:

    .venv\Scripts\python.exe -m pytest tests/test_result_flow.py -q

수동으로 확인할 항목은 다음과 같다.

- 모바일 폭 375px에서 가로 스크롤이 생기지 않는지 (현재 전 화면 통과)
- 인쇄 화면에서 상단 메뉴와 버튼이 인쇄되지 않는지
- 로딩 화면이 뒤로가기 후 남아 있지 않는지

## 7. 배포 (D-8)

- `Procfile`, `render.yaml`을 추가해 두었다. Render에서 저장소를 연결하면
  `gunicorn app:app`으로 실행된다.
- 환경변수는 Render 대시보드의 Environment 탭에서 등록한다.
  `FLASK_SECRET_KEY`, `OPENAI_API_KEY`, `CLOVA_OCR_API_URL`, `CLOVA_OCR_SECRET_KEY`.
  저장소에는 어떤 키도 넣지 않는다.
- `FLASK_SECRET_KEY`를 실제 값으로 넣어야 상황 선택이 세션에 유지된다.
- Render 무료 인스턴스는 일정 시간 요청이 없으면 잠들었다가 첫 요청에서 느리게 뜬다.
  심사 직전에는 미리 한 번 접속해 둔다.
- Vercel로 배포할 경우 Python 런타임이 베타이고 요청·응답 4.5MB 제한이 있으므로,
  B의 업로드 파일 크기를 3MB 이하로 제한해야 한다.

계정 생성과 실제 배포는 사람이 직접 진행해야 한다. 배포 URL이 나오면 이 문서에 적는다.

배포 URL: (미정)

## 8. 다음 단계 (8/30 통합에서 확인할 것)

- B의 자료 입력 화면이 `case_id` 질의문자열을 받아 사례를 유지하는지
- C의 분석 결과 키 이름(`timeline`, `missingEvidence`, `submissionSummary`)이 그대로인지
- A의 사례 생성 API가 만든 신규 `case_id`로도 `/case/<case_id>` 흐름이 열리는지
