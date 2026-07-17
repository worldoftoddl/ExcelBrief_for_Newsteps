"""reviewer 그래프 테스트 — 서명란 스캔·증거 수집·보고서 렌더는 단위로,
전체 파이프라인은 실제 API(skipif)로 검증한다."""

import os

import pytest
from langchain_core.messages import HumanMessage
from openpyxl import Workbook

from agent.reviewer import (
    Finding,
    ReviewFindings,
    ReviewerNodes,
    _collect_evidence,
    _render_report,
    _scan_signoffs,
    reviewer,
)

FILE = "표본_검토조서.xlsx"
SHEET = "5100"


@pytest.fixture()
def review_dir(tmp_path, monkeypatch):
    """서명란(작성자 채움·검토자 공란)과 소형 표·수식을 심은 조서."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    ws["A1"] = "현금 실사 조서"
    ws["A2"] = "작성자"
    ws["B2"] = "김신입"
    ws["A3"] = "검토자"  # B3 공란 — 검토 미완
    rows = [
        ["항목", "장부", "실사"],
        ["소액현금", 100, 100],
        ["보통예금", 900, 900],
    ]
    for i, row in enumerate(rows, start=6):
        for j, value in enumerate(row, start=1):
            ws.cell(row=i, column=j, value=value)
    ws["B9"] = "=SUM(B7:B8)"
    ws["C9"] = 1000  # 수식 지대 내 하드코딩
    wb.save(tmp_path / FILE)
    monkeypatch.setenv("WORKPAPERS_DIR", str(tmp_path))
    return tmp_path


def test_scan_signoffs_detects_filled_and_blank(review_dir):
    out = _scan_signoffs(review_dir / FILE)
    assert f'{SHEET}!A2 "작성자" → 채움(김신입)' in out
    assert f'{SHEET}!A3 "검토자" → 공란' in out


def test_scan_signoffs_ignores_long_sentences(review_dir):
    from openpyxl import load_workbook

    wb = load_workbook(review_dir / FILE)
    wb[SHEET]["A20"] = "검토자는 다음 사항을 확인한 후 서명해야 한다는 안내 문구"
    wb.save(review_dir / FILE)
    out = _scan_signoffs(review_dir / FILE)
    assert "A20" not in out


def test_collect_evidence_sections(review_dir):
    out, examined, skipped = _collect_evidence(FILE)
    assert "워크북:" in out  # overview
    assert "수식 지도:" in out and "하드코딩" in out  # formula_map
    assert "주석·의도 정보:" in out  # annotations
    assert "[서명란 스캔]" in out
    assert "소액현금" in out  # 본문 정독 포함
    # 서명란 스캔은 절단(MAX_EVIDENCE_CHARS)에서 살아남도록 증거 선두에 있다
    assert out.index("[서명란 스캔]") < out.index("수식 지도:")
    assert examined == [SHEET] and skipped == []


def test_collect_evidence_sheet_cap_and_report_scope(review_dir):
    from openpyxl import load_workbook

    wb = load_workbook(review_dir / FILE)
    for i in range(1, 8):  # 기존 1개 + 7개 = 8개 시트 (상한 6개 초과)
        ws = wb.create_sheet(f"추가{i}")
        ws["A1"] = "항목"
        ws["A2"] = "값"
    wb.save(review_dir / FILE)

    out, examined, skipped = _collect_evidence(FILE)
    assert len(examined) == 6 and examined[0] == SHEET
    assert skipped == ["추가6", "추가7"]
    assert "추가6, 추가7" in out  # 생략 시트가 증거에도 명시

    findings = ReviewFindings(
        workpaper_purpose="p", performed_procedures=[], missing_procedures=[],
        signoff_assessment="s", tieout_findings=[], open_items=[], overall="o",
    )
    report = _render_report(FILE, findings, examined, skipped)
    assert "## 점검 범위" in report
    assert "점검한 시트(6개)" in report
    assert "생략된 시트(2개" in report and "추가7" in report


def test_triage_fallback_heuristic(review_dir):
    """model=None이면 LLM 분류가 예외 → 파일 언급 유무 휴리스틱으로 폴백."""
    nodes = ReviewerNodes(model=None)
    update = nodes.triage(
        {"messages": [HumanMessage(content=f"[첨부 파일: {FILE}] 검토해줘")]}
    )
    assert update["mode"] == "review" and update["error"] is None
    assert nodes.route_triage(update) == "review"

    update = nodes.triage({"messages": [HumanMessage(content="안녕, 사용법 알려줘")]})
    assert update["mode"] == "chat"
    assert nodes.route_triage(update) == "chat"

    update = nodes.triage({"messages": []})  # 빈 입력도 chat으로
    assert update["mode"] == "chat"


def test_locate_without_file_lists_candidates(review_dir):
    nodes = ReviewerNodes(model=None)
    update = nodes.locate({"messages": [HumanMessage(content="조서 검토해줘")]})
    assert update["error"] and FILE in update["error"]
    assert nodes.route_locate(update) == "fail"


def test_render_report_sections_and_severity_order():
    findings = ReviewFindings(
        workpaper_purpose="현금 실사 조서",
        performed_procedures=["실사 대사"],
        missing_procedures=[
            Finding(title="낮음건", severity="낮음", location="5100!A1", detail="d"),
            Finding(title="높음건", severity="높음", location="5100!C9", detail="d"),
        ],
        signoff_assessment="작성 완료, 검토 서명 공란",
        tieout_findings=[],
        open_items=[],
        overall="검토 서명 전 단계",
    )
    out = _render_report(FILE, findings)
    for section in ("① 조서 개요", "② 수행된 절차", "③ 서명·검토 상태",
                    "④ 검산·tie-out 점검", "⑤ 누락·추가 필요 절차",
                    "⑥ 미결 항목", "⑦ 총평"):
        assert section in out
    assert out.index("높음건") < out.index("낮음건")  # 심각도 정렬
    assert "- (해당 없음)" in out  # 빈 섹션 표기
    assert "agent 그래프" in out  # 한계 고지


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="실 API 키 필요"
)
async def test_chat_branch_with_real_model(review_dir):
    graph = await reviewer(
        {"configurable": {"model": "anthropic:claude-haiku-4-5-20251001"}}
    )
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="안녕! 너는 어떤 검토를 해줘?")]}
    )
    answer = result["messages"][-1]
    text = answer.content if isinstance(answer.content, str) else str(answer.content)
    assert text.strip() and "오류:" not in text
    assert "# 조서 검토 보고" not in text  # 검토 파이프라인을 타지 않았다


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="실 API 키 필요"
)
async def test_full_pipeline_with_real_model(review_dir):
    graph = await reviewer(
        {"configurable": {"model": "anthropic:claude-haiku-4-5-20251001"}}
    )
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=f"[첨부 파일: {FILE}]\n이 조서 완성도 점검해줘")]}
    )
    text = result["messages"][-1].content
    assert "# 조서 검토 보고" in text and "⑦ 총평" in text
    assert result["error"] is None
