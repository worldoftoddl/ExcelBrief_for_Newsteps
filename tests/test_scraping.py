"""scraping 계층(security·processing·fetcher) 테스트 — upstream 단위 테스트 이식.

네트워크·LLM 호출 없음: DNS 리졸버와 HTTP 응답은 전부 페이크로 주입한다.
"""

import httpx
import pytest

from agent.scraping import (
    HttpFetcher,
    ScraperConfig,
    UnsafeUrlError,
    html_to_text,
    split_text,
    validate_public_url,
)


def resolve_to(*addresses: str):
    return lambda _hostname: addresses


# --- security ---


def test_accepts_http_url_resolving_only_to_public_addresses():
    url = validate_public_url(
        "https://example.com/products?q=agent",
        resolver=resolve_to("93.184.216.34"),
    )

    assert url == "https://example.com/products?q=agent"


@pytest.mark.parametrize(
    ("url", "addresses"),
    [
        ("file:///etc/passwd", ()),
        ("http://localhost/admin", ("127.0.0.1",)),
        ("http://metadata.internal/", ("169.254.169.254",)),
        ("http://service.internal/", ("10.0.0.10",)),
        ("http://[::1]/", ("::1",)),
    ],
)
def test_rejects_non_http_or_non_public_targets(url, addresses):
    with pytest.raises(UnsafeUrlError):
        validate_public_url(url, resolver=resolve_to(*addresses))


def test_rejects_credentials_and_unapproved_ports():
    with pytest.raises(UnsafeUrlError):
        validate_public_url(
            "https://user:password@example.com/",
            resolver=resolve_to("93.184.216.34"),
        )

    with pytest.raises(UnsafeUrlError):
        validate_public_url("https://example.com:8080/", resolver=resolve_to("93.184.216.34"))


# --- processing ---


def test_html_to_text_keeps_main_content_and_removes_noise():
    html = """
    <html><body>
      <nav>Navigation</nav>
      <main><h1>Agent Catalog</h1><p>Useful product details.</p></main>
      <script>alert('ignore')</script><footer>Copyright</footer>
    </body></html>
    """

    text = html_to_text(html)

    assert text == "Agent Catalog\nUseful product details."
    assert "Navigation" not in text
    assert "ignore" not in text


def test_split_text_preserves_overlap_and_all_content():
    chunks = split_text("abcdefghij", chunk_chars=6, overlap=2)

    assert chunks == ["abcdef", "efghij"]


@pytest.mark.parametrize("chunk_chars,overlap", [(0, 0), (10, -1), (10, 10)])
def test_split_text_rejects_invalid_limits(chunk_chars, overlap):
    with pytest.raises(ValueError):
        split_text("content", chunk_chars, overlap)


# --- http_fetcher ---


def _fetcher_with(handler, **config_kwargs):
    config = ScraperConfig(**config_kwargs)
    fetcher = HttpFetcher(config, resolver=resolve_to("93.184.216.34"))
    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    class PatchedClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    return fetcher, PatchedClient


def test_fetch_returns_html_and_follows_safe_redirect(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(302, headers={"location": "https://example.com/new"})
        return httpx.Response(
            200, headers={"content-type": "text/html; charset=utf-8"}, text="<main>ok</main>"
        )

    fetcher, patched = _fetcher_with(handler)
    monkeypatch.setattr(httpx, "Client", patched)

    result = fetcher.fetch("https://example.com/old")

    assert result.html == "<main>ok</main>"
    assert result.final_url == "https://example.com/new"


def test_fetch_rejects_oversized_response(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text="x" * 200
        )

    fetcher, patched = _fetcher_with(handler, max_response_bytes=100)
    monkeypatch.setattr(httpx, "Client", patched)

    with pytest.raises(ValueError, match="size limit"):
        fetcher.fetch("https://example.com/big")


def test_fetch_rejects_non_html_content_type(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, text="%PDF")

    fetcher, patched = _fetcher_with(handler)
    monkeypatch.setattr(httpx, "Client", patched)

    with pytest.raises(ValueError, match="content type"):
        fetcher.fetch("https://example.com/file.pdf")
