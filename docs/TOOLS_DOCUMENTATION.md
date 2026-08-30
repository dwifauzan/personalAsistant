# Tools Module Documentation

## Overview

The `tools/` module provides the AI with web browsing capabilities through Ollama's native tool-calling API. The LLM decides when and what to search — no regex routing.

## File Structure

```
tools/
├── http_client.py        # Async HTTP client with retry
├── html_utils.py         # HTML text extraction
├── definitions.py        # Tool schemas for Ollama
├── executor.py           # Parallel tool dispatcher
├── searching.py          # Web/news search handlers
└── searchingFinance.py   # Finance data handler
```

---

## tools/http_client.py

Async HTTP client. All network requests go through here.

### `async fetch(url: str, timeout: int = None) -> str`

Fetches a URL and returns its HTML content as a string.

- Uses `aiohttp` with SSL via `certifi`
- Retries up to `MAX_RETRIES` (2) times on failure
- Timeout: `FETCH_TIMEOUT` (15 seconds) per request
- Returns `""` on failure

### `async fetch_json(url: str, timeout: int = None) -> dict`

Fetches a URL and parses the response as JSON.

- Calls `fetch()` internally
- Returns `{}` on failure or invalid JSON

---

## tools/html_utils.py

HTML cleanup utility.

### `extract_text(html: str, max_chars: int = 6000) -> str`

Extracts clean text from raw HTML.

- Removes: `script`, `style`, `nav`, `footer`, `header`, `aside`, `noscript`, `form`, `iframe`, `svg`, `button`
- Collapses whitespace
- Truncates to `max_chars`
- Returns `""` for empty input

---

## tools/definitions.py

Tool schemas registered with Ollama. The LLM sees these definitions and decides which to call.

### `TOOL_DEFINITIONS: list[dict]`

Contains 4 tool schemas:

| Tool | Purpose | Parameters |
|------|---------|------------|
| `web_search` | Search the web (Bing) | `query` (str), `max_results` (int, default 3) |
| `news_search` | Search latest news (Google News RSS) | `query` (str), `max_results` (int, default 3) |
| `finance_lookup` | Stock/index data (Yahoo Finance) | `symbol_or_name` (str) |
| `browse_url` | Read a specific webpage | `url` (str), `max_chars` (int, default 5000) |

---

## tools/executor.py

Maps tool names to handler functions and runs them in parallel.

### `TOOL_HANDLERS: dict[str, Callable]`

Registry mapping tool names to async handler functions:
```
"web_search"       → web_search_handler
"news_search"      → news_search_handler
"finance_lookup"   → finance_lookup_handler
"browse_url"       → browse_url_handler
```

### `async execute_tool(name: str, arguments: dict) -> str`

Executes a single tool by name.

- Looks up handler in `TOOL_HANDLERS`
- Returns error string if tool not found
- Catches exceptions and returns error string

### `async execute_tools_parallel(calls: list[dict]) -> list[str]`

Executes multiple tool calls in parallel using `asyncio.gather()`.

- Input: list of `{"name": str, "arguments": dict}`
- Output: list of result strings (same order as input)
- All tools run concurrently

---

## tools/searching.py

Web and news search handlers. All async.

### `async web_search_handler(query: str, max_results: int = 3) -> str`

Searches Bing, fetches full pages in parallel, returns formatted content.

**Flow:**
1. Search Bing for `query` (fetches `max_results * 2` candidates)
2. Pick top `max_results` results
3. Fetch all pages in parallel (max 3 concurrent via semaphore)
4. Extract text from each page
5. If page text < 300 chars, fall back to snippet
6. Return formatted string: `Source N: title\nURL: ...\nContent: ...`

### `async news_search_handler(query: str, max_results: int = 3) -> str`

Searches Google News RSS, fetches full articles in parallel.

**Flow:**
1. Fetch Google News RSS feed for `query`
2. Parse `<item>` elements, extract title/link/snippet
3. Link extraction has 3 fallback strategies:
   - `next_sibling` of `<link>` tag
   - `<guid>` tag content
   - `<description>` tag's `<a href>`
4. Fetch all article pages in parallel
5. Return formatted string: `News N: title\nURL: ...\nContent: ...`

### `async browse_url_handler(url: str, max_chars: int = 5000) -> str`

Fetches a single URL and extracts its text content.

**Flow:**
1. Fetch URL via `http_client.fetch()`
2. Extract text via `html_utils.extract_text()`
3. Return `Content from {url}:\n{text}`

### Internal helpers

- `_extract_search_results_bing(query, max_results)` — parses Bing search results
- `_decode_bing_url(href)` — decodes Bing's base64 redirect URLs
- `_fetch_pages_parallel(results, max_chars)` — fetches multiple pages concurrently with semaphore

---

## tools/searchingFinance.py

Financial data handler.

### `async finance_lookup_handler(symbol_or_name: str, max_days: int = 7) -> str`

Looks up stock market index data from Yahoo Finance.

**Flow:**
1. Resolve name to Yahoo symbol (e.g., "IHSG" → "^JKSE")
2. Fetch chart data from Yahoo Finance API
3. Extract current price, previous close, change, percentage
4. Append daily closing prices (up to `max_days`)
5. Return formatted string

**Supported indexes:**

| Name | Symbol |
|------|--------|
| IHSG / IDX / JKSE | ^JKSE |
| Nasdaq | ^IXIC |
| Dow Jones | ^DJI |
| S&P 500 | ^GSPC |

### Internal helpers

- `_resolve_symbol(symbol_or_name)` — maps human names to Yahoo Finance symbols

---

## llm.py

The tool-call loop. This is the brain of the new architecture.

### `chat(messages: list[dict]) -> dict`

Main entry point. Sends messages to Ollama with tool definitions, handles tool calls in a loop.

**Flow:**
```
1. Send messages + tool definitions to Ollama
2. If response has no tool_calls → return response (done)
3. If response has tool_calls:
   a. Execute all tool calls in parallel via executor
   b. Append assistant message to messages
   c. Append each tool result as {"role": "tool", ...}
   d. Go back to step 1 (max 3 rounds)
4. After max rounds → force final response (no tools) → return
```

### `_run_tool_calls(tool_calls: list[dict]) -> list[str]`

Bridges sync/async — creates an event loop, runs `execute_tools_parallel()`, closes the loop.

---

## main.py

Simplified chat loop. No routing logic.

**Flow:**
```
1. Read user input
2. If profile update → handle separately (still uses regex in profile.py)
3. Build messages: [system_prompt + history]
4. Call chat(messages) → LLM handles everything (tools, search, etc.)
5. Print + speak response
6. Append to history
```

---

## Complete Data Flow

```
User: "What's IHSG today and any news about it?"
  │
  ▼
main.py
  │ builds messages = [system_prompt + history]
  │ calls chat(messages)
  ▼
llm.py — chat()
  │ sends to Ollama with tools=[web_search, news_search, finance_lookup, browse_url]
  │
  │ Ollama response:
  │   tool_calls: [
  │     {name: "finance_lookup", args: {symbol_or_name: "IHSG"}},
  │     {name: "news_search", args: {query: "IHSG Jakarta"}}
  │   ]
  │
  │ calls _run_tool_calls()
  ▼
tools/executor.py — execute_tools_parallel()
  │ asyncio.gather(
  │   finance_lookup_handler("IHSG"),
  │   news_search_handler("IHSG Jakarta")
  │ )
  │
  │ ┌─────────────────────────────┐  ┌──────────────────────────────┐
  │ │ searchingFinance.py         │  │ searching.py                 │
  │ │ finance_lookup_handler()    │  │ news_search_handler()        │
  │ │   → resolve "IHSG" → ^JKSE │  │   → fetch Google News RSS    │
  │ │   → fetch_json Yahoo API   │  │   → parse articles           │
  │ │   → format price data      │  │   → fetch pages in parallel  │
  │ │   → return string          │  │   → format articles          │
  │ └─────────────────────────────┘  └──────────────────────────────┘
  │         │                                │
  │         ▼                                ▼
  │   Both use http_client.fetch() / fetch_json()
  │   Both use html_utils.extract_text()
  │
  │ returns ["Index: ^JKSE | Current price: 7234.56...", "News 1: ..."]
  ▼
llm.py — chat() (continued)
  │ appends assistant message + tool results to messages
  │ sends back to Ollama (round 2)
  │
  │ Ollama response:
  │   "IHSG is at 7,234.56 (+0.45%). Meanwhile, breaking news reports..."
  │   (no tool_calls → return)
  ▼
main.py
  │ prints "E.V : IHSG is at 7,234.56..."
  │ calls speak() → TTS audio output
  ▼
User hears the response
```

---

## Config Reference

| Setting | Value | Used By |
|---------|-------|---------|
| `MAX_CONCURRENT_FETCHES` | 3 | `searching.py` — semaphore for parallel page fetches |
| `FETCH_TIMEOUT` | 15 | `http_client.py` — seconds per HTTP request |
| `MAX_RETRIES` | 2 | `http_client.py` — retry attempts on failure |
| `MAX_TOOL_ROUNDS` | 3 | `llm.py` — max tool-call loop iterations |
| `MODEL_NAME` | llama3.1:latest | `llm.py` — Ollama model |
| `NUM_PREDICT` | 140 | `llm.py` — max tokens per response |
