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
- [x] `eval/score_interpretation.py` 채점·프롬프트 보완 반복
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
진행 순서 (2026-07-17 사용자 결정):
① UI 마이그레이션(최우선 — 새 오픈소스 UI로 교체, 대상 리포는 착수 시 지정)
→ ② read_table/query → ③ 그 효과를 본 뒤 압축 인코딩 필요성 재평가

- [x] UI 마이그레이션 (2026-07-17) — ui/를
      [langgraph-chat-ui](https://github.com/braincrew-lab/langgraph-chat-ui)
      (teddynote-lab 계열, agent-chat-ui의 확장판) frontend로 통째 교체.
      standalone 인증 모드(DB·NextAuth 미사용), ko 로케일. 얻은 것: 스레드
      사이드바(저장·이름변경·삭제)·툴 호출 시각화·서브그래프 노드 추적·다크 테마
    - Phase 1(a273f85): 벤더링 교체 + passthrough 확인(클라이언트가 항상
      origin+/api 호출, 서버가 LANGGRAPH_API_URL로 중계 — 기존 구조와 동일)
    - Phase 2(8bc7d36·cbd0b93): 커스텀 자산 이식 — /api/models+ModelSelector
      (submit 시 localStorage에서 읽어 config 주입, useMessageSubmit 6지점+
      human.tsx 편집 재전송), 조서 업로드는 **/api/workpapers**로 개명
      (벤더의 /api/upload은 스키마 폼 URL 모드용이라 분리), 문서 칩·[첨부 파일:] 규약
    - Phase 3(26a7b42): 브랜딩은 site.ts 하나가 아니라 **DEFAULT_SETTINGS
      (types/global-settings.ts)와 i18n defaults(ko/en.json)가 폴백 체인으로
      덮는다** — 3곳 모두 교체해야 적용(실측). 예시 질문은 WelcomeScreen에
      CHAT_STARTERS 버튼으로, full-description.md는 사용 안내 다이얼로그로 이식
    - Phase 4(71b06d3): Dockerfile — pnpm install --ignore-scripts 후 전체 COPY,
      pnpm build가 prisma generate 포함(standalone 모드는 런타임에 Prisma 미사용,
      빌드 타입용으로만 필요). openssl 설치. AUTH_MODE 등 빌드·런타임 양쪽 주입
    - 함정: features/chat/components/index.tsx(Thread)는 **미사용 죽은 코드** —
      실제 트리는 ChatContent→ThreadContent→useMessageSubmit. 배선은 후자에
    - 함정: Space는 deploy/hf_space/Dockerfile의 **Space 리포 사본**으로 빌드 —
      GitHub만 갱신하면 BUILD_ERROR. hf upload로 Space에도 올려야 반영
- [ ] 미이식(필요 시): 구 UI의 설정 yaml 3종은 site.ts/DEFAULT_SETTINGS로 대체됨.
      스타터 클릭은 입력창 채움 방식(구 UI는 즉시 전송이었는지 미확인)
- [x] `excel_load_table`/`excel_query_table` (2026-07-17) —
      awesome-llm-apps/For_me/langgraph_data_analysis_agent의 DataStore 이식.
      시트 범위를 in-memory DuckDB(`data` 테이블)로 등록하고 읽기 전용 SQL로
      집계·필터·검산. pandas eval 위임 대신 **SQL 화이트리스트**로 RCE 문제 해소
    - 격리 2중: sqlglot AST 검증(단일 SELECT/WITH만, DDL/DML·타 테이블·
      read_*/scan/glob 함수 차단) + DuckDB `enable_external_access=false`
      (엔진 수준 파일·URL 차단 — read_csv('/etc/passwd') 실측 차단)
    - 원본의 plan/revise 그래프 루프는 채택 안 함 — create_agent ReAct 루프가
      "오류: …" 텍스트를 받아 SQL 자가 수정 (기존 도구 방침과 동일)
    - 한글 열명 보존 정규화("금액(원)"→"금액_원", 큰따옴표 인용) — 원본의
      ASCII 전용 정규화는 한글 헤더가 전부 column_N이 돼 부적합(실측)
    - 함정: pandas 3은 문자열 열의 None을 NaN으로 바꿈 — `v is None` 판정이면
      혼합 열 강등 시 "nan" 문자열 생성·null 집계 0 (pd.isna로 판정해야 함)
    - e2e(Haiku): overview→read_range→load_table→query_table 순서로 자발 사용,
      한글 열명 인용 GROUP BY SQL 작성, 근거 범위(시트!범위) 병기 확인
- [x] CSV 입력 지원 (2026-07-17) — `_load_csv`가 CSV를 값 전용 단일 시트
      워크북으로 변환(.xls 변환과 같은 접근)해 모든 Excel 도구·표 SQL·그래프가
      무수정 동작. 시트명은 파일 stem(금지문자 치환·31자 절단)
    - 인코딩: utf-8-sig → cp949 순 시도 (한국 실무 CSV는 cp949가 흔함, 실측
      테스트), 구분자는 csv.Sniffer(,;탭|) 폴백 excel
    - 타입: int→float→문자열 보수 추론 (콤마 천단위 서식은 건드리지 않음 —
      "1,234"는 문자열 유지)
    - UI: 업로드 허용 확장자·오류 문구·accept 속성·사용 안내에 csv 추가
- [x] `analyst` 별도 그래프 (2026-07-17) — 원본의 고정 워크플로(inspect→
      plan_sql→validate→execute→answer + revise 루프 최대 2회)를 채팅용으로
      각색해 두 번째 그래프로 등록 (UI 그래프 셀렉터가 다중 그래프 설계라는
      사용자 결정). 도구(tools/table.py)의 DataStore 계층을 그대로 재사용
    - 원본과 차이: 입력이 question이 아니라 messages — 대상 파일은
      "[첨부 파일: …]" 표기·파일명 언급에서 탐지, 표는 가장 큰 값-블록을
      자동 선택(시트명 언급 시 한정). 제목 행(값 1개) 스킵 휴리스틱 포함
    - 모델은 메인 그래프와 동일하게 configurable.model 라우팅.
      진행 상황은 custom stream(_emit)으로 방출
- [x] `reviewer` 조서검토 전용 그래프 (2026-07-17) — 조서 완성도 점검
      (절차 누락·서명란·tie-out 검산)을 고정 워크플로로 분리.
      locate → collect(비LLM 증거: overview·formula_map·annotations·서명란
      스캔·최대 블록 정독) → assess(LLM 1회, Pydantic 구조화 소견, 재시도 1회)
      → report(결정적 템플릿 렌더, ①~⑦ 섹션·심각도 정렬)
    - 서명란 스캔(비LLM): 작성자/검토자 표지 셀(30자 이하)을 찾아 같은 셀
      콜론 뒤·오른쪽·아래 값으로 채움/공란 판정
    - 함정: 약한 모델(Haiku 실측)이 Finding 객체 대신 문자열 리스트를 반환 —
      field_validator(mode="before")로 문자열을 Finding으로 승격해 흡수
    - 한계 고지 내장: 기준서 인용은 안 함(도구 없음) — agent 그래프 안내.
      e2e(Haiku, 데모조서 5400 작성중): 미완성 5420 시트·검토 서명 공란·
      하드코딩 잠정치·리드↔조회서 464.8백만 차이 검출 확인
    - graph_common.py: analyst와 공유하는 메시지 파싱·파일 탐지 헬퍼 추출
- [ ] SpreadsheetLLM류 압축 인코딩 도구 (초대형 워크북) — ②의 효과 확인 후 재평가
      (참조 구현 보유. eval이 공개 Space에서 임의 코드 실행이 되므로 격리 설계 필요)
- [x] 멀티 벤더 모델 선택 (2026-07-16) — LiteLLM 게이트웨이 대신 langchain
      `init_chat_model` 접두사 라우팅으로 구현 (별도 게이트웨이 프로세스 불필요)
    - 백엔드: resolve_model에 `openai:`·`google_genai:` 라우트 추가
      (langchain-google-genai 의존성). GEMINI_API_KEY/GOOGLE_API_KEY 둘 다 인식
    - UI: 모델 드롭다운(ModelSelector) + `/api/models`(벤더 API 키가 설정된
      모델만 노출, 레지스트리는 ui/src/lib/models.ts) + 전송 시
      `configurable.model` 주입, localStorage 유지
    - 검증: GPT-5.1/GPT-5 mini/Gemini(-latest 별칭) 실호출 + list_workpapers
      도구 호출 확인. Gemini 2.5는 지원 종료라 -latest 별칭 채택
    - Space 배포(커밋 00e8d8f): OPENAI_API_KEY·GEMINI_API_KEY를 Space 시크릿으로
      추가(사용자 승인) → 드롭다운 6종 노출(Local은 의도대로 숨김), Gemini 실응답
      확인. 방문자가 세 벤더 키의 사용량을 소비하므로 각 벤더 지출 한도 설정 권장
    - 오픈모델 공개 데모(2026-07-16, 사용자 선택 "옵션 3"): GPU Space(t4-small
      $0.40/h) 대신 **HF Inference Providers 라우터** 채택 — `hf:<org/model>`
      라우트(router.huggingface.co/v1, OpenAI 호환). Qwen3.6-27B·gpt-oss-120b
      도구 호출 검증 완료. ZeroGPU는 Gradio SDK 전용이라 Docker Space 불가(실측 조사)
    - 함정: CLI용 HF_TOKEN(write)에는 Inference Providers 호출 권한이 없어 403 —
      fine-grained **HF_INFERENCE_TOKEN**(Inference Providers 권한만) 별도 발급
    - 사고·수정(2026-07-16): 사용자가 Space에서 gpt-oss-120b로 docx 브리핑 요청 시
      React #185 크래시. 근본 원인은 서버측 — gpt-oss가 standards_search의
      source_type에 리스트 대신 문자열을 넘겨 _MCPToolExecutionError로 **런 전체
      사망**(스레드 status=error), UI 크래시는 그 오류 스트림의 2차 증상.
      수정: mcp_client._run이 예외를 "오류: …" 텍스트로 변환해 모델이 자가
      수정하게 함 (excel 도구와 동일 방침). 실측: gpt-oss가 같은 실수 후
      ["감사기준"]으로 고쳐 재호출, KSA::505 인용 완주. Claude는 스키마를
      정확히 지켜 그간 드러나지 않았던 문제 — 약한 모델일수록 필수 방어
- [x] 로컬 모델 지원 (2026-07-16) — Ollama 채택. WSL2에 0.20.0이 systemd 서비스로
      **이미 설치돼 있었음**(:11434, 재설치 불필요). qwen3:8b pull(도구 호출 지원,
      RTX 3080 8GB 적재). 기존 `local:` 라우트(OpenAI 호환 :11434/v1) 그대로 사용
    - 함정: Ollama 기본 num_ctx 4096 < 시스템 프롬프트+도구(4.2k 토큰) →
      입력 절단으로 빈 응답. `PARAMETER num_ctx 16384` 파생 모델
      **qwen3:8b-16k**를 만들어 해결 (레지스트리 spec도 이것)
    - gemma3:4b도 있었으나 Ollama에서 도구 호출 미지원이라 배제
- ~~다중 사용자 인증·조서 접근 권한~~ — 계획에서 삭제 (2026-07-16, 사용자 결정)

## 그래프 다듬기 세션 (2026-07-17 오후) — 4그래프 체제 완성·배포

- [x] analyst 다듬기 — ① 질문의 명시 범위(`시트명!A1:C50`, 단일 시트면 범위만)
      를 자동 블록 선택보다 우선 (함정: `\w`가 밑줄을 단어 문자로 취급 —
      `[\W_]` 분리 필요) ② triage→chat/analysis 분기(LLM 분류 1회, 실패 시
      파일 언급 휴리스틱 폴백) ③ 대화 맥락 주입 — messages는 쌓이고 있었지만
      분석 경로가 최신 질문만 써서 스레드에서 기억상실처럼 동작(원본 단발
      질문 구조의 이식 잔재). conversation_context(최근 6개×600자)를
      triage·plan·answer에 주입. e2e: "그중 매출이 가장 큰 도시"를 이전 턴
      맥락에서 해석해 WHERE 절 생성
- [x] reviewer 다듬기 — ① triage→chat/review 분기 ② investigate 노드
      (미니 ReAct, Excel 도구 5종, 라운드 3·호출 6 상한) — 기본 증거 부족분만
      보충 조사 ③ cite 노드(LLM 없음) — assess가 소견별로 낸
      standards_query·source_hint로 search→get_paragraph 재확인 인용
      (소견 간 asyncio.gather 병렬, 실패는 인용 생략 강등) ④ 서명란 스캔을
      증거 선두로(절단 보호) ⑤ 점검 범위(점검/생략 시트) 결정적 렌더
      ⑥ 근거 위치를 사람 표기로("시트의 무엇(셀주소)") — 프롬프트/스키마 단
      ⑦ chat에 기준서 MCP 미니 ReAct(라운드 3·호출 4) — 맥락 인용 재전달은
      도구 없이, 새 인용은 도구 확인 후만
    - 함정: async 노드의 동기 파일 I/O(list_workpapers)를 langgraph 서버
      blockbuster가 BlockingError로 차단 → asyncio.to_thread 우회
    - e2e: 데모조서 5400 검토 — K-IFRS 1109 5.5.15(대손충당금)·KSA 505
      A18(조회 대체절차) 확정 인용, 후속 질문은 chat이 보고서 인용 재전달
- [x] find_target_file 퍼지 매칭 — "데모조서 5400 매출채권"(밑줄·괄호 생략)
      이 미매칭이던 것을 토큰 겹침(≥2, 최다 겹침)으로 해결. 환영 화면 예시
      질문이 실패하는 실전 버그였음
- [x] explainer 조서 해설 전용 그래프 신설 (Phase 1: evidence.py·
      standards_lookup.py 공용 계층 추출 → Phase 2: 그래프) — reviewer와
      같은 골격(triage→locate→collect→investigate→explain→cite→report),
      산출물은 해설(①정체 ②시트 구성 ③절차 해설+인용 ④읽는 법 ⑤미완
      ⑥용어 풀이 ⑦요약). 기존 agent는 "All-in-One Agent"로 개명
- [x] agent 대화 요약 미들웨어 — SummarizationMiddleware, fraction 0.75
      우선·프로파일 미보유 모델(실측: 기본 claude-sonnet-5조차 미등재,
      local/hf)은 제공자별 절대값 폴백(anthropic 150k/local·hf 24k/기타
      100k). 요약 모델은 라우팅된 모델 그대로(로컬 전용 사용자 보호)
- [x] MCP 상한 조정 — cite 대상 5→10건, 도구 결과 클립 4k→6k자.
      상한 전수: cite 10건×2왕복(병렬)·chat 라운드3/호출4·SEARCH_TOP_K 3·
      전송 timeout 30s/120s·서버 top_k 1~20. agent는 recursion_limit(25)뿐
- [x] UI 개선 일괄 — ① 그래프 셀렉터 한국어 표시명 + 그래프별 첫 화면
      (configs/graphs.ts 단일 소스: 표시명·소개·예시 질문) ② 그래프 전환을
      window.location.reload(하얀 깜빡임, upstream 원본 동작)에서
      router.refresh()+connection key 리마운트로 교체, 전환 시 새 채팅
      ③ HF iframe에서 그래프 선택이 안 유지되던 버그 — Space는 cross-site
      iframe이라 SameSite=Lax 쿠키 미전송 → production에서 None+Secure
      (crossSiteCookieAttributes, 연결·로케일 쿠키 적용)
- [x] 스트리밍 차이 조사 (수정 없음, 사용자 납득) — agent만 중간 내레이션이
      스트리밍되는 이유: ReAct는 내레이션이 messages 상태로 흘러가고, 고정
      그래프는 중간 호출이 구조화 출력(텍스트 없음)+최종 report가 템플릿
      렌더(토큰 없음). analyst answer는 실측상 이미 토큰 스트리밍됨
- [x] 브랜딩 — 앱 이름 "Agent for Newstep", 첫 화면·헤더 정리, favicon 교체
- [x] upstream 문서 복원 — langgraph-chat-ui docs/ 23종 + README 2종을
      ui/docs/로 (이식 시 삭제했던 것, 사용자 질책 → 메모리에 원칙 기록)
- [x] 데모 데이터 — 매출시트_데모.csv (HF AbhayBhan/SalesData 공개 더미
      1000행) 커밋, analyst e2e·pandas 검산 일치
- [x] Space 배포 (factory rebuild ×2) — 4그래프 서빙·새 브랜딩·쿠키 수정
      반영 확인. 테스트 누적 118개 통과
- [x] 로컬 무스타일 화면 재발 — 이번엔 좀비가 아니라 .next에 프로덕션 빌드
      산출물(해시 CSS)이 덮인 변종. 진단 지표·복구 절차 메모리 갱신

## 웹 계층·5그래프 세션 (2026-07-18) — 웹 추출/검색·기업이해·품질 다듬기

- [x] 웹 추출 이식 (langgraph_web_scraping_agent → 서브그래프) — 독립
      그래프가 아니라 agent 도구 web_extract로 노출. scraping/ 패키지
      (SSRF 방어·바운디드 fetcher·bs4 정리·청킹) 원본 무수정 이식,
      Playwright fallback 제외, 모델은 호출자 주입(SCRAPER_MODEL env 폐기),
      청크 5개 상한·결과 6k자 클립 추가
    - 함정: anthropic output_version=v1은 content가 블록 리스트 —
      reasoning 블록(서명 포함)이 도구 결과에 직렬화되던 버그를 e2e에서
      발견, 텍스트 블록만 취합으로 수정
- [x] 웹 추출 Jina Reader 하이브리드 개정 — 1차 r.jina.ai(JSON 모드,
      JS 렌더링 포함 마크다운) 50k자 클립 통짜 1회 추출, 실패 시 기존
      httpx+bs4 경로 폴백. 청킹·병합은 Jina 경로에서 소멸. 경로 검증은
      LangSmith 트레이스(fetch_via_jina→extract_chunks 직행)로 실측
- [x] 조서 해설·검토 관점 강제 — 원인은 프롬프트가 아니라 스키마('왜'를
      묻는 필드 부재). ProcedureNote에 assertion·risk_addressed, Finding에
      assertion·risk_if_unresolved 추가 + '주장→위험→절차→증거' 렌즈
      프롬프트 + 템플릿 태그 렌더. 엑셀/MCP 컨텍스트 분리는 이미 구현
      상태라 불필요 판정
- [x] profiler 기업이해 그래프 신설 (5번째) — 감사기준서 315 골격:
      triage→plan→dart→gather→extract(웹 추출 서브그래프 재사용)→analyze
      →cite→report(①~⑧+조사 자료+근거 목록+감사증거 아님 고지).
      LLM ≤8회 상한, 우아한 강등 사다리(DART·검색 키·URL 중 하나만 있어도
      동작). UI 셀렉터·예시 등록
- [x] DART 공식 공시 백본 — dart_client.py (OpenDartReader 접근만 얇게
      포팅: corpCode 매핑 프로세스 캐시·기업개황·주요 재무계정·최근 공시,
      httpx·pandas 무의존). 실측: 삼성전자 연결 15계정×3개년, 웹 자료
      (나무위키 자본금 오기)를 공시 수치로 판정하는 보고서 확인
- [x] Tavily 웹 검색 — agent 15번째 도구 web_search(Tavily 우선·Jina
      폴백, 키 없으면 미등록), profiler 검색 격상(최근 이슈 topic=news
      90일, 검색 발췌 전체를 폭 보완 증거로 4k 클립 수집). s.jina.ai는
      무키 불가(401) 실측이 설계 변경 계기
- [x] profiler analyze 견고화 — Space 실측에서 구조화 출력이 리스트
      필드를 '<item>…' 문자열로 내고 섹션 누락 → 2회 동일 실패. 교정
      재시도(직전 검증 오류를 프롬프트에 주입) + 문자열 승격·빈 값 강등
- [x] 보고서 뭉탱이 글 해소 (사용자 지적, LangSmith로 원인 확정) —
      ① 템플릿의 들여쓴 연속 줄을 마크다운이 한 문단으로 접음 → 그래프
      3종 템플릿을 하위 불릿 구조로 ② 약한 모델(Haiku)이 필드에 장문 →
      스키마 설명·프롬프트에 분량 강제(주장은 명칭만·위험 한 문장·해설
      두세 문장). 동일 조건 재실측: 섹션 분량 1/3, 요소별 제 줄
- [x] UI — 채팅 입력창 placeholder 제거 (설정 3층 병합 함정: site.ts만
      비우면 i18n 기본값이 다시 채움 — ko/en defaults도 함께 비움)
- [x] 시크릿 3종 등록 — JINA_API_KEY·TAVILY_API_KEY·DART_API_KEY를 로컬
      .env와 Space 시크릿(add_space_secret, 자동 재시작) 양쪽에.
      셸 함정: .env는 set -a 없이 source하면 자식 프로세스에 미전달
- [x] Space 배포 (factory rebuild ×5) — 매 단계 e2e 실측(웹 추출·검색·
      DART·profiler 브리핑·뭉탱이 수정). 테스트 누적 180개 통과
