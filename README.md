# personalAsistant — E.V Voice Assistant

CLI voice assistant named **E.V**, built on `ollama` (`llama3.1:latest`) + `Kokoro ONNX` TTS.

## Structure

```
main.py                  -> application entry point
app/                     -> assistant application package
  config.py              -> all settings (model, TTS voice, timeouts)
  llm.py                 -> Ollama/LM Studio chat + tool-call loop
  lmstudio.py            -> LM Studio HTTP fallback backend
  metrics.py             -> session usage counters for the TUI
  profile.py             -> long-term user memory service
  tts.py                 -> speech generation and serialized playback
  ui/tui.py              -> curses dashboard and input loop
tools/                   -> LLM-callable tools
  definitions.py         -> 7 tool schemas for Ollama
  executor.py            -> name->handler map + asyncio.gather parallel run
  searching.py           -> web_search (Bing scrape), news_search, browse_url (+ SSRF _validate_url)
  searchingFinance.py    -> finance_lookup (Yahoo chart API + Google Finance fallback)
  reminder.py            -> set/get/delete_reminder (JSON file)
  http_client.py         -> aiohttp fetch/fetch_json with retry
  html_utils.py          -> BeautifulSoup extract_text
reminder/
  alertMe.py + reminders.json -> background alerter
profile.md               -> long-term user profile data
kokoro-v1.0.onnx / voices-v1.0.bin -> TTS model files
docs/TOOLS_DOCUMENTATION.md -> detailed tools docs
requirements.txt
```

## Flow

1. **Start `main.py`:** spawn `reminder_loop()` daemon thread (`check_reminders()` every 30s), then launch the curses dashboard.
2. **TUI input `app/ui/tui.py`:** a Copilot-inspired terminal workspace with an open chat transcript, model/backend status, reminders and AI-usage sidebar, colored input bar, activity line, and command footer. Type a message and press Enter; use Ctrl-L to clear chat and Ctrl-C or Ctrl-Q to exit. AI/tool logs such as Ollama fallback messages are captured into the activity line instead of writing over the input bar. AI and reminder speech are queued through the dashboard loop to avoid concurrent CoreAudio playback.
3. **Profile branch `main.py`, `app/profile.py`:**
   `wants_profile_update()` regex match (ID/EN) -> `ollama.generate()` rewrites `profile.md` (with `.bak`, sanitize, length checks) -> short reply + `speak()`.
4. **Normal branch `main.py:47-61`:**
   Build `messages = [system_prompt(build_system_prompt() with profile.md) + history]` -> `llm.chat(messages)`.
5. **`app/llm.py` tool loop (max `MAX_TOOL_ROUNDS=3`):**
   `ollama.chat(..., tools=TOOL_DEFINITIONS)` -> if no `tool_calls`, fallback `_parse_text_tool_calls()` regex for models emitting JSON in text -> if none, return. Else `_run_tool_calls()` -> `asyncio.run(execute_tools_parallel())` -> append `assistant` + `role=tool` results, repeat. After max, force final `ollama.chat()` without tools.
6. **Speak `app/tts.py`:** lazy singleton `Kokoro()` (`_FloatSpeedSession` for float32 speed fix), `engine.create(text, voice=af_bella, lang=en-us)` -> sanitized audio -> serialized `sounddevice` playback.
7. **Reminders:** `tools/reminder.py` writes `reminder/reminders.json` (`HH:MM` normalized). `reminder/alertMe.py:36-52` matches `datetime.now("%H:%M")`, `speak(message)`, deletes fired entry.

`app/metrics.py` tracks model calls, tool calls, input/output characters, backend, and session duration for the dashboard's AI usage panel.

## Setup

```bash
python3.10 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
ollama pull llama3.1:latest
python main.py
```

Python 3.10 or newer is required. The current `kokoro-onnx` release requires
`onnxruntime>=1.20.1`, which does not provide a compatible package for Python
3.9 on macOS ARM.

Requires Kokoro model files in project root (`kokoro-v1.0.onnx`, `voices-v1.0.bin`).

## Configuration (`app/config.py`)

- `MODEL_NAME = "llama3.1:latest"`
- `NUM_PREDICT = 120` — short, TTS-friendly replies
- `KOKORO_VOICE = "af_bella"`, `KOKORO_LANGUAGE = "en-us"`, `KOKORO_SPEED = 1.0`, `KOKORO_SAMPLE_RATE = 24000`
- `MAX_CONCURRENT_FETCHES = 3`, `FETCH_TIMEOUT = 15`, `MAX_RETRIES = 2`, `MAX_TOOL_ROUNDS = 3`
- `OPEN_BROWSER = True`

## Tools

| Tool | Handler | Purpose |
|------|---------|---------|
| `web_search` | `searching.py` | Bing scrape |
| `news_search` | `searching.py` | Google News RSS |
| `finance_lookup` | `searchingFinance.py` | IHSG/Nasdaq/DJI/S&P500 + symbols |
| `browse_url` | `searching.py` | Fetch page + extract text (SSRF-guarded) |
| `set_reminder` / `get_reminders` / `delete_reminder` | `reminder.py` | JSON-backed reminders |

System prompt (`app/profile.py`) defines E.V as concise, friendly, 1-2 sentences, only answers most recent message, must actually call tools instead of describing them.

## Standalone reminder runner

`python -m reminder.alertMe` runs the polling loop directly. Importing `check_reminders` from `main.py` no longer blocks.
