# E.V - Bug & Security Todo List

## Completed
- [x] Bug #1: Hardcoded paths in `config.py` → fixed with `Path(__file__).parent`
- [x] Bug #2: No graceful shutdown in `main.py` → fixed with `try/except KeyboardInterrupt`
- [x] Bug #3: No error handling in `main.py` → fixed with inner `try/except Exception`
- [x] Bug #4: Profile update writes raw LLM output → fixed with backup + validation
- [x] Bug #5: Markdown stripping only handles ``` prefix → fixed with regex for headings, bold, italic, code
- [x] Bug #6: `asyncio.new_event_loop()` per call in `llm.py` → fixed with `asyncio.run()`

---

## Bugs

| # | Location | Issue |
|---|---|---|
| 7 | `tools/searchingFinance.py:36-43` | `_fetch_yahoo_finance` points to TradingView **HTML** page, not a JSON API — `fetch_json` always returns `{}`, silently fails every time |
| 8 | `tools/searching.py:163-164` | News link extraction relies on `next_sibling` — fragile, breaks on Google News HTML structure changes |
| 9 | `tools/http_client.py:46-53` | `fetch_json` silently swallows all errors — JSON parse failure returns `{}` with no indication something went wrong |
| 10 | `tts.py:29` | Global `engine` with `global` keyword — race condition if called from multiple threads |
| 11 | `requirement.txt` | Non-standard filename (`requirement.txt` vs `requirements.txt`) — `pip install -r` won't find it without explicit name |

---

## Security

| # | Location | Severity | Issue |
|---|---|---|---|
| ~~1~~ | ~~`tools/executor.py` + `browse_url`~~ | ~~**High**~~ | ~~SSRF~~ — Fixed: added `_validate_url()` in `tools/searching.py` — blocks non-http(s) schemes, resolves hostnames and rejects private/loopback/link-local/reserved IPs |
| 2 | `profile.py:139` | **High** | Arbitrary file write — LLM output written directly to `profile.md`. Prompt injection could make the LLM write malicious content |
| 3 | `profile.md` | **Medium** | Sensitive data in plaintext — health records (panic attack, mental health, blood pressure) stored unencrypted |
| 4 | `tools/http_client.py` | **Medium** | No URL scheme validation — could be used with `file://` protocol to read local files |
| 5 | `tools/searching.py:15-19` | **Low** | Bing scraping violates their ToS — could result in IP being blocked |
