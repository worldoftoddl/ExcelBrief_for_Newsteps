"""Deterministic document cleanup and chunking."""

import re


def html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "template"]):
        element.decompose()
    for selector in ("nav", "footer", "aside"):
        for element in soup.select(selector):
            element.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    text = root.get_text("\n", strip=True)
    lines = (re.sub(r"\s+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def split_text(text: str, chunk_chars: int, overlap: int) -> list[str]:
    if chunk_chars <= 0 or overlap < 0 or overlap >= chunk_chars:
        raise ValueError("chunk_chars must be positive and overlap must be smaller")
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + chunk_chars // 2, end)
            if boundary > start:
                end = boundary
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = end - overlap
    return [chunk for chunk in chunks if chunk]
