"""Bounded HTTP page fetcher with redirect revalidation."""

from dataclasses import dataclass

import httpx

from .config import ScraperConfig
from .security import Resolver, _resolve, validate_public_url


@dataclass(frozen=True, slots=True)
class FetchResult:
    html: str
    final_url: str
    content_type: str


class HttpFetcher:
    def __init__(self, config: ScraperConfig, resolver: Resolver = _resolve) -> None:
        self.config = config
        self.resolver = resolver

    def fetch(self, url: str) -> FetchResult:
        current_url = validate_public_url(url, self.resolver)
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }

        with httpx.Client(timeout=self.config.timeout_seconds, follow_redirects=False) as client:
            for redirect_count in range(self.config.max_redirects + 1):
                with client.stream("GET", current_url, headers=headers) as response:
                    if response.is_redirect:
                        if redirect_count >= self.config.max_redirects:
                            raise ValueError("Too many redirects")
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("Redirect response has no location")
                        current_url = validate_public_url(
                            str(response.url.join(location)), self.resolver
                        )
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if (
                        "text/html" not in content_type
                        and "application/xhtml+xml" not in content_type
                    ):
                        raise ValueError(f"Unsupported content type: {content_type or 'unknown'}")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > self.config.max_response_bytes:
                            raise ValueError("Response exceeds configured size limit")
                    encoding = response.encoding or "utf-8"
                    return FetchResult(
                        body.decode(encoding, errors="replace"), str(response.url), content_type
                    )

        raise RuntimeError("Fetch loop ended unexpectedly")
