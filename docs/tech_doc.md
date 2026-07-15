# 기술 문서 — ExcelBrief for Newsteps

> 스택·의존성·환경변수·개발 규약.

## 1. 기술 스택

| 계층 | 선택 | 비고 |
|---|---|---|
| 언어 | Python 3.11+ | 도구 내부에서 타 언어 프로세스 호출 허용 |
| 에이전트 | langchain (`create_agent`) | 단일 에이전트로 충분 (MVP) |
| 서버/런타임 | langgraph + langgraph-cli | `langgraph dev` → :2024 |
| MCP 연동 | langchain-mcp-adapters | stdio/HTTP 양쪽 지원 |
| Excel | openpyxl | 수식·병합 셀 접근 |
| LLM (상용) | Anthropic API | 기본 `claude-sonnet-5` |
| LLM (로컬) | vLLM 또는 Ollama | OpenAI 호환 엔드포인트 (모델 미정) |
| UI | braincrew-lab/agent-chat-ui | Next.js 15, Node 20+, pnpm |
| 배포 | HuggingFace Spaces (Docker) | backend·UI Space 2개 또는 단일 Space+프록시 |
| 관측 | LangSmith | 트레이싱·평가 |
| 테스트 | pytest + pytest-asyncio | 픽스처 xlsx 기반 |

## 2. 의존성 (pyproject.toml 예정)

```
langchain
langgraph
langgraph-cli[inmem]        # langgraph dev 실행용
langchain-anthropic
langchain-openai            # 로컬 OpenAI 호환 서버 접속용
langchain-mcp-adapters
openpyxl
python-dotenv
pytest, pytest-asyncio      # dev
```

버전은 설치 시점에 고정한다(잠금 파일 커밋). LangChain 계열은 API 변화가 잦으므로
구현 전 반드시 최신 문서(docs.langchain.com) 대조.

## 3. 환경변수 (.env)

| 변수 | 용도 | 상태 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 상용 LLM | 준비됨 |
| `LANGSMITH_API_KEY` | 트레이싱 | ⚠️ 현행 이름으로 갱신 필요 (아래) |
| `LANGSMITH_TRACING=true` | 〃 | 〃 |
| `LANGSMITH_PROJECT` | 〃 | 〃 |
| `MCP_AUTH_TOKEN` | MCP HTTP(기본) Bearer 토큰 | 준비됨 |
| `MCP_HTTP_URL` | MCP HF Space 엔드포인트 | 추가 예정 |
| `MCP_TRANSPORT` | `http`(기본) / `stdio`(로컬 옵션) | 추가 예정 |
| `QDRANT_URL` / `QDRANT_API_KEY` | MCP stdio(로컬 옵션) 기동 시만 | 준비됨 |
| `LOCAL_LLM_BASE_URL` | 로컬 모델 엔드포인트 | 추가 예정 |
| `WORKPAPERS_DIR` | 조서 폴더 (기본 `data/workpapers`) | 추가 예정 |

> ⚠️ **현재 `.env`는 구식 LangSmith 변수명(`LANGCHAIN_API_KEY`,
> `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_PROJECT`)을 쓰고 있다.
> 현행 명칭은 `LANGSMITH_API_KEY` / `LANGSMITH_TRACING` / `LANGSMITH_PROJECT`이며
> 구명칭은 더 이상 동작하지 않는다.** Phase 0에서 갱신한다.

## 4. 실행 방법 (구현 후)

```bash
# 백엔드
cd ExcelBrief_for_Newsteps
uv sync                      # 또는 pip install -e .
langgraph dev                # :2024

# UI (최초 1회 클론)
cd ui && pnpm install
cp .env.example .env         # NEXT_PUBLIC_API_URL=http://localhost:2024
pnpm dev                     # :3000

# (옵션) 로컬 모델
ollama serve                 # 또는 vLLM

# 배포 — HuggingFace Spaces (Docker)
# backend Space: Dockerfile에서 langgraph 서버 :7860 기동,
#                시크릿(ANTHROPIC_API_KEY, MCP_AUTH_TOKEN, LANGSMITH_API_KEY) 주입
# UI Space:      next build/start, NEXT_PUBLIC_API_URL=<backend Space URL>
```

## 5. 개발 규약

- **TDD**: Excel 도구는 픽스처 xlsx(감사조서 모사 + 범용 시트)로 테스트 먼저 작성.
  에이전트 전체는 스모크 테스트(도구 호출 발생 여부) 수준 — LLM 출력 자체는
  LangSmith 평가로 다룬다.
- **커밋**: conventional commits (`feat:`, `fix:`, …). 계획 문서 완료 후 `git init`.
- **비밀값**: `.env` 커밋 금지 (`.gitignore` 유지). auditPaper_MCP 규약과 동일.
- **경로 보안**: Excel 도구는 `WORKPAPERS_DIR` 하위만 접근 (resolve 후 prefix 검증).
- **문서 대조**: LangChain/LangGraph API는 훈련 데이터가 아니라
  docs.langchain.com 실문서 기준으로 구현.

## 6. 평가 (품질 측정)

- auditPaper_MCP의 `eval/score_interpretation.py` + 골드셋 채점 체계를 재활용:
  해석 산출물을 `해석_{조서번호}.md` 형식으로 저장하면 기존 채점기로 평가 가능.
- LangSmith 트레이스로 도구 호출 패턴(개요→정독→기준 검색 순서 준수) 점검.

## 7. 알려진 제약

| 제약 | 대응 |
|---|---|
| agent-chat-ui 업로드가 이미지·PDF만 지원 | MVP는 가상 샘플 조서 사전 배치, 방문자 업로드는 백로그 최우선 |
| SpreadsheetLLM 공식 코드 미공개 | 커뮤니티 재구현체 검토 (백로그) |
| `langgraph dev`는 인메모리 개발 서버 | 포트폴리오 데모 수준에선 허용. 트래픽·영속성이 필요해지면 self-hosted 컨테이너 검토 |
| HF Space는 유휴 시 슬립 가능 | 데모 전 워밍업(첫 접속 지연 안내 문구), MCP 첫 검색 타임아웃 넉넉히 |
| openpyxl은 계산 엔진이 없음 | 수식 결과는 저장된 캐시 값(`data_only`) 사용 — 재계산 불가함을 프롬프트에 명시 |
| 공개 URL에 실데이터 게시 불가 | 데모 조서는 가상 데이터로 제작 |
