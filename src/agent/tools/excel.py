"""Excel 탐색 도구 — 에이전트가 워크북을 통째가 아니라 필요한 부분만 읽게 한다.

모든 도구는 WORKPAPERS_DIR 하위 파일만 접근하며(경로 탈출 차단),
실패는 예외 대신 "오류: …" 텍스트로 반환해 에이전트가 자가 수정하게 한다.
"""

import os
from pathlib import Path

from langchain_core.tools import tool
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries

MAX_CELLS = 500
MAX_FIND_HITS = 50
_PREVIEW_COLS = 8


def _base_dir() -> Path:
    return Path(os.environ.get("WORKPAPERS_DIR", "data/workpapers")).resolve()


def _resolve(path: str) -> Path:
    """WORKPAPERS_DIR 하위로 경로를 한정한다. 실패 시 ValueError(사용자용 메시지)."""
    base = _base_dir()
    target = (base / path).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"오류: 조서 폴더({base.name}/) 밖의 경로는 접근할 수 없습니다.")
    if not target.is_file():
        candidates = sorted(p.name for p in base.glob("*.xls[xm]"))
        listing = "\n".join(f"- {c}" for c in candidates) or "(폴더가 비어 있음)"
        raise ValueError(
            f"오류: '{path}' 파일이 없습니다. 현재 폴더의 파일 목록:\n{listing}"
        )
    return target


def _sheet(wb, name: str):
    if name not in wb.sheetnames:
        raise ValueError(
            f"오류: 시트 '{name}'이(가) 없습니다. 시트 목록: {', '.join(wb.sheetnames)}"
        )
    return wb[name]


def _fmt(value) -> str:
    return "" if value is None else str(value)


@tool
def list_workpapers() -> str:
    """조서 폴더에 있는 Excel 파일 목록을 반환한다.

    파일명이 기억나지 않거나 사용자가 파일을 모호하게 지칭할 때 먼저 호출한다.
    """
    base = _base_dir()
    files = sorted(base.glob("*.xls[xm]"))
    if not files:
        return f"조서 폴더({base})에 Excel 파일이 없습니다."
    return "\n".join(f"- {p.name} ({p.stat().st_size // 1024:,} KB)" for p in files)


@tool
def excel_workbook_overview(path: str) -> str:
    """워크북 전체 지도를 반환한다: 시트별 크기·첫 행 미리보기·병합 셀 수.

    어떤 Excel 파일이든 정독 전에 반드시 이 도구로 구조를 먼저 파악한다.

    Args:
        path: 조서 폴더 기준 파일명 (예: "D-10_매출채권.xlsx")
    """
    try:
        target = _resolve(path)
    except ValueError as e:
        return str(e)

    wb = load_workbook(target, read_only=False, data_only=True)
    lines = [f"워크북: {target.name} — 시트 {len(wb.sheetnames)}개"]
    for ws in wb.worksheets:
        first_row = [
            _fmt(c.value) for c in next(ws.iter_rows(min_row=1, max_row=1), [])
        ][:_PREVIEW_COLS]
        preview = " | ".join(v for v in first_row if v) or "(빈 행)"
        lines.append(
            f"\n[{ws.title}] {ws.max_row}행 × {ws.max_column}열, "
            f"병합 {len(ws.merged_cells.ranges)}건"
        )
        lines.append(f"  첫 행: {preview}")
    return "\n".join(lines)


@tool
def excel_read_range(path: str, sheet: str, cell_range: str, mode: str = "values") -> str:
    """지정 범위의 셀을 마크다운 표로 반환한다 (1회 최대 500셀).

    mode="values"는 저장된 값(수식은 파일에 저장된 캐시 값 — 재계산 아님),
    mode="formulas"는 수식 문자열을 보여준다. 계산 로직 확인 시 formulas 사용.

    Args:
        path: 조서 폴더 기준 파일명
        sheet: 시트 이름
        cell_range: 셀 범위 (예: "A1:C10")
        mode: "values"(기본) 또는 "formulas"
    """
    try:
        target = _resolve(path)
        min_col, min_row, max_col, max_row = range_boundaries(cell_range)
        count = (max_row - min_row + 1) * (max_col - min_col + 1)
        if count > MAX_CELLS:
            return (
                f"요청 범위가 {count:,}셀로 1회 상한({MAX_CELLS}셀)을 초과합니다. "
                f"범위를 더 작게 나눠 순차적으로 요청하세요."
            )
        wb = load_workbook(target, read_only=False, data_only=(mode != "formulas"))
        ws = _sheet(wb, sheet)
    except ValueError as e:
        return str(e)

    header = [""] + [get_column_letter(c) for c in range(min_col, max_col + 1)]
    rows = ["| " + " | ".join(header) + " |",
            "|" + "---|" * len(header)]
    for r in range(min_row, max_row + 1):
        cells = [_fmt(ws.cell(row=r, column=c).value) for c in range(min_col, max_col + 1)]
        rows.append("| " + " | ".join([str(r)] + cells) + " |")
    note = " (수식 문자열)" if mode == "formulas" else " (저장된 값 — 수식 재계산 아님)"
    return f"{sheet}!{cell_range}{note}\n" + "\n".join(rows)


@tool
def excel_find(path: str, query: str, sheet: str = "") -> str:
    """문자열이 포함된 셀을 찾아 좌표와 값을 반환한다 (최대 50건).

    계정명·거래처·틱마크 등 특정 항목이 워크북 어디에 있는지 찾을 때 사용.

    Args:
        path: 조서 폴더 기준 파일명
        query: 찾을 문자열 (대소문자 무시, 부분 일치)
        sheet: 특정 시트로 한정할 때만 지정 (기본: 전체 시트)
    """
    try:
        target = _resolve(path)
        wb = load_workbook(target, read_only=False, data_only=True)
        sheets = [_sheet(wb, sheet)] if sheet else wb.worksheets
    except ValueError as e:
        return str(e)

    needle = query.casefold()
    hits = []
    for ws in sheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None and needle in str(cell.value).casefold():
                    hits.append(f"{ws.title}!{cell.coordinate}: {cell.value}")
                    if len(hits) >= MAX_FIND_HITS:
                        return "\n".join(hits) + f"\n… 상한({MAX_FIND_HITS}건) 도달 — 검색어를 좁히세요."
    return "\n".join(hits) if hits else f"'{query}'와 일치하는 셀이 없습니다."


@tool
def excel_sheet_stats(path: str, sheet: str) -> str:
    """시트의 데이터 분포를 요약한다: 비어있지 않은 셀·수식 셀·숫자/문자 비율.

    큰 시트를 정독하기 전에 어느 영역부터 읽을지 우선순위를 정할 때 사용.

    Args:
        path: 조서 폴더 기준 파일명
        sheet: 시트 이름
    """
    try:
        target = _resolve(path)
        ws_f = _sheet(load_workbook(target, read_only=False, data_only=False), sheet)
    except ValueError as e:
        return str(e)

    total = ws_f.max_row * ws_f.max_column
    non_empty = formulas = numbers = texts = 0
    for row in ws_f.iter_rows():
        for cell in row:
            v = cell.value
            if v is None:
                continue
            non_empty += 1
            if isinstance(v, str) and v.startswith("="):
                formulas += 1
            elif isinstance(v, (int, float)):
                numbers += 1
            else:
                texts += 1
    density = non_empty / total * 100 if total else 0
    return (
        f"[{sheet}] {ws_f.max_row}행 × {ws_f.max_column}열 (총 {total:,}셀)\n"
        f"- 비어있지 않은 셀: {non_empty:,} (밀도 {density:.0f}%)\n"
        f"- 수식 셀: {formulas:,}\n"
        f"- 숫자 셀: {numbers:,} / 문자 셀: {texts:,}\n"
        f"- 병합: {len(ws_f.merged_cells.ranges)}건"
    )


EXCEL_TOOLS = [
    list_workpapers,
    excel_workbook_overview,
    excel_read_range,
    excel_find,
    excel_sheet_stats,
]
