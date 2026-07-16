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

> LangSmith 트레이스 해부 관찰 (2026-07-16, MCP로 직접 조회):
> ① 82.9초 대화에서 LLM 시간이 84%(최종 답변 생성만 39.9초) — excel 도구는 0.1초 미만,
>   standards_search만 회당 8.5~8.7초(원격 MCP)이나 병렬 호출로 상쇄되고 있음.
> ② 도구 호출 순서·병렬화는 프롬프트 정책대로 동작, 중복 호출 없음.
> ③ 오류 트레이스 2건뿐: thinking 400(수정 완료), GraphRecursionError(limit 15 도달,
>   Phase 2 시절 1건) — 도구 다연발 질문에서 재발 가능, recursion_limit 상향 검토.
> ④ ls_max_tokens=4096 — 긴 조서 해설 절단 위험, 상향 검토.
> ⑤ 답변 서두 영어 혼입("Now I have all...") 2례 → 프롬프트 서두 규칙으로 대응(아래).
> ⑥ ~~프롬프트 캐싱 미적용~~ → **해결**: 요청 최상위 `cache_control`(자동 캐싱)을
>   model_kwargs로 전달. 실측 — 2라운드부터 cache_read 6.3k→6.9k 증분 확대,
>   입력의 87%가 캐시 히트(해당 토큰 90% 할인). 대화 접두 전체가 캐시됨.
>
> 인용 표기 계층 실전 검증(2026-07-16 04:52 대화): display 주입·본문 cid 미노출·
> 말미 근거 목록(표기+cid)·한국어 서두 — 전 규칙 준수 확인.

- [x] **(선행) 인용 표기 계층** — `src/agent/citations.py`: cid→표기 문자열(`display`)
      순수 함수 + para_no 특수 케이스(BC·IE사례·부록·정의-용어·A접두) 파서,
      `mcp_client._with_displays()` 래퍼로 standards_* 3종 결과에 주입
      (픽스처 단위 테스트 16개 + 라이브 주입 확인, 전체 46개 통과).
      같은 커밋에서 프롬프트 인용 규칙을 "본문 표기·근거 목록 cid"로 교체,
      답변 서두 한국어 시작 규칙 추가(관찰 ⑤ 대응)
- [x] 평가용 조서 해석 생성 → `reports/해석_3650.md`·`해석_3900A.md`
      (골드셋 교차: 4000P-1은 골드 제작 원본 시트(별도 4000P-1 조서)가 배치
      워크북에 없어 무효 판정 — P 시트엔 1115만 명시, 1002·1024·1036 부재 확인)
- [x] `eval/score_interpretation.py` 채점·프롬프트 보완 반복 — **둘 다 recall 1.0**
      - 3650: 0.8 → 1.0. 원인: 본문에서 언급한 기준서(330)·지침(2018-3)을 도구
        확인 없이 남겨 cid 누락 → [인용 규칙] "번호 특정 언급 시 그 문서 문단
        최소 1건 확인" 추가
      - 3900A: 0.33 → 1.0. 원인 2건: ① 조서가 명시 인용(A57)한 570·705를
        701 문단 15 재인용으로 갈음 → [탐색 원칙] 명시 참조 회수 규칙 +
        [답변 형식] ⑤ 직전 자가 점검(본문 등장 번호 전수 대조) 추가 — 추상
        규칙 2회는 실패, **행동 체크리스트로 바꾸자 통과**. ② max_tokens 4096
        절단으로 근거 목록 미도달(관찰 ④ 실증) → resolve_model 8192로 상향
      - 회귀: 프롬프트 최종본으로 3650·3900A 재실행 모두 1.0, pytest 46개 통과
- [x] 미완성 조서·범용 Excel 시나리오 점검 (F2·F3 충족 확인) — Phase 6에서
      제작한 데모 조서로 사후 검증: 미완성 조서(데모 5400)는 조회 미회신·
      공란 시트·검토 미완을 짚고 KSA 505/K-IFRS 1109 원문 확인 후 추가 절차
      제안, 범용 Excel(예산집행 현황)은 감사조서 아님을 판별해 기준 인용 없이
      구조·수식·시트간 대사 요약 (reports/해석_데모*.md)
- [x] LangSmith 트레이스로 도구 호출 패턴 검토 — 탐색 순서·병렬 배칭·중복 없음
      확인(관찰 노트 ①②). **부수 발견·수정**: `_with_displays`가 내부에서
      `tool.ainvoke`를 재호출해 논리적 1회가 tool run 2개(래퍼+원본)로 기록되던
      이중 트레이싱 → 원본 coroutine 직접 호출(content_and_artifact 튜플 처리)로
      수정, 단위 테스트 3개 추가 + 실전 트레이스에서 1건 기록 확인 (49개 통과)

**완료 기준**: PRD 6절 성공 기준 4항목 전부 충족.

## Phase 6 — HuggingFace Spaces 배포

- [x] 가상 샘플 조서 3건 제작 (실데이터 미사용, 데모 시나리오 커버:
      완성 조서 / 미완성 조서 / 범용 Excel)
      - `scripts/make_demo_workpapers.py` → data/workpapers/에 생성:
        데모조서_5300 현금및현금성자산(완성 — 틱마크·범례·검토서명·tie-out·
        KSA 330/505·K-IFRS 1007 참조), 데모조서_5400 매출채권 작성중(미완성 —
        조회 미회신 5건·대손충당금 시트 공란·검토란 공란·KSA 505/K-IFRS 1109),
        데모_부서별 예산집행 현황(범용)
      - openpyxl은 수식 캐시 값을 못 쓰므로 저장 후 sheet XML의 <v>에 계산값
        주입(openpyxl이 미리 쓴 빈 <v/> 재사용) — 값 모드 판독 실측 확인
- [x] 배포 구조 확정: **단일 Space + API passthrough** (로컬 검증 완료 방식 재사용)
      - 루트 `Dockerfile`: 2-스테이지 — node로 UI standalone 빌드 →
        python:3.12-slim 런타임에 node 바이너리만 복사, `start.sh`가
        langgraph 서버(:2024) 준비 대기 후 UI(:7860) 기동
      - `NEXT_PUBLIC_API_URL=/api` 상대 경로 빌드 — normalizeApiUrl이
        window.location.origin과 결합해 어떤 도메인에서든 동작 (실측 확인)
      - 로컬 검증: standalone server.js에 LANGGRAPH_API_URL 런타임 주입 →
        /api/info·/api/assistants/search 중계 확인 (Docker는 WSL에 없어
        이미지 빌드 자체는 HF 빌더에서 검증)
      - `deploy/hf_space/{README.md,Dockerfile}`: auditPaper_MCP와 동일한
        "Space가 GitHub 리포를 clone" 패턴 — 웹 UI로 Space 생성 후 두 파일만
        업로드, 시크릿(ANTHROPIC_API_KEY·MCP_AUTH_TOKEN·LANGSMITH_API_KEY) 설정
- [x] 포트폴리오용 README.md (아키텍처 mermaid·평가 결과·기술 스택·로컬 실행법)
      + `.env.example` 신설
- [x] 공개 URL 엔드투엔드 검증 — hf CLI(HF_TOKEN, .env)로 전 과정 자동화:
      `toddl/excelbrief` **Private** Space 생성, deploy/hf_space 2파일 업로드,
      시크릿 3종+LANGSMITH_TRACING 설정, 빌드(RUNNING) 확인
      - start.sh 실측: langgraph 서버 5초 준비 → Next.js :7860 기동
      - Private 상태 검증(Bearer HF_TOKEN): /api/info 중계 200, UI 루트 200,
        기준서 RAG 대화(KSA::505::7 원문 확인·cid 반환), 조서 8건 목록 정상
      - README 데모 링크(toddl/excelbrief)와 실제 URL 일치 — 수정 불요
      **visibility 운영**: 개발 중 private → 제출 기간 protected(PRO 전용,
      앱만 공개·소스 비공개·복제 불가) 또는 public → 종료 후 private 복귀.
      전환: `hf repos settings toddl/excelbrief --type space --protected`
      - **Private 열람 시 흰 화면 이슈 (해결)**: hub 페이지 iframe의 인증
        쿠키(`?__sign` JWT → hf.space 쿠키)가 서드파티 쿠키 차단에 걸려
        JS/CSS가 비인증 404(HF 404 페이지 3KB)로 떨어짐. 브라우저 쿠키
        예외(`huggingface.co`) 추가로 해결. **소유자가 private 상태로 볼
        때만 발생** — protected/public 방문자는 인증 쿠키가 불필요해 무관.
        진단법: 헤드리스 크로미움 + Bearer HF_TOKEN으로 직접 URL 렌더링
        (앱 정상 확인) → 404 크기 3.1KB = 비인증 응답 대조
      - **비용 통제(제출 전 필수)**: Anthropic Console 워크스페이스 지출
        한도 설정 — protected여도 링크 소지자는 무제한 사용 가능하므로

**완료 기준**: 링크 하나로 채용 담당자가 조서 해석 데모를 체험 가능,
README로 프로젝트 소개 완결 (PRD 성공 기준 5).

## 백로그 (MVP 이후)

- [x] **(최우선)** UI 포크 수정 — 문서 업로드 허용 + 서버 저장 경로 연결 (2026-07-16)
      → 방문자가 자기 Excel/Word로 데모 가능해짐
    - 지원 형식: xlsx·xlsm·xls·docx (사용자 요청으로 xls·docx까지 확대)
    - 백엔드: `.xls`는 xlrd→openpyxl 변환으로 기존 excel_* 도구가 투명하게 동작
      (수식·서식·메모 없음 — 도구가 안내 문구 반환), `.docx`는 `read_document`
      신규 도구(python-docx, 문단·표→마크다운, 20k자 상한)
    - 업로드 경로: Next.js `/api/upload`(nodejs 런타임, 정적 라우트라 catch-all
      프록시보다 우선) → `WORKPAPERS_DIR` 저장. 파일명 새니타이즈, 기존 파일과
      충돌 시 " (1)" 접미사(데모 조서 덮어쓰기 방지), 20MB 상한, 확장자 화이트리스트
    - 프런트: 문서 파일은 base64 인라인 대신 선택 즉시 업로드 → 입력창 위 칩 표시,
      전송 시 `[첨부 파일: 저장파일명]` 텍스트를 메시지에 덧붙임(시스템 프롬프트가
      이 표기를 도구 path로 쓰도록 안내). 업로드 중 전송 버튼 비활성
    - 검증: pytest 56건 통과(신규 test_document_tools.py 7건 포함), tsc·eslint
      깨끗, next build 성공, curl 업로드 4케이스, 실제 에이전트 대화에서
      첨부 docx를 read_document로 읽어 답변 확인
    - 유의: HF Space 파일시스템은 휘발성 — 업로드 파일은 Space 재시작 시 사라짐
      (데모 용도로 허용)
    - Space 배포 검증(커밋 9194704, factory rebuild): /api/upload 저장·형식 거부
      정상, 에이전트가 업로드 docx를 read_document로 읽어 답변 완주. 검증 후
      일반 재시작으로 테스트 업로드 파일 제거. 참고: HF 프록시가 SSE 응답의
      content-type 헤더를 제거해 langgraph_sdk 스트리밍은 TransportError가 나지만
      curl/브라우저(fetch)는 정상 — SDK로 Space를 칠 때는 raw HTTP 사용
- [ ] SpreadsheetLLM류 압축 인코딩 도구 (초대형 워크북)
- [ ] `read_table`/`query` — DataFrame 등록 + pandas 표현식 계산 위임
      (참조 구현 보유. eval이 공개 Space에서 임의 코드 실행이 되므로 격리 설계 필요)
- [ ] LiteLLM 게이트웨이 — 상용↔로컬 자동 폴백, 사용량 통제
- [ ] 로컬 모델 확정 (vLLM vs Ollama, 모델 선정 벤치마크)
- [ ] 다중 사용자 인증·조서 접근 권한
