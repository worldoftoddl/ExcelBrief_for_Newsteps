"""analyst 그래프 테스트 — 파일 탐지·블록 선택·비LLM 노드는 단위로,
전체 파이프라인은 실제 API(skipif)로 검증한다."""

import os

import pytest
from langchain_core.messages import HumanMessage
from openpyxl import Workbook

from agent.analyst import (
    AnalystNodes,
    _find_target_file,
    _pick_table_block,
    analyst,
)

FILE = "표본_지출.xlsx"
SHEET = "지출"


@pytest.fixture()
def table_dir(tmp_path, monkeypatch):
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    ws["A1"] = "부서별 지출 내역"
    rows = [
        ["부서", "항목", "금액"],
        ["감사1본부", "출장비", 500],
        ["감사1본부", "교육비", 300],
        ["감사2본부", "출장비", 700],
    ]
    for i, row in enumerate(rows, start=3):
        for j, value in enumerate(row, start=1):
            ws.cell(row=i, column=j, value=value)
    wb.save(tmp_path / FILE)
    monkeypatch.setenv("WORKPAPERS_DIR", str(tmp_path))
    return tmp_path


def test_find_target_file_attachment_then_mention(table_dir):
    assert _find_target_file([f"[첨부 파일: {FILE}]\n집계해줘"]).name == FILE
    assert _find_target_file([f"{FILE} 부서별 합계"]).name == FILE
    assert _find_target_file(["표본_지출 부서별 합계"]).name == FILE  # stem 언급
    assert _find_target_file(["아무 파일도 언급 안 함"]) is None


def test_pick_table_block_prefers_largest(table_dir):
    target = table_dir / FILE
    sheet, ref = _pick_table_block(target, ["부서별 합계 알려줘"])
    assert sheet == SHEET
    assert ref == "A3:C6"  # 제목(A1, 1행짜리)이 아니라 표 본체


def test_explicit_range_with_sheet_overrides_block_pick(table_dir):
    nodes = AnalystNodes(model=None)
    update = nodes.inspect_data(
        {
            "messages": [
                HumanMessage(content=f"[첨부 파일: {FILE}] {SHEET}!A3:C5 범위만 집계해줘")
            ]
        }
    )
    assert update["error"] is None
    assert update["dataset"]["cell_range"] == "A3:C5"  # 자동 선택(A3:C6)이 아니라 명시 범위
    assert update["profile"]["row_count"] == 2


def test_explicit_range_without_sheet_on_single_sheet(table_dir):
    nodes = AnalystNodes(model=None)
    update = nodes.inspect_data(
        {"messages": [HumanMessage(content=f"[첨부 파일: {FILE}] A3:C6 집계해줘")]}
    )
    assert update["error"] is None
    assert update["dataset"] == {"path": FILE, "sheet": SHEET, "cell_range": "A3:C6"}


def test_no_block_error_lists_sheets(table_dir):
    from openpyxl import Workbook as WB

    wb = WB()
    wb.active.title = "표지"
    wb.active["A1"] = "제목뿐"
    wb.save(table_dir / "빈조서.xlsx")
    nodes = AnalystNodes(model=None)
    update = nodes.inspect_data(
        {"messages": [HumanMessage(content="[첨부 파일: 빈조서.xlsx] 집계해줘")]}
    )
    assert update["error"] is not None
    assert "표지" in update["error"]  # 시트 목록 안내
    assert "시트명!A1:C50" in update["error"]  # 범위 지정 안내


def test_inspect_data_without_file_lists_candidates(table_dir):
    nodes = AnalystNodes(model=None)  # inspect는 LLM 미사용
    update = nodes.inspect_data(
        {"messages": [HumanMessage(content="부서별 합계 알려줘")]}
    )
    assert update["error"] and FILE in update["error"]
    assert nodes.route_inspect(update) == "fail"


def test_inspect_data_registers_table(table_dir):
    nodes = AnalystNodes(model=None)
    update = nodes.inspect_data(
        {"messages": [HumanMessage(content=f"[첨부 파일: {FILE}]\n부서별 금액 합계")]}
    )
    assert update["error"] is None
    assert update["dataset"] == {
        "path": FILE,
        "sheet": SHEET,
        "cell_range": "A3:C6",
    }
    assert '"금액"' in update["schema"]
    assert update["profile"]["row_count"] == 3
    assert nodes.route_inspect(update) == "plan"


def test_validate_and_execute_without_llm(table_dir):
    nodes = AnalystNodes(model=None)
    state = nodes.inspect_data(
        {"messages": [HumanMessage(content=f"[첨부 파일: {FILE}] 합계")]}
    )
    state["sql"] = 'SELECT "부서", SUM("금액") AS 합계 FROM data GROUP BY 1 ORDER BY 2 DESC'
    state.update(nodes.validate_sql(state))
    assert state["error"] is None
    state.update(nodes.execute_sql(state))
    assert state["error"] is None
    assert state["result_rows"][0] == ["감사1본부", 800] or state["result_rows"][0] == [
        "감사1본부",
        800.0,
    ]
    assert nodes.route_execution(state) == "answer"

    state.update(nodes.validate_sql({"sql": "DROP TABLE data", "attempts": 2}))
    assert state["error"] and nodes.route_sql(state | {"attempts": 2}) == "fail"


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="실 API 키 필요"
)
async def test_full_pipeline_with_real_model(table_dir):
    graph = await analyst(
        {"configurable": {"model": "anthropic:claude-haiku-4-5-20251001"}}
    )
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=f"[첨부 파일: {FILE}]\n부서별 금액 합계를 큰 순서로 알려줘"
                )
            ]
        }
    )
    answer = result["messages"][-1]
    text = answer.content if isinstance(answer.content, str) else str(answer.content)
    assert "감사1본부" in text and "800" in text
    assert result["error"] is None
