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

## Phase 4 — agent-chat-ui 연동

- [ ] `ui/`에 braincrew-lab/agent-chat-ui 클론, `.env` 설정
      (`NEXT_PUBLIC_API_URL=http://localhost:2024`, `NEXT_PUBLIC_ASSISTANT_ID`)
- [ ] `public/chat-config.yaml`·`chat-openers.yaml` — 명칭·시작 문구 커스터마이징
- [ ] 백엔드↔UI 엔드투엔드 확인 (스트리밍, 스레드 이어가기)

**완료 기준**: 브라우저에서 조서 해석 대화가 처음부터 끝까지 동작.

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
- [ ] LiteLLM 게이트웨이 — 상용↔로컬 자동 폴백, 사용량 통제
- [ ] 로컬 모델 확정 (vLLM vs Ollama, 모델 선정 벤치마크)
- [ ] 다중 사용자 인증·조서 접근 권한
