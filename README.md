# personalAsistant — E.V Voice Assistant

CLI voice assistant named **E.V**, built on `ollama` (`llama3.1:latest`) + `Kokoro ONNX` TTS develop for lightweight and fast answers not design for complex necessary or heavy context.

goals created this project about research

## Flow

1. **Start `main.py`:** spawn `reminder_loop()` daemon thread (`check_reminders()` every 30s), then launch the curses dashboard.
2. **TUI input `app/ui/tui.py`:** a Copilot-inspired terminal workspace with an open chat transcript and a lightweight information rail rather than a boxed workspace panel. The rail groups local time, reminders, connection/model details, AI usage, and latest activity. The colored input bar, live status line, spinner, and in-chat process lines remain separate from the conversation. Type a message and press Enter; use Ctrl-L to clear chat and Ctrl-C or Ctrl-Q to exit. Each request shows `Working...`, then streams Ollama fallback, model rounds, searches, and tool execution directly inside the chat as process lines, followed by `Completed` or an error. AI and reminder speech are queued through the dashboard loop to avoid concurrent CoreAudio playback.
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

