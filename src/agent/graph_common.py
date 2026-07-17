"""채팅 입력형 그래프(analyst·reviewer) 공통 헬퍼.

messages에서 질문·대상 파일을 찾는 로직과 custom stream 방출을 모은다.
"""

import re
from typing import Any

from langgraph.config import get_stream_writer

from agent.tools.excel import _base_dir, _supported_files

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
ATTACHMENT_RE = re.compile(r"\[첨부 파일: ([^\]]+)\]")


def emit(stage: str, message: str, **details: Any) -> None:
    try:
        get_stream_writer()({"stage": stage, "message": message, **details})
    except RuntimeError:
        pass


def msg_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def human_texts_newest_first(state: dict) -> list[str]:
    return [
        msg_text(m)
        for m in reversed(state.get("messages", []))
        if getattr(m, "type", "") == "human"
    ]


def excel_files() -> list:
    return [
        f for f in _supported_files(_base_dir()) if f.suffix.lower() in EXCEL_SUFFIXES
    ]


def find_target_file(texts: list[str]):
    """메시지에서 대상 Excel 파일을 찾는다 — 첨부 표기 우선, 파일명 언급 차선."""
    files = excel_files()
    for text in texts:
        for name in reversed(ATTACHMENT_RE.findall(text)):
            for f in files:
                if f.name == name.strip():
                    return f
        for f in files:
            if f.name in text or f.stem in text:
                return f
    return None


def missing_file_message(intro: str) -> str:
    listing = "\n".join(f"- {f.name}" for f in excel_files()) or "(조서 폴더가 비어 있음)"
    return f"{intro} 파일을 첨부하거나 아래 파일명 중 하나를 질문에 포함해 주세요:\n{listing}"
