# LangGraph Web Scraping Agent

A self-contained replacement for the ScrapeGraphAI example. It exposes each step as a LangGraph
node so an external UI can stream progress and inspect failures.

## Workflow

```text
validate_request -> fetch_page -> clean_content -> chunk_content
                 -> extract_chunks -> merge_results -> validate_result
                                                    |-> retry extraction
                                                    |-> complete / fail
```

The MVP handles one public HTTP(S) page. HTTP fetching is the default. Playwright is an optional,
disabled fallback for JavaScript-rendered pages.

## Setup

```bash
cd For_me/langgraph_web_scraping_agent
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

For browser fallback:

```bash
pip install -e '.[browser,dev]'
playwright install chromium
```

Set `OPENAI_API_KEY`. LangSmith tracing is enabled with the variables in `.env.example`.

## Invoke

```python
from web_scraping_agent import build_graph

graph = build_graph()
result = graph.invoke({
    "url": "https://example.com/products",
    "instruction": "Extract product names and prices",
    "output_schema": {
        "title": "Products",
        "type": "object",
        "properties": {
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "price": {"type": "number"},
                    },
                    "required": ["name", "price"],
                },
            }
        },
        "required": ["products"],
    },
})
print(result["result"])
```

## Stream to a UI

Use `custom` events for stable UI progress and `updates` for graph diagnostics:

```python
async for mode, event in graph.astream(
    request,
    stream_mode=["custom", "updates"],
):
    if mode == "custom":
        await ui.send_progress(event)
```

Stages include `validating_request`, `fetching`, `cleaning`, `chunking`, `extracting`, `merging`,
`validating_result`, `complete`, and `failed`.

## Security and limits

The fetchers allow only HTTP(S) on ports 80/443, reject credentials, resolve every top-level URL
and redirect, block non-public IP ranges, cap redirects and response bytes, and enforce timeouts.
Browser requests are also filtered. Production deployments should additionally apply an outbound
network policy or proxy because application-level DNS checks alone cannot fully prevent DNS
rebinding. Respect site terms, robots policies, authentication boundaries, and applicable law.

Run tests with `pytest`. Unit tests do not call the network or an LLM.
