# 기술 문서 — Agent for Newstep (구 ExcelBrief for Newsteps)

> 스택·의존성·환경변수·개발 규약. 2026-07-18 현행화.

## 1. 기술 스택

| 계층 | 선택 | 비고 |
|---|---|---|
| 언어 | Python 3.12 | |
| 에이전트 | langchain 1.x (`create_agent`) + langgraph StateGraph | 그래프 5종 (agent·explainer·analyst·reviewer·profiler) |
| 서버/런타임 | langgraph + langgraph-cli | `langgraph dev --host 0.0.0.0` → :2024 (WSL2는 호스트 바인딩 필수) |
| MCP 연동 | langchain-mcp-adapters | HTTP+Bearer 기본 / stdio 로컬 옵션 |
| Excel | openpyxl | 수식·서식·병합 셀·주석 접근 |
| 표 SQL | duckdb + sqlglot + pandas 3 | AST 검증 + external_access=false 2중 격리 |
| LLM | Anthropic(기본 sonnet-5)·OpenAI·Gemini·HF Inference·Ollama | resolve_model 접두사 라우팅 |
| UI | braincrew-lab/langgraph-chat-ui 이식 (ui/) | Next.js 15, pnpm. upstream 문서는 ui/docs/ |
| 배포 | HuggingFace Space 단일 컨테이너 (Docker) | toddl/excelbrief — UI passthrough 프록시 |
| 관측 | LangSmith (+MCP로 트레이스 해부) | 프로젝트 excelbrief |
| 테스트 | pytest + pytest-asyncio | 픽스처 코드 생성 방식, 118개 |

## 2. 의존성 (pyproject.toml — requirements.lock으로 고정)

```
langchain / langgraph / langgraph-cli[inmem]
langchain-anthropic / langchain-openai / langchain-google-genai
langchain-mcp-adapters
openpyxl / duckdb / sqlglot / pandas / numpy
beautifulsoup4 / httpx            # 웹 추출 폴백 경로·Jina/Tavily/DART 호출
python-dotenv
pytest, pytest-asyncio      # dev
```

LangChain 계열은 API 변화가 잦으므로 구현 전 docs.langchain.com 실문서 대조.

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
| `JINA_API_KEY` | (선택) 웹 추출 1차 경로·Jina 검색 폴백 | 준비됨 |
| `TAVILY_API_KEY` | (선택) 웹 검색 1순위 (agent web_search·profiler) | 준비됨 |
| `DART_API_KEY` | (선택) 기업이해 OpenDART 공시 수집 | 준비됨 |

> ⚠️ **현재 `.env`는 구식 LangSmith 변수명(`LANGCHAIN_API_KEY`,
> `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_PROJECT`)을 쓰고 있다.
> 현행 명칭은 `LANGSMITH_API_KEY` / `LANGSMITH_TRACING` / `LANGSMITH_PROJECT`이며
> 구명칭은 더 이상 동작하지 않는다.** Phase 0에서 갱신한다.

## 4. 실행 방법 (현행)

```bash
# 백엔드 — 그래프 5종 서빙
.venv/bin/python -m langgraph_cli dev --no-browser --host 0.0.0.0 --port 2024

# UI
cd ui && pnpm install && pnpm dev    # :3000 (ui/.env에 LANGSMITH_* 포함)
# 주의: dev 실행 중 next build 금지 (.next 충돌 → CSS 404 무스타일)
#       재기동 전 next 프로세스 전멸 확인 후 하나만 띄울 것

# (옵션) 로컬 모델 — Ollama systemd 서비스 (:11434, qwen3:8b-16k)

# 배포 — HF Space 단일 컨테이너 (toddl/excelbrief)
# 빌드가 GitHub main을 clone하므로: git push 후 factory rebuild 트리거
# (huggingface_hub restart_space(factory_reboot=True))
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
| SpreadsheetLLM 공식 코드 미공개 | 커뮤니티 재구현체 검토 (백로그) |
| `langgraph dev`는 인메모리 개발 서버 | 포트폴리오 데모 수준에선 허용. Space도 동일 방식 |
| HF Space는 유휴 시 슬립·업로드 휘발 | 데모 전 워밍업, 업로드는 재시작 시 삭제 고지 |
| HF Space는 cross-site iframe | SameSite=Lax 쿠키 미전송 → 선호 쿠키는 None+Secure |
| langgraph async 노드에서 동기 I/O 차단(blockbuster) | asyncio.to_thread로 우회 |
| openpyxl은 계산 엔진이 없음 | 수식 결과는 저장된 캐시 값(`data_only`) — 재계산 불가를 프롬프트·보고서 고지 |
| 고정 그래프의 최종 보고서는 토큰 스트리밍 불가 | 템플릿 렌더 특성 — custom 진행 이벤트로 침묵 구간 보완 (설계상 수용) |
| 공개 URL에 실데이터 게시 불가 | 데모 조서는 가상 데이터·공식 서식·공개 더미만 |
