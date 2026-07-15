# 아키텍처 — ExcelBrief for Newsteps

> 구성요소와 선택 근거. 상세 흐름·인터페이스는 [system_design.md](system_design.md) 참조.

## 1. 전체 그림

```
┌─────────────────────────────────────────┐
│ agent-chat-ui (Next.js 15, 포크 그대로)   │  braincrew-lab/agent-chat-ui
│  NEXT_PUBLIC_API_URL=localhost:2024      │
└──────────────────┬──────────────────────┘
                   │ LangGraph API (SSE 스트리밍)
┌──────────────────▼──────────────────────┐
│ LangGraph 서버 (Python, langgraph dev)   │  본 저장소
│  └─ 에이전트 (create_agent 기반)          │
│      ├─ 모델: init_chat_model            │── 상용 Anthropic API
│      │   config로 라우팅                  │── 로컬 vLLM/Ollama (OpenAI 호환)
│      ├─ Excel 탐색 도구 (openpyxl)        │
│      └─ MCP 클라이언트                    │
│          (langchain-mcp-adapters)        │
└──────────────────┬──────────────────────┘
                   │ HTTP (기본 — HF Space 원격) / stdio (로컬 옵션)
┌──────────────────▼──────────────────────┐
│ auditPaper_MCP (기존 완성 자산)           │  HF Space 상시 배포 (toddl/auditpaper-mcp)
│  standards_search                        │
│  standards_get_paragraph                 │──→ Qdrant Cloud
│  standards_define_terms                  │    (기준서 212파일 20,970문단)
└─────────────────────────────────────────┘
```

## 2. 구성요소와 선택 근거

### UI — agent-chat-ui 포크 (신규 개발 없음)

- LangGraph 서버 전용 챗 UI. `NEXT_PUBLIC_API_URL` + `NEXT_PUBLIC_ASSISTANT_ID`만
  설정하면 붙는다. `public/chat-config.yaml`로 브랜딩·문구 커스터마이징.
- **제약**: 파일 업로드가 이미지·PDF만 지원 → MVP는 **가상 샘플 조서를 서버에
  미리 배치**하고 방문자가 선택해 데모하는 방식 (`data/workpapers/`, 배포 이미지에 포함).
  방문자 xlsx 업로드는 공개 데모 가치가 커서 백로그 최우선.

### 백엔드 — LangGraph 서버

- agent-chat-ui가 LangGraph API를 요구하므로 백엔드 형태는 LangGraph 서버로 확정.
- 그래프 내부는 LangChain `create_agent`로 만든 단일 에이전트를 노출.
  MVP 요구(챗 + 도구 탐색 + RAG)에는 커스텀 그래프가 불필요하며,
  추후 다단계 분석 파이프라인이 필요해지면 해당 부분만 LangGraph 노드로 확장.

### 모델 계층 — init_chat_model + config 라우팅

- `init_chat_model()`에 모델 문자열을 넘겨 제공자를 런타임에 결정.
- LangGraph의 `config["configurable"]["model"]`로 요청(스레드)마다 모델 선택.
  UI의 assistant 설정으로 "상용 API" / "로컬 모델" 어시스턴트를 분리 가능.
- 로컬 모델은 vLLM 또는 Ollama의 OpenAI 호환 엔드포인트로 서빙 (구체 모델 미정 —
  인터페이스가 동일하므로 구조에 영향 없음).
- 자동 폴백·사용량 통제가 필요해지는 시점에 LiteLLM 게이트웨이를 앞단에 추가 (백로그).

### Excel 접근 — 도구 기반 탐색 (통짜 변환 금지)

- 조서는 수십 시트·수식·병합 셀·틱마크가 섞여 있어 전체 텍스트 변환 시
  토큰 한도 초과·구조 훼손이 발생한다.
- 에이전트에게 openpyxl 기반 도구(워크북 개요·범위 읽기·수식 조회·검색)를 주고
  **필요한 부분만 탐색하며 읽게** 한다. 이 방식으로 범용 Excel(F2)도 자연 처리.
- 초대형 워크북 압축(SpreadsheetLLM류)은 백로그 — 공식 코드 미공개로
  커뮤니티 재구현체 검토 필요.

### 기준서 RAG — auditPaper_MCP 재사용 (재작업 제로)

- 도구 3종의 입출력 스키마·오류 봉투가 규약화된 완성 자산.
- `langchain-mcp-adapters`의 `MultiServerMCPClient`로 연결:
  - **HTTP (기본)**: HF Space 상시 배포(`toddl/auditpaper-mcp`) + Bearer 토큰.
    백엔드 자체가 HF Spaces에 올라가므로, 배포·로컬 개발이 같은 경로를 쓰는 게 단순함
  - **stdio (옵션)**: auditPaper_MCP를 같은 머신에서 직접 기동하는 로컬 개발용
    (기존 `.mcp.json` 배선 재사용)

## 3. 배포 — HuggingFace Spaces

포트폴리오 MVP이므로 HF Spaces 공개 배포. 기본안은 Space 2개:

| Space | 내용 | 비고 |
|---|---|---|
| `excelbrief-backend` | LangGraph 서버 (Docker) | 컨테이너에서 langgraph 서버 기동, :7860 노출. 샘플 조서 포함 |
| `excelbrief-ui` | agent-chat-ui (Docker, Next.js) | `NEXT_PUBLIC_API_URL` → backend Space URL |

- **대안 (단일 Space)**: Next.js와 LangGraph 서버를 한 컨테이너에서 기동하고
  agent-chat-ui의 API passthrough(서버측 `LANGGRAPH_API_URL`)로 내부 프록시 —
  CORS가 필요 없고 URL이 하나로 정리됨. 배포 Phase에서 실측 후 택1.
- auditPaper_MCP는 이미 HF Space 상시 배포 → HTTP + Bearer 토큰으로 연결 (추가 작업 없음).
- LLM은 상용 Anthropic API (Space 시크릿으로 키 주입). `local:` 라우트는
  로컬 개발·시연용으로 유지 — 배포 환경에는 로컬 GPU가 없음.

## 4. 저장소 구조 (예정)

```
ExcelBrief_for_Newsteps/
├─ langgraph.json          # LangGraph 서버 정의 (graph 진입점)
├─ pyproject.toml
├─ .env                    # 키 (커밋 금지)
├─ src/agent/
│   ├─ graph.py            # create_agent 조립 + 모델 라우팅
│   ├─ tools/excel.py      # openpyxl 탐색 도구
│   ├─ mcp_client.py       # auditPaper_MCP 연결
│   └─ prompts.py          # 시스템 프롬프트 (조서 해석 지침)
├─ data/workpapers/        # 조서 파일 위치 (MVP 업로드 대체)
├─ tests/                  # pytest (도구 단위 + 에이전트 스모크)
├─ docs/                   # 본 계획 문서
└─ ui/                     # agent-chat-ui 클론 (또는 별도 폴더)
```
