# 태스크 목록 — ExcelBrief for Newsteps

> 각 Phase는 독립 검증 후 다음으로 진행. Phase당 변경 파일 5개 이하 유지.

## Phase 0 — 프로젝트 초기화

- [x] `git init` + 첫 커밋 (계획 문서)
- [x] `pyproject.toml` 작성, 의존성 설치 (버전 잠금 — `requirements.lock`)
- [x] `.env` 정비 — LangSmith 변수명 현행화(`LANGSMITH_*`),
      `MCP_TRANSPORT`/`MCP_HTTP_URL`/`LOCAL_LLM_BASE_URL`/`WORKPAPERS_DIR` 추가
- [x] `data/workpapers/` 생성 + 가상 샘플 조서 배치 (`D-10_매출채권_샘플.xlsx`)

**완료 기준**: `python -c "import langchain, langgraph"` 성공, git 이력 시작.

## Phase 1 — 에이전트 뼈대 + 모델 라우팅

- [x] `src/agent/graph.py` — `create_agent` + `resolve_model()` (anthropic:/local: 분기)
- [x] `src/agent/prompts.py` — 시스템 프롬프트 초안
- [x] `langgraph.json` — graph 진입점 등록
- [x] 스모크 테스트 — 그래프 컴파일·더미 대화 1턴 (4개 통과)

**완료 기준**: `langgraph dev` 기동 → LangGraph Studio(또는 curl)로 대화 성공,
`configurable.model` 변경 시 다른 모델로 응답.

## Phase 2 — auditPaper_MCP 연결

- [x] `src/agent/mcp_client.py` — `MultiServerMCPClient` HTTP 배선
      (HF Space 원격 기본, stdio 로컬 옵션 포함)
- [x] 에이전트에 `standards_*` 3종 도구 노출
- [x] 시스템 프롬프트에 인용 규칙(cid 병기·도구 사용 순서·오류 봉투 대응) 추가
- [x] 통합 테스트 — "수익 인식 5단계 근거 문단은?" → cid 포함 답변 확인 (7개 통과)

**완료 기준**: 기준서 질문에 `KIFRS::1115::31`류 cid 인용이 포함된 답변.

## Phase 3 — Excel 탐색 도구 (TDD)

- [x] 픽스처 — `tests/conftest.py`에서 조서 모사·범용 xlsx를 임시 폴더에 생성
      (바이너리 커밋 대신 코드 생성 방식)
- [x] `tests/test_excel_tools.py` — 도구 4종 + `list_workpapers` 테스트 먼저 작성 (RED)
- [x] `src/agent/tools/excel.py` — 구현 (GREEN): overview / read_range(값·수식,
      500셀 상한) / find / sheet_stats / list_workpapers, 경로 탈출 차단
- [x] 에이전트에 도구 연결 + 탐색 순서 프롬프트 반영 (통합 테스트로 개요 선행 확인)

**완료 기준**: pytest 전체 통과, 에이전트가 샘플 xlsx를 개요→정독 순서로 읽고 설명.

## Phase 3.5 — Excel 도구 v2: 서식·의도 채널 (TDD)

> 설계: [Tool design direction.md](Tool%20design%20direction.md) · Phase 4와 병행 가능,
> **Phase 5(해석 품질 평가) 이전 완료 필수** — 채점 원재료(서식·메모)가 여기서 나옴.

- [x] (선행) openpyxl phonetic 로드 버그 방어 패치 — 한공회 서식 실측으로 발견
- [x] (선행) 테스트를 한공회 공식 조서 서식 기준으로 전환, 가상 샘플 삭제
- [x] (선행) 참조 구현 확보 — `docs/reference/xlsx_agent_tools.py`
      (R1C1 변환기·이탈 휴리스틱·블록 감지 이식원, system_design 4.1)
- [x] read_range `mode="format"` (RED→GREEN) — 색상 3계열(rgb/theme/indexed) 분기
      (theme 분기는 참조 구현에 없어 신규), 프롬프트 탐색 원칙 반영
- [x] `excel_get_annotations` 신설 — 메모·숨김·데이터 유효성·정의된 이름
      (실파일에 없는 요소는 심은 파일 픽스처로 전량 회수 검증)
- [x] `excel_formula_map` 신설 — R1C1 패턴 압축 + 하드코딩 검출 (참조 구현 이식,
      3500 시트 수식 4개→패턴 2종 압축 검증)
- [x] overview 강화 — 값/수식 밀도·시트간 참조·sheet_state + 블록 감지,
      블록 ref → read_range 인계 (에이전트가 실사용 확인)
- [x] 잔손질: 워크북 LRU 캐시·마크다운 파이프 이스케이프·find formulas 모드·
      도구 출력 첫 줄 출처 규약
- [x] 프롬프트 정책 이식 — [검증 원칙] 신설: 수치 주장 셀 주소 인용·암산 금지
      (재조회 검산)·절단 시 범위 축소

**완료 기준**: "색으로 표시된 검토 항목"·"검토자 메모"·"이 시트의 검증 로직"
3개 질문에 셀 주소 근거로 답변. 한공회 서식으로 엔드투엔드 확인.
→ 충족: 색 표시 질문 라이브 확인(3650A 음영을 mode=format 4회로 탐색, 셀 주소 인용),
메모는 심은 파일 테스트로, 검증 로직은 formula_map 단위 테스트로 검증.

## Phase 4 — agent-chat-ui 연동

> 그래프 무변경 원칙: UI는 LangGraph API 클라이언트일 뿐, Phase 1의
> `create_agent` 그래프(assistant id `agent`)에 그대로 붙는다.

### 4a — UI 단독 기동 (리스크 흡수)

- [x] pnpm 설치 (corepack으로 활성화), Node v24 확인
- [x] `ui/`에 braincrew-lab/agent-chat-ui 클론 — **벤더링 결정**
      (`ui/.git` 제거 후 본 저장소에서 소스 직접 추적. 근거: 백로그 xlsx 업로드
      포크 수정을 여기서 추적 + HF 배포 자체완결. upstream: `dfc5430`, 2025-11-13)
- [x] `ui/.env` 설정 (`NEXT_PUBLIC_API_URL=http://localhost:2024`,
      `NEXT_PUBLIC_ASSISTANT_ID=agent`) — 커밋 제외(ui/.gitignore)
- [x] `pnpm dev` 단독 기동 — :3000 HTTP 200, StreamProvider가 env 정상 해석,
      chat-openers 6건 로드 확인

**완료 기준**: 브라우저에서 빈 채팅 화면이 뜬다 (백엔드 연결 전). → 충족

### 4b — 백엔드 연결 엔드투엔드

- [x] `langgraph dev`(:2024) + UI 동시 기동, 조서 해석 대화 1건 완주
      (UI가 쓰는 동일 API 경로 — threads → runs/stream(messages-tuple) — 로 검증:
      3650 조서 질문에 excel_* 7회 + standards_search 4회, 셀 주소 인용 답변)
- [x] **버그 수정**: 스트리밍 병합 시 thinking 블록이 signature만 남아 다음 턴
      재전송에서 Anthropic 400(`thinking.thinking Field required`) —
      `output_version="v1"`(표준 콘텐츠 블록)으로 해결. 비스트리밍(pytest) 경로에선
      재현 안 되던 문제. 전체 테스트 30개 통과 재확인
- [x] 스트리밍(토큰 단위 285 이벤트)·스레드 이어가기("방금 그 조서" 후속 질문이
      문맥 유지)·CORS preflight(:3000 오리진 허용) 확인

**완료 기준**: 브라우저에서 조서 해석 대화가 처음부터 끝까지 동작.
→ 서버측 전 구간 검증 완료, 브라우저 육안 확인만 남음 (사용자 확인 대기)

> **WSL2 주의**: Windows 브라우저 → WSL :2024 직접 접속은 포트 중계가 불안정해
> (Windows 측에 2024 리스너가 안 생기는 사례 실측) UI가 "Failed to connect to
> LangGraph server"를 띄울 수 있다. **해결: UI 내장 API passthrough 사용** —
> `ui/.env`를 `NEXT_PUBLIC_API_URL=http://localhost:3000/api` +
> `LANGGRAPH_API_URL=http://localhost:2024`로 설정하면 브라우저는 :3000만 쓰고
> Next 서버가 내부에서 :2024로 중계한다 (Phase 6 단일 Space 구성과 동일 방식).
> Windows 호스트에서 `/api/info` 200 검증 완료.

### 4c — 브랜딩·커스터마이징

- [x] `settings.yaml`(우선 로드)·`chat-config.yaml` — 앱 이름 "ExcelBrief for Newsteps",
      소개 문구·입력창 placeholder 교체
- [x] `chat-openers.yaml` — 배치된 한공회 조서 5종 기준 예시 질문 6건
- [x] `full-description.md` — 기능 3종·조서 목록·인용 규칙·데모 주의 문구로 전면 교체
- [x] `layout.tsx` — 하드코딩된 탭 타이틀/메타 교체 (tsc·eslint 통과)

**완료 기준**: 첫 화면만 보고 방문자가 무엇을 물어볼지 알 수 있다.
→ 충족: :3000에서 settings/openers(6건)/타이틀 서빙 확인. 브라우저 육안 확인은
4b와 함께 1회로 갈음 (사용자 확인 대기).

## Phase 5 — 해석 품질·평가

- [ ] **(선행) 인용 표기 계층** — 도구 결과 후처리로 cid→표기 문자열(`display`) 생성
      (system_design 5.1절: para_no 특수 케이스 파서 + 픽스처 단위 테스트),
      같은 커밋에서 프롬프트 인용 규칙을 "본문 표기·근거 목록 cid"로 교체
- [ ] 평가용 조서 1건으로 해석 생성 → `해석_{조서번호}.md` 저장
      (평가는 로컬에서, 공개 배치는 가상 조서만)
- [ ] auditPaper_MCP `eval/score_interpretation.py`로 채점, 프롬프트 보완 반복
- [ ] 미완성 조서·범용 Excel 시나리오 점검 (F2·F3 충족 확인)
- [ ] LangSmith 트레이스로 도구 호출 패턴 검토

**완료 기준**: PRD 6절 성공 기준 4항목 전부 충족.

## Phase 6 — HuggingFace Spaces 배포

- [ ] 가상 샘플 조서 2~3건 제작 (실데이터 미사용, 데모 시나리오 커버:
      완성 조서 / 미완성 조서 / 범용 Excel)
- [ ] backend Space — Dockerfile 작성, langgraph 서버 :7860 기동,
      시크릿(ANTHROPIC_API_KEY·MCP_AUTH_TOKEN·LANGSMITH_API_KEY) 설정
- [ ] UI Space — agent-chat-ui Docker 배포, backend URL 연결
      (또는 단일 Space + API passthrough로 택1 — 실측 후 결정)
- [ ] 공개 URL 엔드투엔드 검증 + 포트폴리오용 README
      (데모 링크·아키텍처 다이어그램·사용법·기술 스택)

**완료 기준**: 링크 하나로 채용 담당자가 조서 해석 데모를 체험 가능,
README로 프로젝트 소개 완결 (PRD 성공 기준 5).

## 백로그 (MVP 이후)

- [ ] **(최우선)** UI 포크 수정 — xlsx 업로드 허용 + 서버 저장 경로 연결
      → 방문자가 자기 Excel로 데모 가능해짐
- [ ] SpreadsheetLLM류 압축 인코딩 도구 (초대형 워크북)
- [ ] `read_table`/`query` — DataFrame 등록 + pandas 표현식 계산 위임
      (참조 구현 보유. eval이 공개 Space에서 임의 코드 실행이 되므로 격리 설계 필요)
- [ ] LiteLLM 게이트웨이 — 상용↔로컬 자동 폴백, 사용량 통제
- [ ] 로컬 모델 확정 (vLLM vs Ollama, 모델 선정 벤치마크)
- [ ] 다중 사용자 인증·조서 접근 권한
