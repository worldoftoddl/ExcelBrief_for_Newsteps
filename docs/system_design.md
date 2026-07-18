# 시스템 설계 — Agent for Newstep (구 ExcelBrief for Newsteps)

> 상세 흐름·인터페이스·데이터 계약. 구성요소 개관은 [architecture.md](architecture.md) 참조.
> 2026-07-18 현행화 — 그래프 5종(기업이해 추가)·공용 계층·업로드 반영.

## 1. 핵심 흐름 — 조서 해석 요청

```
사용자: "data/workpapers/D-10 매출채권.xlsx 해석해줘"
  │
  ▼ agent-chat-ui → LangGraph API (thread 생성/이어가기, config.configurable.model 포함)
  ▼ 에이전트 루프 (create_agent)
  1. excel_workbook_overview(경로)        → 시트 목록·크기·헤더 파악
  2. excel_read_range(시트, 범위)          → 핵심 영역 정독 (필요 시 반복)
  3. excel_read_range(..., formulas=True) → 계산 로직 확인
  4. standards_search("매출채권 조회확인 …") → 관련 기준 문단 검색
  5. standards_get_paragraph(cid, context) → 인용 원문 확정
  6. (필요 시) standards_define_terms      → 용어 정의
  ▼
최종 답변: 수행 절차 해석 + 근거 기준 cid 인용 + 추가 필요 절차
  ▼ SSE 스트리밍으로 UI에 토큰 단위 전달
```

## 2. 그래프 정의 — 5종

`langgraph.json`이 그래프 5종의 팩토리를 등록한다. 모두
`config["configurable"]["model"]`로 요청마다 모델을 라우팅한다.

### 2.1 agent (All-in-One) — create_agent ReAct

```python
# src/agent/graph.py (개요)
model = resolve_model(model_spec)
tools = EXCEL_TOOLS + TABLE_TOOLS + DOCUMENT_TOOLS \
    + [make_web_extract_tool(model), make_web_search_tool()] \
    + standards_tools  # 15종 (web_search는 검색 키 없으면 미등록 → 14종)
create_agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT,
             middleware=[summarization_middleware(model, model_spec)])
```

- 시스템 프롬프트(`prompts.py`)가 행동 전부를 유도: 탐색 순서(개요→정독),
  표 집계는 SQL 도구, 검증 원칙(셀 주소 병기·암산 금지), 인용 규칙
  (search→get_paragraph 확정·source_type 한정·cid는 근거 목록에만).
- SummarizationMiddleware: 긴 스레드에서 오래된 이력을 요약으로 치환
  (fraction 0.75, 프로파일 미보유 모델은 anthropic 150k/local·hf 24k/기타
  100k 절대값 폴백. 요약 모델 = 라우팅된 모델).
- `web_extract`(웹 추출)는 내부적으로 **서브그래프**를 invoke하는 도구다
  (`web_extract.py`). fetch는 하이브리드: 1차 **Jina Reader**(r.jina.ai —
  JS 렌더링 포함, 마크다운 반환, JINA_API_KEY 없으면 무키 20 RPM 모드)로
  50k자 클립 후 청킹·병합 없이 통짜 1회 추출, 실패 시 기존 httpx+bs4 경로
  (fetch 재시도 3→clean→chunk→extract→merge)로 폴백. 공통: validate(SSRF
  차단)→…→validate(+빈 결과 재추출 ≤2). langgraph_web_scraping_agent
  이식 — 취득 계층은 `scraping/`(원본 문서 README.upstream.md).
  상한: 폴백 청크 5개(초과분 버리고 고지)·결과 6,000자 클립·응답 2MB·
  리다이렉트 5회. 공개 http(s)만 허용 — 사설/루프백 IP는 DNS 해석 후 차단,
  리다이렉트마다 재검증 (Jina 경로도 입구에서 같은 URL 검증 통과 필요).
- `web_search`(웹 검색, `web_search.py`)는 Tavily 우선(결과에 본문 발췌
  포함)·Jina 검색 폴백 — 상위 5건을 [출처: URL]과 발췌로 반환(4k자 클립).
  정독이 필요하면 모델이 그 URL을 web_extract로 잇는다. 검색 키가 둘 다
  없으면 도구 자체가 등록되지 않고 프롬프트가 기능 없음 안내로 강등.

### 2.2 고정 파이프라인 3종 (explainer·analyst·reviewer)

공통 골격과 상한 — 재량은 지정된 노드에만 허용하고 폭주는 구조로 차단:

| 요소 | explainer / reviewer | analyst |
|---|---|---|
| 분기 | triage → chat(기준서 MCP 미니 ReAct) 또는 본 파이프라인 | 동일 (chat은 도구 없음) |
| 증거/입력 | collect(evidence.py, 비LLM: 개요·서명란·수식 지도·주석·블록 정독. 시트 6·28k자) → investigate(Excel 도구 미니 ReAct, 라운드 3·호출 6) | inspect(명시 범위 `시트!A1:C50` 우선, 없으면 최대 값-블록 자동 선택) |
| 본체 LLM | explain/assess — 구조화 출력 + 소견·절차별 standards_query·source_hint 생성 | plan_sql — 구조화 SQL + revise 루프 ≤2 (validate 재검증 필수) |
| 안전 관문 | (입력을 비LLM으로 통제) | sqlglot AST 검증 + DuckDB external_access=false |
| 인용 | cite(LLM 없음): resolve_citation — search(top_k 3)→get_paragraph 재확인, 대상 ≤10건 병렬, 실패는 인용 생략 | 없음 |
| 출력 | report — 결정적 템플릿(①~⑦ + 점검 범위 + 근거 목록 + 고지) | answer — LLM 해석 (SQL·대상 범위·절단 여부 병기, 토큰 스트리밍됨) |
| chat 상한 | 라운드 3·호출 4·결과 6k자 클립 | — |

- 대상 파일 탐지(graph_common.find_target_file): 첨부 표기 → 정확 매칭 →
  토큰 겹침 퍼지(≥2, 최다). 대화 맥락(conversation_context, 최근 6개×600자)을
  triage·plan·answer에 주입해 스레드 후속 질의("그중 상위 3개만") 지원.
- 스트리밍: 고정 그래프는 진행 상황을 custom 스트림(emit)으로 전달. 최종
  보고서는 템플릿 렌더라 토큰 스트리밍이 구조적으로 불가(설계상 수용) —
  analyst의 answer만 LLM 호출이라 토큰이 흐른다.

### 2.3 profiler (기업이해) — 감사 착수 전 회사 이해 브리핑

감사기준서 315의 "기업과 기업환경 이해" 활동을 공개 웹 자료로 보조한다:

- 흐름: triage(브리핑/대화) → plan(LLM이 회사명·초점 파싱, URL은 코드
  정규식 추출) → dart(상장·공시 대상이면 OpenDART로 기업개황·주요
  재무계정 3개년·최근 90일 공시 수집 — 비LLM, `dart_client.py`,
  corpCode 매핑은 프로세스 수명 캐시) → gather(사용자 제공 URL 우선,
  검색 보충은 Tavily 우선·Jina 폴백 — 질의 3~4종(최근 이슈는 topic=news
  90일), 정독 대상은 도메인 중복 배제·4건 상한, 검색 발췌 전체는 폭 보완
  증거로 별도 수집(4k자 클립); 정독할 웹 자료 없이 공시·발췌만 있으면
  extract 생략하고 analyze 직행) → extract(웹 추출 서브그래프 재사용, 자료당 LLM 1회·결과
  5k자 클립) → analyze(구조화 CompanyProfile — DART 수치를 공식 원천으로
  우선, 상충은 명시; 위험 후보에 영향 계정·경영진 주장 명시) →
  cite(resolve_citation 재사용, ≤8건) → report(결정적 템플릿 ①~⑧ +
  조사 자료(DART 첫 줄) + 근거 목록 + "감사증거 아님" 고지).
- LLM 상한: triage 1 + plan 1 + extract ≤4 + analyze ≤2 = 최대 8회
  (dart 노드는 LLM 0회).
- 우아한 강등 사다리: DART 키·검색 키·URL이 전부 없을 때만 fail 안내.
  DART만 있어도, URL만 있어도, 검색 키만 있어도 각각 동작한다.

## 3. 모델 라우팅 (벤더 5종)

| 라우트 키 (`configurable.model`) | 해석 |
|---|---|
| `anthropic:<model-id>` (기본) | Anthropic API. output_version=v1·프롬프트 캐싱(cache_control). 기본 `claude-sonnet-5` |
| `openai:<model-id>` | OpenAI API |
| `google_genai:<model-id>` | Gemini (GOOGLE_API_KEY 또는 GEMINI_API_KEY) |
| `hf:<org/model>` | HF Inference Providers 라우터 (OpenAI 호환, HF_INFERENCE_TOKEN) |
| `local:<model-name>` | 로컬 OpenAI 호환 서버 (Ollama :11434/v1, qwen3:8b-16k) |

- `resolve_model()`이 접두사로 분기, 5개 그래프 공용. max_tokens 8192.
- UI 모델 드롭다운은 `ui/src/lib/models.ts` 레지스트리를 `/api/models`로 받아
  벤더 키가 설정된 모델만 노출, 전송 시 `configurable.model` 주입.

## 4. Excel 도구 명세 (MVP 4종)

모든 도구는 `data/workpapers/` 하위 경로만 허용 (경로 탈출 차단).

| 도구 | 입력 | 출력 |
|---|---|---|
| `excel_workbook_overview` | `path` | 시트별 {이름, 행×열 크기, 첫 행(헤더) 미리보기, 병합 셀 수}. 워크북 전체 지도 |
| `excel_read_range` | `path, sheet, cell_range, mode=values\|formulas` | 범위 셀 값(또는 수식)을 마크다운 표로. 상한: 1회 500셀 — 초과 시 분할 안내 반환 |
| `excel_find` | `path, query, sheet?` | 문자열 매칭 셀 좌표 목록 (계정명·틱마크 탐색용) |
| `excel_sheet_stats` | `path, sheet` | 데이터 밀도, 수식 셀 비율, 숫자/문자 분포 — 정독 우선순위 판단용 |

- 구현: openpyxl `read_only=False`(수식 문자열 접근) + `data_only` 이중 로드.
- 반환은 전부 텍스트(마크다운) — 모델 비의존적.
- 타 언어 도구(예: SpreadsheetLLM 재구현체)는 같은 시그니처의 도구로 감싸 추가 (백로그).

### 4.1 v2 확장 — 서식·의도 채널 (Phase 3.5)

> 설계 배경: [Tool design direction.md](Tool%20design%20direction.md) ·
> 참조 구현: [reference/xlsx_agent_tools.py](reference/xlsx_agent_tools.py)
> (알고리즘 이식원 — 반환 포맷은 JSON 봉투 대신 현행 텍스트 유지, 7절 결정)

| 변경 | 내용 | 참조 구현 관계 |
|---|---|---|
| `excel_workbook_overview` 강화 | 시트별 값/수식 셀 수·시트간 참조 수·`sheet_state`(숨김 시트 노출) + **빈 행 2행 경계 블록 감지** — 블록 ref는 `excel_read_range` 인수로 인계 | `workbook_overview`+`_detect_tables` 이식 |
| `excel_read_range` `mode="format"` | 셀 값 뒤 압축 주석 `[B\|F:RRGGBB\|C:RRGGBB]`. 색상 3계열 분기 — theme는 `T{n}±{tint}` 표기 | 참조 구현은 rgb만 처리 — **theme/indexed 분기는 신규** (한공회 3650A 음영이 전부 theme 계열) |
| `excel_get_annotations` 신설 | 셀 메모·숨김 행/열/시트·데이터 유효성·정의된 이름 | 참조 구현에 없음 — 신규 |
| `excel_formula_map` 신설 | R1C1 정규화 패턴 압축 + 수식 지대 내 하드코딩 숫자 검출 (판정은 에이전트 몫) | `_to_r1c1`+이탈 휴리스틱 이식 |
| `excel_find` `mode="formulas"` | 수식 문자열 검색 — 시트간 참조(`='1100'!…`) 추적 | 참조 구현 `find`는 수식 포함 검색 |
| 잔손질 | 워크북 LRU 캐시(무상태 시그니처 유지) · 마크다운 파이프 이스케이프 · **모든 도구 출력 첫 줄 = 출처**(`시트!범위`) 규약 | `envelope.meta.source`의 텍스트판 |
| 프롬프트 정책 이식 | 수치 주장에 셀 주소 인용 강제 · 합계/증감 암산 금지(원본 셀 재조회 검산) · 절단 안내 시 범위 축소 재호출 | `POLICY_PROMPT` 요지 반영 |

**보류 (백로그)**: 참조 구현의 `read_table`(DataFrame 등록)·`query`(pandas eval) —
계산 위임 가치는 크나 eval은 공개 Space에서 임의 코드 실행 경로가 되므로
격리 방안(subprocess/RestrictedPython)과 함께 재검토.

## 5. MCP 연결

```python
# src/agent/mcp_client.py (개요)
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "auditpaper-standards": {           # 기본: HTTP 원격 (HF Space 상시 배포)
        "transport": "streamable_http",
        "url": MCP_HTTP_URL,            # https://toddl-auditpaper-mcp.hf.space/mcp
        "headers": {"Authorization": f"Bearer {MCP_AUTH_TOKEN}"},
    }
    # 옵션(stdio 로컬 개발): {"transport": "stdio",
    #   "command": "<auditPaper_MCP>/.venv/bin/python",
    #   "args": ["-m", "server.mcp_server"], "cwd": "<auditPaper_MCP>",
    #   "env": {"QDRANT_URL": ..., "QDRANT_API_KEY": ...}}
})
tools = await client.get_tools()   # standards_* 3종이 LangChain 도구로 노출
```

- 전송 방식은 `.env`의 `MCP_TRANSPORT=http|stdio`로 선택, 기본 http —
  백엔드가 HF Spaces에 배포되므로 배포·로컬 개발이 같은 경로를 씀.
- HF Space 기동 직후 약 1분은 임베딩 모델 로드로 `standards_search`만 지연될 수 있음
  (auditPaper_MCP 사용안내) — 첫 검색 타임아웃을 넉넉히 설정.
- 도구 응답의 `collection` 필드·오류 4코드 봉투는 auditPaper_MCP 규약 그대로 통과 —
  에이전트가 `hint`를 보고 다음 행동을 정한다.

## 5.1 인용 표기 계층 — cid 풀어 쓰기 (Phase 5 선행 작업)

cid는 내부 식별자이므로 사용자에게 보이는 본문에는 노출하지 않는다.
**표기 문자열 생성은 코드가, 배치 판단은 프롬프트가** 맡는다:

- **코드**: `get_standards_tools()`에서 도구를 감싸(단순 래퍼 또는
  `tool_interceptors`) `standards_search`/`standards_get_paragraph` 결과의 각 문단에
  메타데이터(`source_type`·`standard_no`·`standard_title`·`para_no`) 기반
  **완성된 표기 문자열**(`display`)을 덧붙인다. 변환 규칙은 auditPaper_MCP 규약을 따름:

  | cid 패턴 | 표기 |
  |---|---|
  | `KIFRS::1115::31` | K-IFRS 제1115호 '고객과의 계약에서 생기는 수익' 문단 31 |
  | `KSA::315::A12` | 감사기준서 315 문단 A12(적용자료) |
  | `GUIDE::2017-1::25` | 회계감사실무지침 2017-1 문단 25 |
  | `KIFRS::1116::BC1` | K-IFRS 제1116호 결론도출근거 BC1 (기준서 본문 아님 병기) |
  | `KIFRS::1103::IE사례5-2` | K-IFRS 제1103호 적용사례 사례 5의 문단 2 |
  | `KSA::240::부록1` / `::정의-<용어>` | 감사기준서 240 부록 1 / '<용어>'의 정의 |

  순수 함수로 구현해 픽스처 페이로드로 단위 테스트한다 (네트워크 불요).
- **프롬프트**: 배치 규칙 2줄만 — "본문에는 도구 결과의 표기 문자열을 사용하고
  cid 원형을 노출하지 말 것. cid는 답변 말미 근거 목록에만 병기할 것."
  (근거 목록의 cid 덕에 `eval/score_interpretation.py` 원문 대조 채점이 그대로 작동)
- **주의**: 프롬프트 교체는 포매터가 붙는 커밋에서 동시에 — 먼저 바꾸면 모델이
  표기를 스스로 조립하다 흔들리는 실패 모드가 생김.

## 6. 조서 파일 전달 (구현 완료)

1. **사전 배치**: 데모 조서(가상)·한공회 공식 서식·공개 더미 CSV를
   `data/workpapers/`에 배치 (배포 이미지 포함, 실데이터 금지)
2. **방문자 업로드**: Excel(xlsx/xlsm/xls)·CSV·Word(docx), 최대 20MB —
   `/api/workpapers`(UI)가 조서 폴더에 저장, 메시지에 `[첨부 파일: 파일명]`
   표기 삽입. Space 재시작 시 휘발
3. 파일 지칭: 첨부 표기 → 파일명·stem 정확 매칭 → 토큰 겹침 퍼지 매칭.
   그래프별 첫 화면 예시 질문(`ui/src/configs/graphs.ts`)이 데모 진입점

## 7. 상태·영속성

- 대화 상태: LangGraph 서버 내장 체크포인터 — 스레드 단위 이어가기는 UI가
  자동 처리. agent는 SummarizationMiddleware로 긴 스레드 압축, 고정 그래프는
  conversation_context 절단(최근 6개×600자)으로 주입분을 경계.
- 조서 파일: 파일시스템 (`data/workpapers/`) — Space에서는 휘발성.
- 별도 DB 없음 (standalone 인증 모드, MVP).

## 8. 오류 처리

| 상황 | 동작 |
|---|---|
| 존재하지 않는 파일 경로 | 도구가 후보 파일 목록과 함께 오류 텍스트 반환 → 에이전트가 되물음 |
| 500셀 초과 범위 요청 | 도구가 분할 읽기 안내 반환 (예외 아님 — 에이전트 자가 수정 유도) |
| MCP 서버 미기동/타임아웃 | `UPSTREAM_UNAVAILABLE` 봉투 → 기준 인용 없이 답하되 그 사실을 명시 |
| 로컬 LLM 엔드포인트 다운 | 요청 실패를 UI에 표면화. 자동 폴백은 LiteLLM 도입 시 (백로그) |
