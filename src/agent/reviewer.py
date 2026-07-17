"""조서검토 전용 그래프 — langgraph.json의 "reviewer" 진입점.

조서 완성도 점검을 고정 워크플로로 수행한다 (범용 해설은 agent 그래프 몫):

  locate(파일 탐지) → collect(기계 증거 수집) → assess(LLM 구조화 소견)
  → report(결정적 템플릿 렌더)

LLM 호출은 assess 1회뿐이다. 증거 수집(구조·수식 지도·주석·서명란 스캔)은
전부 비LLM이라 재현 가능하고, 보고서 형식은 템플릿이 고정한다.

한계(보고서에 고지): 기준서·지침 근거 인용은 이 그래프가 하지 않는다 —
근거가 필요하면 agent 그래프(기준서 도구 보유)를 사용한다.
"""

from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field, field_validator
from typing_extensions import Annotated, TypedDict

from agent.graph import DEFAULT_MODEL, resolve_model
from agent.graph_common import (
    emit,
    find_target_file,
    human_texts_newest_first,
    missing_file_message,
)
from agent.tools.excel import (
    _detect_blocks,
    _load,
    _resolve,
    excel_formula_map,
    excel_get_annotations,
    excel_read_range,
    excel_workbook_overview,
)

MAX_SHEETS = 6
MAX_BLOCK_CELLS = 400  # 시트당 본문 정독 상한 (excel_read_range 상한 500 미만)
MAX_EVIDENCE_CHARS = 28_000
MAX_ASSESS_ATTEMPTS = 2

SIGNOFF_KEYWORDS = (
    "작성자", "검토자", "작성일", "검토일", "서명", "확인자",
    "Preparer", "Reviewer", "Prepared by", "Reviewed by",
)


# ── 서명란 스캔 (비LLM) ──────────────────────────────────────────────────
def _scan_signoffs(target) -> str:
    """작성/검토 표지 셀을 찾아 같은 셀·오른쪽·아래 셀의 채움 여부를 판정한다."""
    wb = _load(target, data_only=True)
    lines = []
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            continue
        for row in ws.iter_rows():
            for cell in row:
                value = cell.value
                if not isinstance(value, str):
                    continue
                text = value.strip()
                # 긴 문장 속 우연 일치(예: "…검토자는 다음을 확인한다")는 표지가 아님
                if len(text) > 30 or not any(k in text for k in SIGNOFF_KEYWORDS):
                    continue
                inline = text.split(":", 1)[1].strip() if ":" in text else ""
                right = ws.cell(row=cell.row, column=cell.column + 1).value
                below = ws.cell(row=cell.row + 1, column=cell.column).value
                filled = (
                    inline
                    or (str(right).strip() if right is not None else "")
                    or (str(below).strip() if below is not None else "")
                )
                status = f"채움({filled[:20]})" if filled else "공란"
                lines.append(f"- {ws.title}!{cell.coordinate} \"{text}\" → {status}")
    if not lines:
        return "[서명란 스캔] 작성·검토 표지를 찾지 못함"
    return "[서명란 스캔] (표지 셀 → 같은 셀·오른쪽·아래 값 유무)\n" + "\n".join(lines[:40])


def _clip_block_ref(block: dict) -> str:
    """블록을 정독 상한(MAX_BLOCK_CELLS) 이내로 행을 잘라 ref로 만든다."""
    rows = max(1, min(block["rows"], MAX_BLOCK_CELLS // max(1, block["cols"])))
    end_row = block["first_row"] + rows - 1
    return (
        f"{get_column_letter(block['c1'])}{block['first_row']}:"
        f"{get_column_letter(block['c2'])}{end_row}"
    )


def _collect_evidence(path_name: str) -> tuple[str, list[str], list[str]]:
    """검토에 필요한 기계 증거를 기존 도구 함수로 수집한다 (비LLM).

    (증거 텍스트, 점검한 시트, 생략한 시트)를 돌려준다 — 보고서가 점검
    범위를 결정적으로 표기할 수 있게. 서명란 스캔은 핵심 증거라 증거
    선두(개요 직후)에 둔다 — 뒤에 두면 MAX_EVIDENCE_CHARS 절단 시 가장
    먼저 잘려나간다.
    """
    target = _resolve(path_name)
    wb = _load(target, data_only=True)
    visible = [ws for ws in wb.worksheets if ws.sheet_state == "visible"]
    examined = [ws.title for ws in visible[:MAX_SHEETS]]
    skipped = [ws.title for ws in visible[MAX_SHEETS:]]
    parts = [excel_workbook_overview.func(path_name), _scan_signoffs(target)]
    for ws in visible[:MAX_SHEETS]:
        parts.append(excel_formula_map.func(path_name, ws.title))
        parts.append(excel_get_annotations.func(path_name, ws.title))
        blocks = _detect_blocks(ws)
        if blocks:
            largest = max(blocks, key=lambda b: b["rows"] * b["cols"])
            parts.append(
                excel_read_range.func(path_name, ws.title, _clip_block_ref(largest))
            )
    if skipped:
        parts.append(
            f"(주의: 시트 {len(skipped)}개는 증거 수집에서 생략됨 — "
            f"상한 {MAX_SHEETS}개: {', '.join(skipped)})"
        )
    evidence = "\n\n".join(parts)
    if len(evidence) > MAX_EVIDENCE_CHARS:
        evidence = evidence[:MAX_EVIDENCE_CHARS] + "\n… (증거 절단 — 상한 초과)"
    return evidence, examined, skipped


# ── LLM 구조화 소견 ──────────────────────────────────────────────────────
class Finding(BaseModel):
    title: str = Field(description="소견 한 줄 요약")
    severity: Literal["높음", "중간", "낮음"]
    location: str = Field(description="근거 위치 — 시트!셀 또는 시트!범위, 없으면 시트명")
    detail: str = Field(description="무엇이 왜 문제/필요한지 신입 회계사가 이해할 설명")


class ReviewFindings(BaseModel):
    workpaper_purpose: str = Field(description="이 조서의 목적·대상 계정 한두 문장")
    performed_procedures: list[str] = Field(description="증거에서 확인되는 수행된 절차")
    missing_procedures: list[Finding] = Field(description="누락되었거나 미완성인 절차")
    signoff_assessment: str = Field(description="서명란 스캔 결과 해석 — 작성·검토 완료 여부")
    tieout_findings: list[Finding] = Field(
        description="검산·tie-out·하드코딩 관련 소견 (수식 지도의 하드코딩 숫자 포함)"
    )
    open_items: list[str] = Field(description="미결 항목·공란·추가 확인 필요 사항")
    overall: str = Field(description="완성도 총평 두세 문장")

    @field_validator("missing_procedures", "tieout_findings", mode="before")
    @classmethod
    def _coerce_str_findings(cls, value):
        """약한 모델이 Finding 객체 대신 문자열 리스트를 내는 경우를 승격한다 (Haiku 실측)."""
        if isinstance(value, list):
            return [
                {"title": v[:80], "severity": "중간", "location": "(미표기)", "detail": v}
                if isinstance(v, str)
                else v
                for v in value
            ]
        return value


class ReviewerState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    question: str
    path: str
    evidence: str
    examined: list  # 증거를 수집한 시트
    skipped: list  # 상한 초과로 생략된 시트
    findings: dict
    attempts: int
    error: str | None


def _render_report(
    path: str,
    findings: ReviewFindings,
    examined: list[str] | None = None,
    skipped: list[str] | None = None,
) -> str:
    def _finding_lines(items: list[Finding]) -> list[str]:
        if not items:
            return ["- (해당 없음)"]
        order = {"높음": 0, "중간": 1, "낮음": 2}
        return [
            f"- [{f.severity}] {f.title} ({f.location})\n  {f.detail}"
            for f in sorted(items, key=lambda f: order[f.severity])
        ]

    def _bullets(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items] or ["- (해당 없음)"]

    lines = [
        f"# 조서 검토 보고 — {path}",
        "",
        "## ① 조서 개요",
        findings.workpaper_purpose,
        "",
        "## ② 수행된 절차 (증거 기준)",
        *_bullets(findings.performed_procedures),
        "",
        "## ③ 서명·검토 상태",
        findings.signoff_assessment,
        "",
        "## ④ 검산·tie-out 점검",
        *_finding_lines(findings.tieout_findings),
        "",
        "## ⑤ 누락·추가 필요 절차",
        *_finding_lines(findings.missing_procedures),
        "",
        "## ⑥ 미결 항목",
        *_bullets(findings.open_items),
        "",
        "## ⑦ 총평",
        findings.overall,
        "",
    ]
    if examined:
        lines += [
            "## 점검 범위",
            f"- 점검한 시트({len(examined)}개): {', '.join(examined)}",
            (
                f"- 생략된 시트({len(skipped)}개, 상한 {MAX_SHEETS}개 초과): "
                f"{', '.join(skipped)} — 필요하면 해당 시트만 담긴 파일로 다시 요청하세요."
                if skipped
                else "- 생략된 시트: 없음"
            ),
            "",
        ]
    lines += [
        "---",
        "*이 보고서는 조서 파일의 기계 수집 증거(구조·수식·주석·서명란)만으로 "
        "작성되었습니다. 감사기준서·K-IFRS 근거 인용이 필요하면 agent 그래프"
        "(기준서 도구)를 사용하세요. 수식 값은 파일에 저장된 캐시 값 기준입니다.*",
    ]
    return "\n".join(lines)


class ReviewerNodes:
    def __init__(self, model) -> None:
        self.model = model

    def locate(self, state: ReviewerState) -> dict[str, Any]:
        emit("locating", "검토할 조서 파일을 찾는 중")
        texts = human_texts_newest_first(state)
        question = texts[0].strip() if texts else ""
        target = find_target_file(texts)
        if target is None:
            return {
                "question": question,
                "error": missing_file_message("검토할 Excel 조서를 찾지 못했습니다."),
            }
        return {"question": question, "path": target.name, "attempts": 0, "error": None}

    def route_locate(self, state: ReviewerState) -> Literal["collect", "fail"]:
        return "fail" if state.get("error") else "collect"

    def collect(self, state: ReviewerState) -> dict[str, Any]:
        emit("collecting", f"증거 수집 중: {state['path']} (구조·수식·주석·서명란)")
        try:
            evidence, examined, skipped = _collect_evidence(state["path"])
            return {
                "evidence": evidence,
                "examined": examined,
                "skipped": skipped,
                "error": None,
            }
        except ValueError as exc:
            return {"error": str(exc)}

    def route_collect(self, state: ReviewerState) -> Literal["assess", "fail"]:
        return "fail" if state.get("error") else "assess"

    def assess(self, state: ReviewerState) -> dict[str, Any]:
        attempt = state.get("attempts", 0) + 1
        emit("assessing", "수집된 증거로 완성도를 평가하는 중", attempt=attempt)
        assessor = self.model.with_structured_output(ReviewFindings)
        try:
            result = assessor.invoke(
                [
                    SystemMessage(
                        content=(
                            "당신은 회계법인의 감사조서 검토자입니다. 제공된 기계 수집 "
                            "증거(워크북 구조·수식 지도·주석·서명란 스캔)만 사용해 조서 "
                            "완성도를 평가하세요. 증거에 없는 내용을 추정하지 말고, 모든 "
                            "소견에 근거 위치(시트!셀)를 표기하세요. 수식 지도의 하드코딩 "
                            "숫자는 오류일 수도 의도된 입력일 수도 있으니 맥락으로 "
                            "판단하되 단정하지 마세요. 기준서 번호 인용은 하지 마세요 — "
                            "원문 확인 도구가 없는 모드입니다."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"검토 요청: {state.get('question', '조서 완성도를 점검해줘')}\n"
                            f"대상 파일: {state['path']}\n\n[수집 증거]\n{state['evidence']}"
                        )
                    ),
                ]
            )
            findings = (
                result
                if isinstance(result, ReviewFindings)
                else ReviewFindings.model_validate(result)
            )
            return {"findings": findings.model_dump(), "attempts": attempt, "error": None}
        except Exception as exc:  # 구조화 출력 실패·일시 오류 → 재시도 후 fail
            return {"attempts": attempt, "error": f"소견 생성 실패 — {exc}"}

    def route_assess(self, state: ReviewerState) -> Literal["report", "retry", "fail"]:
        if not state.get("error"):
            return "report"
        if state.get("attempts", 0) < MAX_ASSESS_ATTEMPTS:
            return "retry"
        return "fail"

    def report(self, state: ReviewerState) -> dict[str, Any]:
        emit("reporting", "검토 보고서를 작성하는 중")
        findings = ReviewFindings.model_validate(state["findings"])
        text = _render_report(
            state["path"],
            findings,
            state.get("examined"),
            state.get("skipped"),
        )
        emit("complete", "조서 검토 완료")
        return {"messages": [AIMessage(content=text)], "error": None}

    def fail(self, state: ReviewerState) -> dict[str, Any]:
        message = state.get("error") or "조서 검토에 실패했습니다."
        emit("failed", message)
        return {"messages": [AIMessage(content=f"오류: {message}")]}


async def reviewer(config: RunnableConfig):
    """요청 config로 모델을 정해 조서검토 그래프를 조립한다 (langgraph 서버가 호출)."""
    model_spec = (config.get("configurable") or {}).get("model", DEFAULT_MODEL)
    nodes = ReviewerNodes(resolve_model(model_spec))

    builder = StateGraph(ReviewerState)
    builder.add_node("locate", nodes.locate)
    builder.add_node("collect", nodes.collect)
    builder.add_node("assess", nodes.assess)
    builder.add_node("report", nodes.report)
    builder.add_node("fail", nodes.fail)

    builder.add_edge(START, "locate")
    builder.add_conditional_edges(
        "locate", nodes.route_locate, {"collect": "collect", "fail": "fail"}
    )
    builder.add_conditional_edges(
        "collect", nodes.route_collect, {"assess": "assess", "fail": "fail"}
    )
    builder.add_conditional_edges(
        "assess",
        nodes.route_assess,
        {"report": "report", "retry": "assess", "fail": "fail"},
    )
    builder.add_edge("report", END)
    builder.add_edge("fail", END)
    return builder.compile()
