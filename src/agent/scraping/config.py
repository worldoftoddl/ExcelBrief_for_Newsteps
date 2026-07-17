"""Runtime configuration, kept outside graph state.

이식 시 변경: 모델 지정(model 필드·SCRAPER_MODEL env)은 제거 — 모델은 호출자가
resolve_model로 라우팅한 인스턴스를 서브그래프에 주입한다.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScraperConfig:
    timeout_seconds: float = 20.0
    max_response_bytes: int = 2_000_000
    max_redirects: int = 5
    chunk_chars: int = 12_000
    chunk_overlap: int = 500
    max_extraction_attempts: int = 2
    user_agent: str = "AgentForNewstep/0.1"
