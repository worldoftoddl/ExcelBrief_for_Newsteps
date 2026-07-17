"""채팅 입력형 그래프(analyst·reviewer) 공통 헬퍼.

messages에서 질문·대상 파일을 찾는 로직과 custom stream 방출을 모은다.
"""

import re
from typing import Any

from langgraph.config import get_stream_writer

from agent.tools.excel import _base_dir, _supported_files

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".csv"}  # 표 형태 파일 (CSV는 값 전용 단일 시트)
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


MAX_CONTEXT_MESSAGES = 6  # 프롬프트에 주입하는 직전 대화 메시지 수
MAX_CONTEXT_CHARS = 600  # 메시지당 클립 길이


def conversation_context(state: dict) -> str:
    """직전 대화(현재 질문 제외 최근 N개)를 프롬프트 주입용으로 요약한다.

    고정 워크플로 그래프는 최신 질문만 쓰기 쉬운데, 스레드에서는
    "그중 상위 3개만" 같은 후속 질의가 흔하다 — 맥락 없이는 오해한다.
    """
    msgs = state.get("messages") or []
    if len(msgs) <= 1:
        return ""
    lines = []
    for m in msgs[-(MAX_CONTEXT_MESSAGES + 1) : -1]:
        role = {"human": "사용자", "ai": "어시스턴트"}.get(getattr(m, "type", None))
        if role is None:
            continue
        text = msg_text(m).strip()
        if not text:
            continue
        if len(text) > MAX_CONTEXT_CHARS:
            text = text[:MAX_CONTEXT_CHARS] + "…"
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def excel_files() -> list:
    return [
        f for f in _supported_files(_base_dir()) if f.suffix.lower() in EXCEL_SUFFIXES
    ]


MIN_FUZZY_TOKENS = 2  # 퍼지 매칭이 요구하는 최소 토큰 겹침


def _tokens(text: str) -> set[str]:
    # [\W_]: 밑줄도 구분자 — "데모조서_5400"이 한 토큰으로 남지 않게
    return {t for t in re.split(r"[\W_]+", text.lower()) if len(t) >= 2}


def find_target_file(texts: list[str]):
    """메시지에서 대상 Excel 파일을 찾는다.

    3단계: ① 첨부 표기 ② 파일명·stem 정확 부분 문자열 ③ 토큰 겹침 퍼지
    매칭. ③은 "데모조서 5400 매출채권"처럼 밑줄·괄호를 생략한 언급을
    잡는다 — 파일명 토큰이 2개 이상 겹치는 파일 중 최다 겹침을 고른다.
    """
    files = excel_files()
    for text in texts:
        for name in reversed(ATTACHMENT_RE.findall(text)):
            for f in files:
                if f.name == name.strip():
                    return f
        for f in files:
            if f.name in text or f.stem in text:
                return f
        text_tokens = _tokens(text)
        best = None
        for f in files:
            overlap = len(_tokens(f.stem) & text_tokens)
            if overlap >= MIN_FUZZY_TOKENS and (best is None or overlap > best[0]):
                best = (overlap, f)
        if best:
            return best[1]
    return None


def missing_file_message(intro: str) -> str:
    listing = "\n".join(f"- {f.name}" for f in excel_files()) or "(조서 폴더가 비어 있음)"
    return f"{intro} 파일을 첨부하거나 아래 파일명 중 하나를 질문에 포함해 주세요:\n{listing}"
