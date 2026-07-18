# 아키텍처 — Agent for Newstep (구 ExcelBrief for Newsteps)

> 구성요소와 선택 근거. 상세 흐름·인터페이스는 [system_design.md](system_design.md) 참조.
> 2026-07-18 현행화 — 5그래프 체제(기업이해 추가)·단일 Space 배포 반영.

## 1. 전체 그림

```
┌───────────────────────────────────────────────┐
│ langgraph-chat-ui (Next.js 15, ui/)            │  braincrew-lab/langgraph-chat-ui 이식
│  그래프 셀렉터·모델 드롭다운·파일 업로드        │  (원본 문서: ui/docs/)
│  LangSmith Tracing 패널                        │
└──────────────────┬────────────────────────────┘
                   │ LangGraph API (SSE — values·messages-tuple·custom)
┌──────────────────▼────────────────────────────┐
│ LangGraph 서버 (Python)                        │  본 저장소, 그래프 5종
│  ├─ agent     All-in-One ReAct (도구 15종)     │
│  ├─ explainer 조서 해설 고정 파이프라인         │
│  ├─ analyst   대형 표 SQL 분석 고정 파이프라인  │
│  ├─ reviewer  조서 검토 고정 파이프라인         │
│  ├─ profiler  기업이해 고정 파이프라인 (웹)     │
│  │                                            │
│  ├─ 공용: resolve_model(벤더 5종 라우팅)        │── Anthropic/OpenAI/Gemini
│  ├─ 공용: tools/(excel·table·documents)        │── HF Inference 라우터
│  ├─ 공용: evidence.py(증거 수집)               │── 로컬 Ollama(OpenAI 호환)
│  ├─ 공용: standards_lookup.py(인용 확정)        │
│  └─ 공용: mcp_client.py                        │
└──────────────────┬────────────────────────────┘
                   │ HTTP + Bearer (기본) / stdio (로컬 옵션)
┌──────────────────▼────────────────────────────┐
│ auditPaper_MCP (기존 완성 자산)                 │  HF Space 상시 배포 (toddl/auditpaper-mcp)
│  standards_search / get_paragraph /            │──→ Qdrant Cloud
│  define_terms                                  │    (기준서 212파일 20,970문단)
└───────────────────────────────────────────────┘
```

## 2. 그래프 5종 — 범용기 1 + 특화기 4

| 그래프 | UI 표시명 | 성격 | LLM 호출 |
|---|---|---|---|
| `agent` | All-in-One Agent | create_agent ReAct — 전 도구 15종(웹 검색·추출 포함, 검색 키 없으면 14종), 제어 흐름 전부 모델 재량. 여러 파일 넘나드는 질문·기준서 자체 질문 | 자유 (recursion 25 상한) |
| `explainer` | 조서 해설 Agent | 고정: triage→locate→collect→investigate→explain→cite→report | 3~4회 상한 |
| `analyst` | 대형 엑셀 분석 Agent | 고정: triage→inspect→plan→validate→execute→answer (+revise≤2) | 3~5회 상한 |
| `reviewer` | 조서 검토 Agent | 고정: triage→locate→collect→investigate→assess→cite→report | 3~4회 상한 |
| `profiler` | 기업이해 Agent | 고정: triage→plan→dart(OpenDART 공식 공시, 비LLM)→gather(URL·검색)→extract(웹 추출 서브그래프)→analyze→cite→report — 감사기준서 315 이해 활동 보조 | ≤8회 상한 |

분리 원칙: **보장이 필요한 작업만 특화 그래프로 뺀다.** 결정성(같은 파일이면
같은 증거)·비용 상한·출력 형식(템플릿)·안전 관문(SQL AST 검증)은 프롬프트가
아니라 그래프 구조로만 강제할 수 있다. agent도 같은 도구로 흉내는 내지만
아무것도 보장하지 않는다. UI에서 그래프를 고르는 행위 = 필요한 보장을 고르는 행위.

고정 그래프 공통 골격: triage가 작업/일반 대화를 분기(LLM 분류 1회, 실패 시
파일 언급 휴리스틱 폴백), chat 노드는 기준서 MCP를 쥔 미니 ReAct(호출 상한),
investigate만 Excel 도구 재량(상한), 본체 LLM은 구조화 출력, cite는 LLM 없이
search→get_paragraph 재확인 인용, report는 결정적 템플릿. 진행 상황은 custom
스트림(emit)으로 UI에 표시.

## 3. 구성요소와 선택 근거

### UI — langgraph-chat-ui 이식 (ui/)

- braincrew-lab/langgraph-chat-ui의 frontend/를 ui/로 이식 (standalone 인증
  모드). 원본 docs/·README는 ui/docs/에 보존 — **이식 시 upstream 문서를
  빼먹지 말 것** (2026-07-17 교훈).
- Excel(xlsx/xlsm/xls)·CSV·Word(docx) 업로드 지원 (조서 폴더에 저장, 휘발성).
- 그래프별 첫 화면(소개·예시 질문)·셀렉터 표시명은 `ui/src/configs/graphs.ts`
  단일 소스. 그래프 전환은 router.refresh() + connection key 리마운트
  (전체 리로드 없음 — upstream 원본의 reload 방식 개선).
- **HF iframe 함정**: Space는 huggingface.co 안의 cross-site iframe이라
  SameSite=Lax 쿠키가 요청에 실리지 않는다 — 선호 쿠키(연결·로케일)는
  production에서 `SameSite=None; Secure` (`crossSiteCookieAttributes`).

### 모델 계층 — init_chat_model + config 라우팅 (벤더 5종)

- `config["configurable"]["model"]` 접두사 라우팅: `anthropic:`(기본
  claude-sonnet-5, 프롬프트 캐싱) / `openai:` / `google_genai:` /
  `hf:`(Inference Providers 라우터) / `local:`(Ollama). 5개 그래프가 공유.
- agent에는 SummarizationMiddleware(긴 스레드 요약 치환) 장착 — fraction 0.75,
  프로파일 미보유 모델은 제공자별 절대값 폴백.

### Excel 접근 — 도구 기반 탐색 + 표 SQL 격리

- openpyxl 도구 7종(개요·범위·검색·주석·수식 지도·통계)으로 필요한 부분만 탐색.
- 표 집계는 excel_load_table/excel_query_table — sqlglot AST 검증 + DuckDB
  `enable_external_access=false` 2중 격리 (pandas eval의 RCE 문제 해소).
- 조서 증거 수집(evidence.py)은 explainer·reviewer 공용 비LLM 계층.

### 기준서 RAG — auditPaper_MCP 재사용

- HTTP + Bearer(기본) / stdio(로컬 옵션). 연결 실패 시 빈 도구 목록으로
  강등 — 인용 없이도 동작.
- `_with_displays` 래퍼가 문단마다 표기 문자열(display)을 주입하고 서버측
  인수 오류를 "오류: …" 텍스트로 변환(약한 모델 자가 수정 유도).
- standards_lookup.py의 resolve_citation이 search→get_paragraph 재확인
  인용 규칙의 단일 구현 (explainer·reviewer cite 공용).

## 4. 배포 — HuggingFace Space 단일 컨테이너 (확정)

`toddl/excelbrief` Space 하나에 Next.js(:7860 노출)와 LangGraph 서버를 함께
기동, UI의 API passthrough로 내부 프록시 (CORS 불필요, URL 하나).
빌드 시점에 GitHub main을 clone하므로 배포 = factory rebuild.

- 시크릿: ANTHROPIC/OPENAI/GEMINI_API_KEY, HF_INFERENCE_TOKEN,
  MCP_AUTH_TOKEN, LANGSMITH_API_KEY, (선택) JINA_API_KEY — 웹 추출 1차
  경로(무키 시 20 RPM 모드)·기업이해 웹 검색용(s.jina.ai, 무키 불가 —
  키 없으면 profiler는 사용자 제공 URL만 조사), (선택) TAVILY_API_KEY —
  웹 검색 1순위 제공자(agent web_search·profiler 검색, 결과에 본문 발췌
  포함), (선택) DART_API_KEY — 기업이해의 OpenDART 공식 공시 수집용
  (없으면 웹 자료만으로 강등)
- 데모 조서: 가상 데이터·한공회 공식 서식·공개 더미 CSV만 (실데이터 금지)
- 빌더 고착·전역 정체 대응 절차는 메모리(hf-space-builder-stuck) 참조

## 5. 저장소 구조 (현행)

```
ExcelBrief_for_Newsteps/
├─ langgraph.json              # 그래프 5종 진입점
├─ pyproject.toml / requirements.lock
├─ src/agent/
│   ├─ graph.py                # agent(All-in-One) + resolve_model + 요약 미들웨어
│   ├─ explainer.py            # 조서 해설 그래프
│   ├─ analyst.py              # 표 SQL 분석 그래프
│   ├─ reviewer.py             # 조서 검토 그래프
│   ├─ profiler.py             # 기업이해 그래프 (감사 착수 전 회사 이해)
│   ├─ dart_client.py          # OpenDART 경량 클라이언트 (공식 공시 자료원)
│   ├─ web_search.py           # 웹 검색 도구 (Tavily 우선·Jina 폴백)
│   ├─ graph_common.py         # 파일 탐지(퍼지)·대화 맥락·emit
│   ├─ web_extract.py          # 웹 추출 서브그래프 + agent 도구 래퍼
│   ├─ scraping/               # 웹 취득 계층 (SSRF 방어·Jina Reader·fetcher·정리·청킹)
│   ├─ evidence.py             # 조서 기계 증거 수집 (공용, 비LLM)
│   ├─ standards_lookup.py     # MCP 결과 파싱·인용 확정 (공용)
│   ├─ citations.py            # cid → 표기 문자열
│   ├─ mcp_client.py           # auditPaper_MCP 연결 + display 래퍼
│   ├─ prompts.py              # agent 시스템 프롬프트
│   └─ tools/                  # excel(7종)·table(SQL 2종)·documents(docx)
├─ data/workpapers/            # 데모 조서·서식·CSV (배포 이미지 포함)
├─ tests/                      # pytest 118개
├─ docs/                       # 계획·현행 문서 (본 문서)
└─ ui/                         # langgraph-chat-ui 이식 (ui/docs/ = upstream 문서)
```
