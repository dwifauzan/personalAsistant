# AI Browser Tool-Calling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace regex-based search routing with LLM-native tool calling and async parallel page fetching.

**Architecture:** The LLM (llama3.1 via Ollama) receives tool definitions and decides when/how to search. Tool calls are dispatched in parallel via asyncio. No regex for intent detection — the LLM handles routing natively.

**Tech Stack:** Python 3.10+, ollama, asyncio, aiohttp, BeautifulSoup4

**Spec:** `docs/superpowers/specs/2026-08-30-ai-browser-design.md`

## Global Constraints

- Python 3.10+ (for match/case and modern async syntax)
- Ollama API with tools parameter (llama3.1 supports tool calling)
- Max 3 concurrent HTTP fetches
- 15 second timeout per HTTP request
- Max 3 tool-call rounds per conversation turn
- All tool handlers must be async
- No regex for intent/route detection (regex only for HTML cleanup if needed)

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/definitions.py` | Tool schemas as Python dicts for Ollama's `tools` parameter |
| `tools/executor.py` | Async dispatcher — maps tool names to handlers, runs in parallel |
| `tools/http_client.py` | Shared async HTTP client with retry/timeout logic |
| `tools/searching.py` | Async search handlers (web_search, news_search, browse_url) |
| `tools/searchingFinance.py` | Async finance handler (finance_lookup) |
| `tools/html_utils.py` | HTML text extraction utilities |
| `llm.py` | Tool-call loop — sends tools to Ollama, handles responses |
| `main.py` | Simplified chat loop |
| `config.py` | Async settings + tool settings |

---

### Task 1: Create Async HTTP Client

**Files:**
- Create: `tools/http_client.py`
- Test: `tests/tools/test_http_client.py`

**Interfaces:**
- Consumes: `config.FETCH_TIMEOUT`, `config.MAX_RETRIES`
- Produces: `async def fetch(url: str) -> str`, `async def fetch_json(url: str) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_http_client.py
import pytest
from tools.http_client import fetch

@pytest.mark.asyncio
async def test_fetch_returns_string():
    result = await fetch("https://httpbin.org/get")
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
async def test_fetch_empty_on_failure():
    result = await fetch("https://this-domain-does-not-exist-12345.com")
    assert result == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_http_client.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'tools.http_client'"

- [ ] **Step 3: Write minimal implementation**

```python
# tools/http_client.py
import asyncio
import ssl
from typing import Optional

import aiohttp
import certifi

from config import FETCH_TIMEOUT, MAX_RETRIES


async def fetch(url: str, timeout: Optional[int] = None) -> str:
    timeout = timeout or FETCH_TIMEOUT
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
                    }
                ) as response:
                    return await response.text()
            except Exception:
                if attempt == MAX_RETRIES - 1:
                    return ""
                await asyncio.sleep(0.5)
    return ""


async def fetch_json(url: str, timeout: Optional[int] = None) -> dict:
    text = await fetch(url, timeout)
    if not text:
        return {}
    import json
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_http_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/http_client.py tests/tools/test_http_client.py
git commit -m "feat: add async HTTP client with retry logic"
```

---

### Task 2: Create HTML Text Extraction Utility

**Files:**
- Create: `tools/html_utils.py`
- Test: `tests/tools/test_html_utils.py`

**Interfaces:**
- Consumes: raw HTML string
- Produces: `def extract_text(html: str, max_chars: int = 6000) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_html_utils.py
from tools.html_utils import extract_text

def test_extract_text_removes_tags():
    html = "<html><body><p>Hello</p><script>bad</script></body></html>"
    result = extract_text(html)
    assert "Hello" in result
    assert "bad" not in result

def test_extract_text_truncates():
    html = "<p>" + "x" * 10000 + "</p>"
    result = extract_text(html, max_chars=100)
    assert len(result) <= 100

def test_extract_text_empty_input():
    assert extract_text("") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_html_utils.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# tools/html_utils.py
import re

from bs4 import BeautifulSoup


def extract_text(html: str, max_chars: int = 6000) -> str:
    if not html:
        return ""
    
    soup = BeautifulSoup(html, "html.parser")
    
    for tag in soup(["script", "style", "nav", "footer", "header", 
                     "aside", "noscript", "form", "iframe", "svg", "button"]):
        tag.decompose()
    
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    
    return text[:max_chars]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_html_utils.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/html_utils.py tests/tools/test_html_utils.py
git commit -m "feat: add HTML text extraction utility"
```

---

### Task 3: Create Tool Definitions

**Files:**
- Create: `tools/definitions.py`

**Interfaces:**
- Consumes: nothing
- Produces: `TOOL_DEFINITIONS: list[dict]` — list of tool schemas for Ollama

- [ ] **Step 1: Write tool definitions**

```python
# tools/definitions.py
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for general information. Use when you need current data, facts, or information beyond your training cutoff.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default 3, max 5)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "news_search",
            "description": "Search for latest news articles and breaking stories. Use when the user asks about recent events, news, or current happenings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The news search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of articles (default 3, max 5)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finance_lookup",
            "description": "Look up stock market indices and financial data. Use for questions about IHSG, Nasdaq, Dow Jones, S&P 500, or specific stock symbols.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_or_name": {
                        "type": "string",
                        "description": "The index name (IHSG, Nasdaq) or stock symbol"
                    }
                },
                "required": ["symbol_or_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "Fetch and read the content of a specific webpage. Use when you have a URL and need to extract information from it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to browse"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to extract (default 5000)",
                        "default": 5000
                    }
                },
                "required": ["url"]
            }
        }
    }
]
```

- [ ] **Step 2: Commit**

```bash
git add tools/definitions.py
git commit -m "feat: add tool definitions for Ollama tool calling"
```

---

### Task 4: Create Async Tool Executor

**Files:**
- Create: `tools/executor.py`
- Test: `tests/tools/test_executor.py`

**Interfaces:**
- Consumes: tool definitions, handler functions from searching.py and searchingFinance.py
- Produces: `async def execute_tool(name: str, arguments: dict) -> str`, `async def execute_tools_parallel(calls: list[dict]) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_executor.py
import pytest
from tools.executor import execute_tool, execute_tools_parallel

@pytest.mark.asyncio
async def test_execute_tool_returns_string():
    result = await execute_tool("web_search", {"query": "test"})
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_execute_unknown_tool_returns_error():
    result = await execute_tool("nonexistent_tool", {})
    assert "error" in result.lower() or "unknown" in result.lower()

@pytest.mark.asyncio
async def test_execute_tools_parallel():
    calls = [
        {"name": "web_search", "arguments": {"query": "test 1"}},
        {"name": "web_search", "arguments": {"query": "test 2"}},
    ]
    results = await execute_tools_parallel(calls)
    assert len(results) == 2
    assert all(isinstance(r, str) for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_executor.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# tools/executor.py
import asyncio
from typing import Callable

from tools.searching import web_search_handler, news_search_handler, browse_url_handler
from tools.searchingFinance import finance_lookup_handler


TOOL_HANDLERS: dict[str, Callable] = {
    "web_search": web_search_handler,
    "news_search": news_search_handler,
    "finance_lookup": finance_lookup_handler,
    "browse_url": browse_url_handler,
}


async def execute_tool(name: str, arguments: dict) -> str:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"Error: Unknown tool '{name}'"
    
    try:
        return await handler(**arguments)
    except Exception as e:
        return f"Error executing {name}: {str(e)}"


async def execute_tools_parallel(calls: list[dict]) -> list[str]:
    tasks = [
        execute_tool(call["name"], call.get("arguments", {}))
        for call in calls
    ]
    return await asyncio.gather(*tasks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_executor.py -v`
Expected: PASS (will need handler stubs first — see Task 5 and 6)

- [ ] **Step 5: Commit**

```bash
git add tools/executor.py tests/tools/test_executor.py
git commit -m "feat: add async tool executor with parallel dispatch"
```

---

### Task 5: Refactor Searching Module to Async Handlers

**Files:**
- Modify: `tools/searching.py` (major refactor)
- Delete: `tools/wordpattern.json`
- Test: `tests/tools/test_searching.py`

**Interfaces:**
- Consumes: `tools/http_client.fetch`, `tools/html_utils.extract_text`
- Produces: `async def web_search_handler(query: str, max_results: int = 3) -> str`, `async def news_search_handler(query: str, max_results: int = 3) -> str`, `async def browse_url_handler(url: str, max_chars: int = 5000) -> str`

- [ ] **Step 1: Delete wordpattern.json**

```bash
rm tools/wordpattern.json
```

- [ ] **Step 2: Rewrite searching.py with async handlers**

```python
# tools/searching.py
import asyncio
import html
import urllib.parse

from tools.http_client import fetch
from tools.html_utils import extract_text
from config import MAX_CONCURRENT_FETCHES


async def _extract_search_results_bing(query: str, max_results: int = 5) -> list[dict]:
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({
        "q": query,
        "count": max_results,
    })
    
    page_html = await fetch(url)
    if not page_html:
        return []
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_html, "html.parser")
    results = []
    seen_links = set()
    
    for result_li in soup.find_all("li", class_="b_algo"):
        if len(results) >= max_results:
            break
        
        h2_tag = result_li.find("h2")
        if not h2_tag:
            continue
        
        link_tag = h2_tag.find("a")
        if not link_tag:
            continue
        
        href = link_tag.get("href", "")
        actual_url = _decode_bing_url(href)
        
        if not actual_url.startswith("http"):
            continue
        
        if actual_url in seen_links:
            continue
        
        title = link_tag.get_text(" ", strip=True)
        if not title:
            continue
        
        seen_links.add(actual_url)
        
        snippet_tag = result_li.find("p") or result_li.find("div", class_="b_caption")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
        
        results.append({
            "title": title,
            "url": actual_url,
            "snippet": snippet,
        })
    
    return results


def _decode_bing_url(href: str) -> str:
    if "bing.com/ck" not in href:
        return href
    
    href = html.unescape(href)
    parsed = urllib.parse.urlparse(href)
    params = urllib.parse.parse_qs(parsed.query)
    
    if "u" in params:
        encoded_url = params["u"][0]
        if encoded_url.startswith("a1"):
            try:
                import base64
                decoded_bytes = base64.b64decode(encoded_url[2:])
                return decoded_bytes.decode("utf-8")
            except Exception:
                pass
    
    return href


async def _fetch_pages_parallel(results: list[dict], max_chars: int = 5000) -> list[str]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
    
    async def fetch_one(result: dict) -> str:
        async with semaphore:
            page_html = await fetch(result["url"])
            text = extract_text(page_html, max_chars=max_chars)
            if len(text) < 300:
                return result.get("snippet", "")
            return text
    
    tasks = [fetch_one(r) for r in results]
    return await asyncio.gather(*tasks)


async def web_search_handler(query: str, max_results: int = 3) -> str:
    results = await _extract_search_results_bing(query, max_results=max_results * 2)
    
    if not results:
        return "No search results found."
    
    page_texts = await _fetch_pages_parallel(results[:max_results])
    
    parts = []
    for i, (result, text) in enumerate(zip(results[:max_results], page_texts), 1):
        if text:
            parts.append(
                f"Source {i}: {result['title']}\n"
                f"URL: {result['url']}\n"
                f"Content:\n{text}\n"
            )
    
    return "\n---\n".join(parts) if parts else "Could not retrieve page content."


async def news_search_handler(query: str, max_results: int = 3) -> str:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })
    
    feed = await fetch(url)
    if not feed:
        return "No news results found."
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(feed, "html.parser")
    results = []
    
    for item in soup.find_all("item"):
        if len(results) >= max_results:
            break
        
        title_tag = item.find("title")
        if not title_tag:
            continue
        
        title = title_tag.get_text(" ", strip=True)
        
        link = ""
        link_tag = item.find("link")
        if link_tag and link_tag.next_sibling:
            sibling_text = str(link_tag.next_sibling).strip()
            if sibling_text.startswith("http"):
                link = sibling_text
        
        description_tag = item.find("description")
        snippet = description_tag.get_text(" ", strip=True) if description_tag else ""
        
        if title:
            results.append({
                "title": title,
                "url": link,
                "snippet": snippet,
            })
    
    if not results:
        return "No news articles found."
    
    page_texts = await _fetch_pages_parallel(results)
    
    parts = []
    for i, (result, text) in enumerate(zip(results, page_texts), 1):
        content = text if text else result.get("snippet", "")
        if content:
            parts.append(
                f"News {i}: {result['title']}\n"
                f"URL: {result['url']}\n"
                f"Content:\n{content}\n"
            )
    
    return "\n---\n".join(parts) if parts else "Could not retrieve news content."


async def browse_url_handler(url: str, max_chars: int = 5000) -> str:
    page_html = await fetch(url)
    if not page_html:
        return f"Could not fetch URL: {url}"
    
    text = extract_text(page_html, max_chars=max_chars)
    if not text:
        return f"No readable content found at: {url}"
    
    return f"Content from {url}:\n{text}"
```

- [ ] **Step 3: Write tests**

```python
# tests/tools/test_searching.py
import pytest
from tools.searching import web_search_handler, news_search_handler, browse_url_handler

@pytest.mark.asyncio
async def test_web_search_returns_string():
    result = await web_search_handler("Python programming", max_results=2)
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
async def test_news_search_returns_string():
    result = await news_search_handler("technology", max_results=2)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_browse_url_returns_content():
    result = await browse_url_handler("https://example.com")
    assert isinstance(result, str)
    assert "Example" in result or "example" in result.lower()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/tools/test_searching.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/searching.py tests/tools/test_searching.py
git rm tools/wordpattern.json
git commit -m "feat: refactor searching to async handlers, remove regex patterns"
```

---

### Task 6: Refactor Finance Module to Async Handler

**Files:**
- Modify: `tools/searchingFinance.py`
- Test: `tests/tools/test_searching_finance.py`

**Interfaces:**
- Consumes: `tools/http_client.fetch_json`
- Produces: `async def finance_lookup_handler(symbol_or_name: str) -> str`

- [ ] **Step 1: Rewrite searchingFinance.py**

```python
# tools/searchingFinance.py
import datetime

from tools.http_client import fetch_json


FINANCE_INDEXES = {
    "ihsg": ("^JKSE", "IHSG (Jakarta Composite Index)"),
    "indeks harga saham gabungan": ("^JKSE", "IHSG (Jakarta Composite Index)"),
    "jkse": ("^JKSE", "IHSG (Jakarta Composite Index)"),
    "idx": ("^JKSE", "IHSG (Jakarta Composite Index)"),
    "nasdaq": ("^IXIC", "Nasdaq Composite"),
    "dow jones": ("^DJI", "Dow Jones Industrial Average"),
    "dowjones": ("^DJI", "Dow Jones Industrial Average"),
    "s&p 500": ("^GSPC", "S&P 500"),
    "sp500": ("^GSPC", "S&P 500"),
    "sandp": ("^GSPC", "S&P 500"),
}


def _resolve_symbol(symbol_or_name: str) -> str:
    query_lower = symbol_or_name.lower()
    
    for key, (symbol, _) in FINANCE_INDEXES.items():
        if key in query_lower:
            return symbol
    
    if symbol_or_name.startswith("^"):
        return symbol_or_name
    
    return symbol_or_name.upper()


async def finance_lookup_handler(symbol_or_name: str, max_days: int = 7) -> str:
    symbol = _resolve_symbol(symbol_or_name)
    
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + symbol
        + "?interval=1d&range=1mo"
    )
    
    data = await fetch_json(url)
    result = data.get("chart", {}).get("result", [{}])[0]
    meta = result.get("meta", {})
    closing_prices = (
        result.get("indicators", {})
        .get("quote", [{}])[0]
        .get("close", [])
    )
    timestamps = result.get("timestamp", [])
    
    if not closing_prices:
        return f"No data available for {symbol}"
    
    prices = [p for p in closing_prices if p is not None]
    
    if not prices:
        return f"No valid price data for {symbol}"
    
    current = prices[-1]
    previous_close = meta.get("previousClose") or (prices[-2] if len(prices) > 1 else prices[-1])
    
    change = current - previous_close
    percentage = (change / previous_close * 100) if previous_close else 0
    
    lines = [
        f"Index: {symbol} | Current price: {current:.2f}",
        f"Previous close: {previous_close:.2f} | Change: {change:+.2f} ({percentage:+.2f}%)",
    ]
    
    for i, timestamp in enumerate(timestamps):
        if closing_prices[i] is not None:
            day = datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
            lines.append(f"{day}: {closing_prices[i]:.2f}")
        
        if len([l for l in lines if ":" in l]) > max_days + 1:
            break
    
    return "\n".join(lines)
```

- [ ] **Step 2: Write tests**

```python
# tests/tools/test_searching_finance.py
import pytest
from tools.searchingFinance import finance_lookup_handler

@pytest.mark.asyncio
async def test_finance_lookup_ihsg():
    result = await finance_lookup_handler("IHSG")
    assert isinstance(result, str)
    assert "JKSE" in result or "price" in result.lower()

@pytest.mark.asyncio
async def test_finance_lookup_nasdaq():
    result = await finance_lookup_handler("nasdaq")
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_finance_lookup_invalid():
    result = await finance_lookup_handler("INVALID_SYMBOL_XYZ")
    assert isinstance(result, str)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/tools/test_searching_finance.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tools/searchingFinance.py tests/tools/test_searching_finance.py
git commit -m "feat: refactor finance module to async handler"
```

---

### Task 7: Rewrite LLM Module with Tool-Call Loop

**Files:**
- Modify: `llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `tools/definitions.TOOL_DEFINITIONS`, `tools/executor.execute_tools_parallel`
- Produces: `def chat(messages: list[dict]) -> dict`

- [ ] **Step 1: Rewrite llm.py**

```python
# llm.py
import ollama

from config import MODEL_NAME, NUM_PREDICT, MAX_TOOL_ROUNDS
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tools_parallel


def chat(messages: list[dict]) -> dict:
    for round_num in range(MAX_TOOL_ROUNDS):
        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            options={"num_predict": NUM_PREDICT},
        )
        
        message = response["message"]
        
        if not message.get("tool_calls"):
            return response
        
        tool_calls = message["tool_calls"]
        print(f"[Round {round_num + 1}] Executing {len(tool_calls)} tool(s) in parallel...")
        
        results = _run_tool_calls(tool_calls)
        
        messages.append(message)
        
        for tool_call, result in zip(tool_calls, results):
            messages.append({
                "role": "tool",
                "content": result,
                "name": tool_call["function"]["name"],
            })
    
    print(f"[Warning] Max tool rounds ({MAX_TOOL_ROUNDS}) reached, forcing final response")
    
    final_response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        options={"num_predict": NUM_PREDICT},
    )
    
    return final_response


def _run_tool_calls(tool_calls: list[dict]) -> list[str]:
    import asyncio
    
    calls = [
        {
            "name": tc["function"]["name"],
            "arguments": tc["function"].get("arguments", {}),
        }
        for tc in tool_calls
    ]
    
    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(execute_tools_parallel(calls))
    finally:
        loop.close()
    
    return results
```

- [ ] **Step 2: Write tests**

```python
# tests/test_llm.py
import pytest
from unittest.mock import patch, MagicMock
from llm import chat

@patch("llm.ollama.chat")
def test_chat_no_tool_calls(mock_chat):
    mock_response = {
        "message": {
            "role": "assistant",
            "content": "Hello!",
        }
    }
    mock_chat.return_value = mock_response
    
    result = chat([{"role": "user", "content": "Hi"}])
    assert result["message"]["content"] == "Hello!"
    assert mock_chat.call_count == 1

@patch("llm.execute_tools_parallel")
@patch("llm.ollama.chat")
def test_chat_with_tool_calls(mock_chat, mock_execute):
    tool_call_response = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": "test"},
                    }
                }
            ],
        }
    }
    
    final_response = {
        "message": {
            "role": "assistant",
            "content": "Here are the results...",
        }
    }
    
    mock_chat.side_effect = [tool_call_response, final_response]
    mock_execute.return_value = ["Search results..."]
    
    result = chat([{"role": "user", "content": "Search for test"}])
    assert result["message"]["content"] == "Here are the results..."
    assert mock_chat.call_count == 2
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_llm.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add llm.py tests/test_llm.py
git commit -m "feat: rewrite LLM module with tool-call loop"
```

---

### Task 8: Update Config with Async Settings

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Add async settings to config.py**

```python
# config.py (add these lines)

# Async/Tool settings
MAX_CONCURRENT_FETCHES = 3
FETCH_TIMEOUT = 15
MAX_RETRIES = 2
MAX_TOOL_ROUNDS = 3
```

- [ ] **Step 2: Commit**

```bash
git add config.py
git commit -m "feat: add async and tool-call settings to config"
```

---

### Task 9: Simplify Main Module

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Simplify main.py**

```python
# main.py
from profile import apply_profile_update, build_system_prompt, wants_profile_update
from llm import chat
from tts import speak

history = []

while True:
    user_input = input("You: ")
    
    print("thinking, please wait......")
    
    if wants_profile_update(user_input):
        apply_profile_update(user_input)
        text = "Oke, profil kamu sudah saya perbarui."
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": text})
        history = history[-8:]
        print("E.V : ", text)
        speak(text)
        continue
    
    history.append({"role": "user", "content": user_input})
    history = history[-8:]
    
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(),
        },
        *history,
    ]
    
    response = chat(messages)
    text = response["message"]["content"]
    print("E.V : ", text)
    speak(text)
    
    history.append({"role": "assistant", "content": text})
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: simplify main module (no regex routing)"
```

---

### Task 10: Add Requirements and Final Test

**Files:**
- Modify: `requirement.txt`

- [ ] **Step 1: Add aiohttp to requirements**

```
# requirement.txt (add this line)
aiohttp
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirement.txt
```

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 4: Manual integration test**

Run the assistant and test:
1. "Hello" — should respond without tool calls
2. "What's IHSG today?" — should call finance_lookup
3. "Search for latest AI news" — should call news_search
4. "What's the weather in Jakarta and any news about it?" — should call multiple tools in parallel

- [ ] **Step 5: Final commit**

```bash
git add requirement.txt
git commit -m "feat: add aiohttp dependency, complete tool-calling implementation"
```

---

## Summary

After completing all 10 tasks:
- No regex for intent/route detection
- LLM decides when/how to search via tool calling
- Parallel page fetching via asyncio
- 4-step flow: User → LLM decides tools → parallel execution → LLM answers → TTS
