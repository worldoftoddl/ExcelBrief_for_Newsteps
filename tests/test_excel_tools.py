"""Phase 3 — Excel 탐색 도구 테스트 (TDD: 구현보다 먼저 작성)."""

import os

import pytest

from agent.tools.excel import (
    excel_find,
    excel_read_range,
    excel_sheet_stats,
    excel_workbook_overview,
    list_workpapers,
)

WP = "조서_테스트.xlsx"


# ── list_workpapers ──────────────────────────────────────────
def test_list_workpapers_lists_xlsx():
    out = list_workpapers.invoke({})
    assert "조서_테스트.xlsx" in out
    assert "범용_판매데이터.xlsx" in out


# ── excel_workbook_overview ──────────────────────────────────
def test_overview_shows_sheets_headers_and_merges():
    out = excel_workbook_overview.invoke({"path": WP})
    for sheet in ("Lead", "명세", "빅시트"):
        assert sheet in out
    assert "매출채권 Lead Schedule" in out  # 첫 행 미리보기
    assert "병합" in out                     # 병합 셀 정보


def test_overview_missing_file_suggests_candidates():
    out = excel_workbook_overview.invoke({"path": "없는파일.xlsx"})
    assert "오류" in out
    assert "조서_테스트.xlsx" in out  # 후보 목록 제시


def test_overview_blocks_path_escape():
    out = excel_workbook_overview.invoke({"path": "../탈출.xlsx"})
    assert "오류" in out


# ── excel_read_range ─────────────────────────────────────────
def test_read_range_values_as_markdown():
    out = excel_read_range.invoke({"path": WP, "sheet": "Lead", "cell_range": "A3:C4"})
    assert "계정과목" in out and "매출채권" in out and "1500" in out
    assert "|" in out  # 마크다운 표


def test_read_range_formulas_mode():
    out = excel_read_range.invoke(
        {"path": WP, "sheet": "Lead", "cell_range": "B6:C6", "mode": "formulas"}
    )
    assert "=SUM(B4:B5)" in out


def test_read_range_cell_cap_returns_guidance():
    out = excel_read_range.invoke({"path": WP, "sheet": "빅시트", "cell_range": "A1:T30"})
    assert "500" in out and "나눠" in out  # 예외가 아니라 분할 안내


def test_read_range_bad_sheet_is_error_text():
    out = excel_read_range.invoke({"path": WP, "sheet": "없는시트", "cell_range": "A1:B2"})
    assert "오류" in out


# ── excel_find ───────────────────────────────────────────────
def test_find_locates_cell_across_sheets():
    out = excel_find.invoke({"path": WP, "query": "한빛"})
    assert "명세!A2" in out


def test_find_scoped_to_sheet():
    out = excel_find.invoke({"path": WP, "query": "매출채권", "sheet": "Lead"})
    assert "Lead!A4" in out and "명세" not in out


# ── excel_sheet_stats ────────────────────────────────────────
def test_sheet_stats_counts_formulas():
    out = excel_sheet_stats.invoke({"path": WP, "sheet": "Lead"})
    assert "수식" in out and "2" in out  # =SUM 2개


# ── 에이전트 통합 (개요→정독 탐색 순서) ──────────────────────
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="API 키 없음")
async def test_agent_explores_overview_first():
    from agent.graph import graph

    g = await graph({"configurable": {}})
    result = await g.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "조서_테스트.xlsx가 어떤 조서인지 간단히 설명해줘.",
                }
            ]
        },
        config={"recursion_limit": 20},
    )
    tool_calls = [
        tc["name"]
        for m in result["messages"]
        for tc in (getattr(m, "tool_calls", None) or [])
    ]
    assert "excel_workbook_overview" in tool_calls
    assert result["messages"][-1].content
