"""Word 문서 도구 — .docx의 문단·표를 마크다운으로 변환해 반환한다.

excel.py와 같은 방침: WORKPAPERS_DIR 하위 파일만 접근하고,
실패는 예외 대신 "오류: …" 텍스트로 반환해 에이전트가 자가 수정하게 한다.
"""

import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_core.tools import tool

from agent.tools.excel import _md, _resolve

MAX_DOC_CHARS = 20_000

_HEADING_RE = re.compile(r"(?:Heading|제목)\s*(\d)")


@tool
def read_document(path: str) -> str:
    """Word(.docx) 문서의 본문 문단과 표를 순서대로 마크다운으로 반환한다.

    감사 관련 문서(내부통제 기술서, 회의록, 정책 문서 등)나 사용자가 업로드한
    Word 파일을 읽을 때 사용한다. .doc(97-2003 구형)은 지원하지 않으므로
    사용자에게 .docx 변환을 안내할 것. Excel 파일은 excel_* 도구를 사용한다.

    Args:
        path: 조서 폴더 기준 파일명 (예: "내부통제 기술서.docx")
    """
    try:
        target = _resolve(path)
    except ValueError as e:
        return str(e)
    if target.suffix.lower() != ".docx":
        return (
            f"오류: read_document는 .docx 전용입니다 ('{target.name}'). "
            f"Excel 파일은 excel_workbook_overview부터 사용하세요."
        )
    try:
        doc = Document(str(target))
    except Exception as e:  # python-docx는 손상 파일에서 다양한 예외를 던진다
        return f"오류: '{target.name}' 문서를 열 수 없습니다 ({e})."

    lines = [f"문서: {target.name}"]
    n_tables = 0
    for item in doc.iter_inner_content():
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            style = item.style.name if item.style is not None else ""
            m = _HEADING_RE.match(style or "")
            lines.append(f"{'#' * int(m.group(1))} {text}" if m else text)
        elif isinstance(item, Table):
            n_tables += 1
            rows = [
                [_md(" ".join(c.text.split())) for c in row.cells] for row in item.rows
            ]
            if not rows:
                continue
            width = max(len(r) for r in rows)
            pad = [r + [""] * (width - len(r)) for r in rows]
            lines.append(f"[표 {n_tables}] {len(rows)}행 × {width}열")
            lines.append("| " + " | ".join(pad[0]) + " |")
            lines.append("|" + "---|" * width)
            lines += ["| " + " | ".join(r) + " |" for r in pad[1:]]

    out = "\n".join(lines)
    if len(out) > MAX_DOC_CHARS:
        out = (
            out[:MAX_DOC_CHARS]
            + f"\n… (총 {len(out):,}자 중 {MAX_DOC_CHARS:,}자까지 표시 — "
            f"필요하면 구체 항목을 지정해 다시 질문하도록 안내)"
        )
    return out


DOCUMENT_TOOLS = [read_document]
