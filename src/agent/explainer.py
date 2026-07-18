"""조서 해설 전용 그래프 — langgraph.json의 "explainer" 진입점.

조서 하나를 정독해 신입 회계사 눈높이로 해설하는 고정 워크플로:

  triage(해설/대화 분기) → locate(파일 탐지) → collect(기계 증거 수집)
  → investigate(증거 충분성 점검·보충 조사, 미니 ReAct) → explain(LLM
  구조화 해설) → cite(기준서 근거 검색·확정, MCP) → report(템플릿 렌더)

reviewer(완성도 점검)와 골격은 같지만 산출물이 다르다 — 무엇이 빠졌는지가
아니라 이 조서가 무엇이고, 어떤 절차가 왜 수행됐고, 어떤 기준에 근거하는지,
어떻게 읽는지를 설명한다. 증거 수집(evidence.py)과 인용 확정
(standards_lookup.py)은 reviewer와 공용 계층이다.

범용 잡식 질문은 all-in-one인 agent 그래프 몫이다.
"""

import asyncio
from typing import Any, Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, field_validator
from typing_extensions import Annotated, TypedDict

from agent.evidence import MAX_SHEETS, collect_workpaper_evidence
from agent.graph import DEFAULT_MODEL, resolve_model
from agent.graph_common import (
    conversation_context,
    emit,
    find_target_file,
    human_texts_newest_first,
    missing_file_message,
)
from agent.mcp_client import get_standards_tools
from agent.standards_lookup import resolve_citation, tool_text
from agent.tools.excel import (
    excel_find,
    excel_formula_map,
    excel_get_annotations,
    excel_read_range,
    excel_sheet_stats,
    list_workpapers,
)

MAX_EXPLAIN_ATTEMPTS = 2

# investigate 미니 ReAct의 상한 (reviewer와 동일 패턴)
MAX_INVESTIGATE_ROUNDS = 3
MAX_INVESTIGATE_CALLS = 6
MAX_TOOL_RESULT_CHARS = 6_000
MAX_EXTRA_EVIDENCE_CHARS = 8_000

MAX_CITED_NOTES = 10  # cite가 근거를 찾는 절차 해설 수

# chat 미니 ReAct(기준서 도구)의 상한
MAX_CHAT_TOOL_ROUNDS = 3
MAX_CHAT_TOOL_CALLS = 4

INVESTIGATE_TOOLS = (
    excel_read_range,
    excel_sheet_stats,
    excel_find,
    excel_formula_map,
    excel_get_annotations,
)


# ── LLM 구조화 해설 ──────────────────────────────────────────────────────
class TriageDecision(BaseModel):
    mode: Literal["explain", "chat"] = Field(
        description=(
            "explain: 조서 파일의 해설·설명·해석 요청. "
            "chat: 인사·사용법 질문·기능 문의·이전 해설에 대한 후속 설명 등 "
            "조서를 새로 읽을 필요가 없는 대화."
        )
    )


class ProcedureNote(BaseModel):
    procedure: str = Field(description="수행된(또는 서식이 요구하는) 감사절차 한 줄 요약")
    location: str = Field(
        description=(
            "근거 위치 — 셀 좌표만 쓰지 말고 사람이 읽는 설명에 좌표를 "
            "괄호로 붙인다. 예: '5410 조회서 시트의 회신결과 표(B5:F12)'"
        )
    )
    interpretation: str = Field(
        description=(
            "이 절차를 왜 하는지, 조서에서 어떻게 수행됐는지 신입 눈높이 해설 "
            "— 두세 문장으로 간결히"
        )
    )
    assertion: str = Field(
        default="",
        description=(
            "이 절차가 다루는 경영진 주장의 명칭만 — 존재성·완전성·평가와 배분"
            "(정확성)·권리와 의무·발생사실·기간귀속·표시와 공시 중에서 (여러 "
            "개면 쉼표 구분, 예: '존재성, 평가'). 문장으로 쓰지 말 것. 주장과 "
            "무관한 서식 안내면 빈 문자열"
        ),
    )
    risk_addressed: str = Field(
        default="",
        description=(
            "이 절차가 없으면 무엇이 잘못될 수 있는지 — 40자 내외 한 문장 "
            "(예: '실재하지 않는 매출채권이 장부에 남는다'). 두 문장 이상 금지"
        ),
    )
    standards_query: str = Field(
        default="",
        description=(
            "이 절차의 근거가 될 기준서 검색어 — 한국어 핵심 개념 위주. "
            "기준서 근거가 필요 없으면 빈 문자열"
        ),
    )
    source_hint: Literal["감사기준", "회계기준", "실무지침", ""] = Field(
        default="", description="검색을 한정할 문서군 — 불확실하면 빈 문자열"
    )
    citation: str = Field(default="", description="(시스템이 채움) 확정 인용 표기")
    citation_cid: str = Field(default="", description="(시스템이 채움) 인용 cid")


class TermNote(BaseModel):
    term: str = Field(description="조서에 등장하는 용어·약어·틱마크")
    explanation: str = Field(description="신입이 이해할 한두 문장 풀이")


class WorkpaperBrief(BaseModel):
    workpaper_purpose: str = Field(
        description="이 조서가 무엇을 위한 것인지 — 대상 계정·감사 목적 두세 문장"
    )
    sheet_roles: list[str] = Field(
        description="시트별 구성과 역할 — '시트명: 역할' 형태 한 줄씩"
    )
    performed_procedures: list[ProcedureNote] = Field(
        description="조서에서 확인되는(또는 서식이 요구하는) 절차와 해설"
    )
    reading_tips: list[str] = Field(
        description="조서 읽는 법 — 틱마크·범례·서명란·수식 흐름 등 관찰 포인트"
    )
    open_items: list[str] = Field(
        description="미완 항목·후속 확인이 필요한 부분 (없으면 빈 리스트)"
    )
    terms: list[TermNote] = Field(description="신입용 용어 풀이 (핵심 위주 최대 8개)")
    overall: str = Field(description="이 조서를 한눈에 요약하는 총평 두세 문장")

    @field_validator("performed_procedures", mode="before")
    @classmethod
    def _coerce_str_procedures(cls, value):
        """약한 모델이 문자열 리스트를 내는 경우를 승격한다 (reviewer 실측 패턴)."""
        if isinstance(value, list):
            return [
                {
                    "procedure": v[:80],
                    "location": "(미표기)",
                    "interpretation": v,
                }
                if isinstance(v, str)
                else v
                for v in value
            ]
        return value

    @field_validator("terms", mode="before")
    @classmethod
    def _coerce_str_terms(cls, value):
        if isinstance(value, list):
            return [
                {"term": v.split(":", 1)[0][:40], "explanation": v}
                if isinstance(v, str)
                else v
                for v in value
            ]
        return value


class ExplainerState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    question: str
    mode: str  # "explain" | "chat" — triage 분기 결과
    path: str
    evidence: str
    extra_evidence: str
    examined: list
    skipped: list
    brief: dict
    attempts: int
    error: str | None


def _render_brief(
    path: str,
    brief: WorkpaperBrief,
    examined: list[str] | None = None,
    skipped: list[str] | None = None,
) -> str:
    def _bullets(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items] or ["- (해당 없음)"]

    lines = [
        f"# 조서 해설 — {path}",
        "",
        "## ① 이 조서는 무엇인가",
        brief.workpaper_purpose,
        "",
        "## ② 시트 구성",
        *_bullets(brief.sheet_roles),
        "",
        "## ③ 수행된 절차 해설",
    ]
    if brief.performed_procedures:
        # 하위 불릿 구조 — 마크다운이 연속 줄을 한 문단으로 접는 것을 막는다
        for note in brief.performed_procedures:
            line = f"- **{note.procedure}** ({note.location})"
            tags = " · ".join(
                t
                for t in (
                    f"주장: {note.assertion}" if note.assertion else "",
                    f"대응 위험: {note.risk_addressed}" if note.risk_addressed else "",
                )
                if t
            )
            if tags:
                line += f"\n  - _{tags}_"
            line += f"\n  - {note.interpretation}"
            if note.citation:
                line += f"\n  - 근거: {note.citation}"
            lines.append(line)
    else:
        lines.append("- (해당 없음)")
    lines += [
        "",
        "## ④ 조서 읽는 법",
        *_bullets(brief.reading_tips),
        "",
        "## ⑤ 미완·후속 확인 항목",
        *_bullets(brief.open_items),
        "",
        "## ⑥ 용어 풀이",
        *(
            [f"- **{t.term}**: {t.explanation}" for t in brief.terms]
            or ["- (해당 없음)"]
        ),
        "",
        "## ⑦ 한눈 요약",
        brief.overall,
        "",
    ]
    if examined:
        lines += [
            "## 점검 범위",
            f"- 정독한 시트({len(examined)}개): {', '.join(examined)}",
            (
                f"- 생략된 시트({len(skipped)}개, 상한 {MAX_SHEETS}개 초과): "
                f"{', '.join(skipped)} — 필요하면 해당 시트만 담긴 파일로 다시 요청하세요."
                if skipped
                else "- 생략된 시트: 없음"
            ),
            "",
        ]
    cited = [n for n in brief.performed_procedures if n.citation_cid]
    if cited:
        seen: set[str] = set()
        lines.append("## 근거 목록")
        for note in cited:
            if note.citation_cid in seen:
                continue
            seen.add(note.citation_cid)
            lines.append(f"- {note.citation} — `{note.citation_cid}`")
        lines.append("")
    lines += [
        "---",
        "*이 해설은 조서 파일의 기계 수집 증거(구조·수식·주석·서명란)와 자동 "
        "보충 조사로 작성되었습니다. 기준서 근거는 절차별 자동 검색으로 원문을 "
        "재확인한 문단(cid 병기)만 인용하며, 인용이 없는 절차는 근거 미확정입니다. "
        "수식 값은 파일에 저장된 캐시 값 기준입니다.*",
    ]
    return "\n".join(lines)


class ExplainerNodes:
    def __init__(self, model) -> None:
        self.model = model

    def triage(self, state: ExplainerState) -> dict[str, Any]:
        """해설 요청인지 일반 대화인지 분기한다 (reviewer와 동일 패턴)."""
        emit("triaging", "요청 유형을 판단하는 중")
        texts = human_texts_newest_first(state)
        question = texts[0].strip() if texts else ""
        if not question:
            return {"question": question, "mode": "chat", "error": None}
        has_file = find_target_file(texts) is not None
        context = conversation_context(state)
        context_part = f"이전 대화:\n{context}\n" if context else ""
        try:
            decider = self.model.with_structured_output(TriageDecision)
            result = decider.invoke(
                [
                    SystemMessage(
                        content=(
                            "당신은 감사조서 해설 에이전트의 라우터입니다. 사용자 "
                            "메시지가 조서 파일의 해설·설명·해석 요청이면 explain, "
                            "인사·사용법 질문·기능 문의·이전 해설에 대한 후속 "
                            "설명처럼 조서를 새로 읽을 필요가 없는 대화면 chat으로 "
                            "분류하세요. 다른 파일이나 같은 파일의 해설을 새로 "
                            "요청하면 explain입니다."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"{context_part}"
                            f"메시지: {question}\n"
                            f"메시지에 해설 대상 파일 언급 존재: {has_file}"
                        )
                    ),
                ]
            )
            decision = (
                result
                if isinstance(result, TriageDecision)
                else TriageDecision.model_validate(result)
            )
            mode = decision.mode
        except Exception:
            mode = "explain" if has_file else "chat"
        return {"question": question, "mode": mode, "error": None}

    def route_triage(self, state: ExplainerState) -> Literal["explain", "chat"]:
        return "chat" if state.get("mode") == "chat" else "explain"

    async def chat(self, state: ExplainerState) -> dict[str, Any]:
        """조서를 새로 읽지 않는 일반 대화 — 기준서 도구를 쥔 미니 ReAct."""
        emit("chatting", "일반 대화로 응답하는 중")
        standards = await get_standards_tools()
        tools_by_name = {t.name: t for t in standards}
        # async 노드에서 동기 파일 I/O는 blockbuster가 차단 — 스레드로 우회
        listing = await asyncio.to_thread(list_workpapers.func)
        citation_rule = (
            (
                "대화 맥락에 이미 확정돼 있는 기준서 인용(근거·근거 목록의 "
                "표기와 cid)은 도구 없이 그대로 옮겨 설명해도 됩니다. 새로운 "
                "기준서 근거가 필요하면 standards_search로 찾고, 인용을 확정할 "
                "문단은 standards_get_paragraph(cid)로 원문을 확인한 뒤 표기와 "
                "cid를 병기해 인용하세요. 낯선 용어는 standards_define_terms로 "
                "확인합니다. 도구로 확인하지 못한 번호는 인용하지 마세요. "
                f"도구 호출은 꼭 필요할 때만, 총 {MAX_CHAT_TOOL_CALLS}회 "
                "이내로 사용하세요."
            )
            if standards
            else (
                "대화 맥락에 이미 확정돼 있는 기준서 인용은 그대로 옮겨 설명해도 "
                "됩니다. 다만 맥락에 없는 기준서 번호를 새로 인용하지는 마세요 — "
                "지금은 원문 확인 도구가 연결돼 있지 않습니다."
            )
        )
        messages: list = [
            SystemMessage(
                content=(
                    "당신은 '조서 해설 Agent'입니다 — 감사조서 파일 하나를 정독해 "
                    "구조·수행 절차·근거 기준을 신입 회계사 눈높이로 해설하는 "
                    "모드입니다. 지금 요청은 조서를 새로 읽을 필요가 없는 일반 "
                    "대화로 분류되었습니다. 한국어로 간결히 답하고, 사용법을 "
                    "물으면 안내하세요: 해설할 파일을 첨부하거나 파일명을 언급해 "
                    "요청합니다. 이전 해설에 대한 후속 질문이면 대화 맥락의 해설 "
                    "내용으로 답하고, 조서를 새로 봐야 하는 질문이면 해설을 다시 "
                    f"요청해 달라고 안내하세요. {citation_rule}\n\n"
                    f"[현재 볼 수 있는 파일]\n{listing}"
                )
            ),
            *state["messages"],
        ]
        model = self.model
        if standards:
            try:
                model = self.model.bind_tools(standards)
            except Exception:
                model = self.model

        response = None
        calls_used = 0
        for round_no in range(MAX_CHAT_TOOL_ROUNDS + 1):
            response = await model.ainvoke(messages)
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls or round_no == MAX_CHAT_TOOL_ROUNDS:
                break
            messages.append(response)
            for call in tool_calls:
                if calls_used >= MAX_CHAT_TOOL_CALLS:
                    messages.append(
                        ToolMessage(
                            content="(도구 호출 상한 도달 — 지금까지의 정보로 답하세요)",
                            tool_call_id=call["id"],
                        )
                    )
                    continue
                emit("chatting", f"기준서 확인: {call['name']}")
                tool = tools_by_name.get(call["name"])
                try:
                    result = (
                        await tool_text(tool, call["args"])
                        if tool
                        else f"오류: 알 수 없는 도구 {call['name']}"
                    )
                except Exception as exc:
                    result = f"오류: {exc}"
                calls_used += 1
                messages.append(
                    ToolMessage(
                        content=str(result)[:MAX_TOOL_RESULT_CHARS],
                        tool_call_id=call["id"],
                    )
                )
        emit("complete", "응답 완료")
        return {"messages": [response], "error": None}

    def locate(self, state: ExplainerState) -> dict[str, Any]:
        emit("locating", "해설할 조서 파일을 찾는 중")
        texts = human_texts_newest_first(state)
        question = texts[0].strip() if texts else ""
        target = find_target_file(texts)
        if target is None:
            return {
                "question": question,
                "error": missing_file_message("해설할 Excel 조서를 찾지 못했습니다."),
            }
        return {"question": question, "path": target.name, "attempts": 0, "error": None}

    def route_locate(self, state: ExplainerState) -> Literal["collect", "fail"]:
        return "fail" if state.get("error") else "collect"

    def collect(self, state: ExplainerState) -> dict[str, Any]:
        emit("collecting", f"증거 수집 중: {state['path']} (구조·수식·주석·서명란)")
        try:
            evidence, examined, skipped = collect_workpaper_evidence(state["path"])
            return {
                "evidence": evidence,
                "examined": examined,
                "skipped": skipped,
                "error": None,
            }
        except ValueError as exc:
            return {"error": str(exc)}

    def route_collect(self, state: ExplainerState) -> Literal["explain", "fail"]:
        return "fail" if state.get("error") else "explain"

    def investigate(self, state: ExplainerState) -> dict[str, Any]:
        """기본 증거의 충분성을 점검하고 부족분만 도구로 보충한다 (미니 ReAct)."""
        emit("investigating", "증거 충분성을 점검하고 부족분을 조사하는 중")
        path = state["path"]
        tools_by_name = {t.name: t for t in INVESTIGATE_TOOLS}
        try:
            model_with_tools = self.model.bind_tools(list(INVESTIGATE_TOOLS))
        except Exception:
            return {"extra_evidence": ""}

        messages: list = [
            SystemMessage(
                content=(
                    "당신은 감사조서 해설자입니다. 아래 기본 증거로 조서를 해설 "
                    "하기에 충분한지 점검하고, 부족한 부분만 도구로 보충 조사하세요 "
                    "— 예: 증거 수집에서 생략된 시트, 잘려 읽힌 블록의 나머지, "
                    "범례·틱마크·설명 셀 확인. 모든 도구의 path 인수는 "
                    f"'{path}'입니다. 도구 호출은 총 {MAX_INVESTIGATE_CALLS}회 "
                    "까지입니다. 증거가 이미 충분하면 도구를 호출하지 말고 "
                    "'증거 충분'이라고만 답하세요."
                )
            ),
            HumanMessage(
                content=(
                    f"해설 요청: {state.get('question', '이 조서를 해설해줘')}\n"
                    f"대상 파일: {path}\n\n[기본 증거]\n{state['evidence']}"
                )
            ),
        ]
        extra_parts: list[str] = []
        calls_used = 0
        for _ in range(MAX_INVESTIGATE_ROUNDS):
            try:
                response = model_with_tools.invoke(messages)
            except Exception:
                break
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                break
            messages.append(response)
            for call in tool_calls:
                if calls_used >= MAX_INVESTIGATE_CALLS:
                    messages.append(
                        ToolMessage(
                            content="(도구 호출 상한 도달)", tool_call_id=call["id"]
                        )
                    )
                    continue
                tool = tools_by_name.get(call["name"])
                try:
                    result = (
                        tool.func(**call["args"])
                        if tool
                        else f"오류: 알 수 없는 도구 {call['name']}"
                    )
                except Exception as exc:
                    result = f"오류: {exc}"
                calls_used += 1
                result = str(result)[:MAX_TOOL_RESULT_CHARS]
                extra_parts.append(f"[추가 조사: {call['name']} {call['args']}]\n{result}")
                messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
        if calls_used:
            emit("investigating", f"보충 조사 {calls_used}건 수행")
        extra = "\n\n".join(extra_parts)[:MAX_EXTRA_EVIDENCE_CHARS]
        return {"extra_evidence": extra}

    def explain(self, state: ExplainerState) -> dict[str, Any]:
        attempt = state.get("attempts", 0) + 1
        emit("explaining", "수집된 증거로 조서를 해설하는 중", attempt=attempt)
        explainer_model = self.model.with_structured_output(WorkpaperBrief)
        try:
            result = explainer_model.invoke(
                [
                    SystemMessage(
                        content=(
                            "당신은 회계법인의 시니어로서 신입에게 감사조서를 "
                            "설명합니다. 제공된 기계 수집 증거(워크북 구조·수식 "
                            "지도·주석·서명란 스캔)와 추가 조사 결과만 사용해 "
                            "조서를 해설하세요. 증거에 없는 내용을 추정하지 마세요. "
                            "근거 위치는 셀 좌표만 나열하면 신입이 알아듣지 "
                            "못합니다 — '어느 시트의 무엇(셀주소)'처럼 그 위치가 "
                            "무엇인지 설명하고 좌표는 괄호로 붙이세요. 빈 서식이면 "
                            "각 칸에 무엇을 채워야 하는지를 해설하세요. 해설의 "
                            "관점: 각 절차를 '경영진 주장 → 위험 → 절차 → 증거' "
                            "사슬로 설명하세요 — assertion에 절차가 다루는 주장을, "
                            "risk_addressed에 이 절차가 없으면 무엇이 잘못될 수 "
                            "있는지를 채우고, interpretation은 그 주장·위험과 "
                            "연결해 서술하세요. 관찰 나열('B5에 합계가 있다')이 "
                            "아니라 목적 설명('매출채권의 실재성을 확인하기 위해 "
                            "…')이 되어야 합니다. 분량을 지키세요 — assertion은 "
                            "주장 명칭만, risk_addressed는 한 문장, interpretation은 "
                            "두세 문장. 길게 쓰면 보고서가 읽히지 않습니다. 기준서 "
                            "번호를 본문에 직접 인용하지 말고, 근거가 필요한 "
                            "절차에는 standards_query(한국어 검색어)와 source_hint를 "
                            "채우세요 — 원문 확인과 인용 확정은 시스템이 수행합니다."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"해설 요청: {state.get('question', '이 조서를 해설해줘')}\n"
                            f"대상 파일: {state['path']}\n\n[수집 증거]\n{state['evidence']}"
                            + (
                                f"\n\n[추가 조사]\n{state['extra_evidence']}"
                                if state.get("extra_evidence")
                                else ""
                            )
                        )
                    ),
                ]
            )
            brief = (
                result
                if isinstance(result, WorkpaperBrief)
                else WorkpaperBrief.model_validate(result)
            )
            return {"brief": brief.model_dump(), "attempts": attempt, "error": None}
        except Exception as exc:  # 구조화 출력 실패·일시 오류 → 재시도 후 fail
            return {"attempts": attempt, "error": f"해설 생성 실패 — {exc}"}

    def route_explain(self, state: ExplainerState) -> Literal["cite", "retry", "fail"]:
        if not state.get("error"):
            return "cite"
        if state.get("attempts", 0) < MAX_EXPLAIN_ATTEMPTS:
            return "retry"
        return "fail"

    async def cite(self, state: ExplainerState) -> dict[str, Any]:
        """절차 해설의 기준서 근거를 검색·재확인해 확정한다 (LLM 없음, 결정적)."""
        emit("citing", "절차 해설의 기준서 근거를 검색·확정하는 중")
        brief = WorkpaperBrief.model_validate(state["brief"])
        tools = {t.name: t for t in await get_standards_tools()}
        search = tools.get("standards_search")
        get_para = tools.get("standards_get_paragraph")
        if search is None or get_para is None:
            return {"brief": brief.model_dump()}

        targets = [n for n in brief.performed_procedures if n.standards_query][
            :MAX_CITED_NOTES
        ]

        async def _cite_one(note: ProcedureNote) -> bool:
            resolved = await resolve_citation(
                search, get_para, note.standards_query, note.source_hint
            )
            if resolved is None:
                return False
            note.citation, note.citation_cid = resolved
            return True

        cited = sum(await asyncio.gather(*(_cite_one(n) for n in targets)))
        if cited:
            emit("citing", f"기준서 근거 {cited}건 확정")
        return {"brief": brief.model_dump()}

    def report(self, state: ExplainerState) -> dict[str, Any]:
        emit("reporting", "해설 문서를 작성하는 중")
        brief = WorkpaperBrief.model_validate(state["brief"])
        text = _render_brief(
            state["path"],
            brief,
            state.get("examined"),
            state.get("skipped"),
        )
        emit("complete", "조서 해설 완료")
        return {"messages": [AIMessage(content=text)], "error": None}

    def fail(self, state: ExplainerState) -> dict[str, Any]:
        message = state.get("error") or "조서 해설에 실패했습니다."
        emit("failed", message)
        return {"messages": [AIMessage(content=f"오류: {message}")]}


async def explainer(config: RunnableConfig):
    """요청 config로 모델을 정해 조서 해설 그래프를 조립한다 (langgraph 서버가 호출)."""
    model_spec = (config.get("configurable") or {}).get("model", DEFAULT_MODEL)
    nodes = ExplainerNodes(resolve_model(model_spec))

    builder = StateGraph(ExplainerState)
    builder.add_node("triage", nodes.triage)
    builder.add_node("chat", nodes.chat)
    builder.add_node("locate", nodes.locate)
    builder.add_node("collect", nodes.collect)
    builder.add_node("investigate", nodes.investigate)
    builder.add_node("explain", nodes.explain)
    builder.add_node("cite", nodes.cite)
    builder.add_node("report", nodes.report)
    builder.add_node("fail", nodes.fail)

    builder.add_edge(START, "triage")
    builder.add_conditional_edges(
        "triage", nodes.route_triage, {"explain": "locate", "chat": "chat"}
    )
    builder.add_edge("chat", END)
    builder.add_conditional_edges(
        "locate", nodes.route_locate, {"collect": "collect", "fail": "fail"}
    )
    builder.add_conditional_edges(
        "collect", nodes.route_collect, {"explain": "investigate", "fail": "fail"}
    )
    builder.add_edge("investigate", "explain")
    builder.add_conditional_edges(
        "explain",
        nodes.route_explain,
        {"cite": "cite", "retry": "explain", "fail": "fail"},
    )
    builder.add_edge("cite", "report")
    builder.add_edge("report", END)
    builder.add_edge("fail", END)
    return builder.compile()
