# 시스템 설계 — ExcelBrief for Newsteps

> 상세 흐름·인터페이스·데이터 계약. 구성요소 개관은 [architecture.md](architecture.md) 참조.

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

## 2. 에이전트 정의

```python
# src/agent/graph.py (개요)
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

def make_graph(config):
    model_spec = config["configurable"].get("model", DEFAULT_MODEL)
    model = resolve_model(model_spec)          # 아래 3절
    tools = excel_tools() + await_mcp_tools()  # 아래 4·5절
    return create_agent(model, tools=tools, system_prompt=SYSTEM_PROMPT)
```

- `langgraph.json`의 graph 진입점이 이 팩토리를 가리킨다.
- 시스템 프롬프트(`prompts.py`)에 조서 해석 지침을 담는다:
  탐색 순서(개요→정독), 인용 규칙(모든 기준 언급에 cid 병기),
  미완성 조서 판단 기준, 범용 Excel일 때의 폴백 동작.

## 3. 모델 라우팅

| 라우트 키 (`configurable.model`) | 해석 |
|---|---|
| `anthropic:<model-id>` (기본) | 상용 Anthropic API. 예: `anthropic:claude-sonnet-5` |
| `local:<model-name>` | 로컬 OpenAI 호환 서버. `init_chat_model("openai:<name>", base_url=LOCAL_LLM_BASE_URL, api_key="unused")` |

- `resolve_model()`이 접두사로 분기. 라우트 추가는 이 함수만 수정.
- `LOCAL_LLM_BASE_URL`은 `.env`로 주입 (vLLM/Ollama 어느 쪽이든 동일 인터페이스).
- UI 쪽은 assistant 설정(`config.configurable`)에 model 값을 넣어 전환.

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

## 6. 조서 파일 전달 (MVP — 공개 데모)

1. **가상 샘플 조서** 2~3건을 `data/workpapers/`에 미리 배치 (배포 이미지에 포함,
   실데이터 미사용)
2. 방문자는 대화에서 파일명으로 지칭하거나, 에이전트가 `list_workpapers()`로
   목록을 제시
3. UI 시작 문구(`chat-openers.yaml`)에 샘플 조서 안내를 넣어
   방문자가 바로 데모를 시작할 수 있게 함

방문자 xlsx 직접 업로드는 UI 포크의 허용 MIME 수정 + 서버 저장 경로 연결로 구현
(백로그 최우선 — 공개 데모 가치가 큼).

## 7. 상태·영속성

- 대화 상태: LangGraph 서버 내장 체크포인터 (`langgraph dev` 기본 제공) —
  스레드 단위 대화 이어가기는 UI가 자동 처리.
- 조서 파일·해석 결과: 파일시스템 (`data/workpapers/`, 필요 시 `reports/`).
- 별도 DB 없음 (MVP).

## 8. 오류 처리

| 상황 | 동작 |
|---|---|
| 존재하지 않는 파일 경로 | 도구가 후보 파일 목록과 함께 오류 텍스트 반환 → 에이전트가 되물음 |
| 500셀 초과 범위 요청 | 도구가 분할 읽기 안내 반환 (예외 아님 — 에이전트 자가 수정 유도) |
| MCP 서버 미기동/타임아웃 | `UPSTREAM_UNAVAILABLE` 봉투 → 기준 인용 없이 답하되 그 사실을 명시 |
| 로컬 LLM 엔드포인트 다운 | 요청 실패를 UI에 표면화. 자동 폴백은 LiteLLM 도입 시 (백로그) |
