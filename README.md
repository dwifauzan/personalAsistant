# personalAsistant — E.V Voice Assistant

CLI voice assistant named **E.V**, built on `ollama` (`llama3.1:latest`) + `Kokoro ONNX` TTS.

## Structure

```
main.py                  -> entry loop + reminder thread
config.py                -> all settings (model, TTS voice, timeouts)
llm.py                   -> Ollama chat + tool-call loop
profile.py + profile.md  -> long-term user memory
tts.py                   -> speech output (Kokoro ONNX)
kokoro-v1.0.onnx / voices-v1.0.bin -> TTS model files
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
docs/TOOLS_DOCUMENTATION.md -> detailed tools docs
requirements.txt
```

## Flow

1. **Start `main.py:10-20`:** spawn `reminder_loop()` daemon thread (`check_reminders()` every 30s).
2. **Input loop `main.py:24-61`:** `input("You: ")`, keep `history` sliding window `history[-4:]` (~2 turns).
3. **Profile branch `main.py:32-40`, `profile.py:80-188`:**
   `wants_profile_update()` regex match (ID/EN) -> `ollama.generate()` rewrites `profile.md` (with `.bak`, sanitize, length checks) -> short reply + `speak()`.
4. **Normal branch `main.py:47-61`:**
   Build `messages = [system_prompt(build_system_prompt() with profile.md) + history]` -> `llm.chat(messages)`.
5. **`llm.py:10-56` tool loop (max `MAX_TOOL_ROUNDS=3`):**
   `ollama.chat(..., tools=TOOL_DEFINITIONS)` -> if no `tool_calls`, fallback `_parse_text_tool_calls()` regex for models emitting JSON in text -> if none, return. Else `_run_tool_calls()` -> `asyncio.run(execute_tools_parallel())` -> append `assistant` + `role=tool` results, repeat. After max, force final `ollama.chat()` without tools.
6. **Speak `tts.py:69-93`:** lazy singleton `Kokoro()` (`_FloatSpeedSession` for float32 speed fix), `engine.create(text, voice=af_bella, lang=en-us)` -> `sounddevice.play()+wait()` blocking.
7. **Reminders:** `tools/reminder.py` writes `reminder/reminders.json` (`HH:MM` normalized). `reminder/alertMe.py:36-52` matches `datetime.now("%H:%M")`, `speak(message)`, deletes fired entry.

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

## Configuration (`config.py`)

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

System prompt (`profile.py:67-77`) defines E.V as concise, friendly, 1-2 sentences, only answers most recent message, must actually call tools instead of describing them.

## Standalone reminder runner

`python -m reminder.alertMe` runs the polling loop directly. Importing `check_reminders` from `main.py` no longer blocks.
