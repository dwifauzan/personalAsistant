from __future__ import annotations

import ollama
import asyncio
import json
import re
from . import lmstudio
from .config import MODEL_NAME, NUM_PREDICT, NUM_CTX, NUM_GPU, MAX_TOOL_ROUNDS, MAX_TOOL_CONTENT_CHARS
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tools_parallel
from .metrics import record_model_call, record_output, record_tool_calls


def chat(messages: list[dict]) -> dict:
    try:
        return _chat_loop(messages, backend="ollama")
    except Exception as e:
        if not lmstudio.is_connection_error(e):
            raise
        print(f"[INFO] Ollama unavailable ({e}), switching to LM Studio...")
        if not lmstudio.is_available():
            raise RuntimeError(
                "Ollama is unreachable and LM Studio is not running "
                "on http://localhost:1234. Start one of them and try again."
            ) from e
        return _chat_loop(messages, backend="lmstudio")


def _chat_loop(messages: list[dict], backend: str = "ollama") -> dict:
    for round_num in range(MAX_TOOL_ROUNDS):
        response = _backend_chat(messages, backend, with_tools=True)

        message = response["message"]

        if not message.get("tool_calls"):
            text = message.get("content", "")
            parsed = _parse_text_tool_calls(text)
            if parsed:
                tool_calls = parsed
                print(f"[Round {round_num + 1}] Parsed {len(tool_calls)} tool call(s) from text...")
            else:
                return response
        else:
            tool_calls = message["tool_calls"]

        print(f"[Round {round_num + 1}] Executing {tool_calls} tool(s) in parallel...")
        record_tool_calls(len(tool_calls))

        results = _run_tool_calls(tool_calls)

        if message.get("tool_calls"):
            messages.append(message)
        else:
            messages.append({"role": "assistant", "content": message.get("content", "")})

        for tool_call, result in zip(tool_calls, results):
            name = tool_call["function"]["name"]
            content = result or ""
            if len(content) > MAX_TOOL_CONTENT_CHARS:
                content = (
                    content[:MAX_TOOL_CONTENT_CHARS]
                    + f"\n...[truncated {len(result) - MAX_TOOL_CONTENT_CHARS} chars]..."
                )
            messages.append({
                "role": "tool",
                "content": content,
                "name": name,
            })

    print(f"[Warning] Max tool rounds ({MAX_TOOL_ROUNDS}) reached, forcing final response")

    return _backend_chat(messages, backend, with_tools=False)


def _backend_chat(messages: list[dict], backend: str, with_tools: bool) -> dict:
    record_model_call(backend)
    if backend == "lmstudio":
        response = lmstudio.chat(
            messages,
            tools=TOOL_DEFINITIONS if with_tools else None,
        )
        record_output(len(response["message"].get("content", "")))
        return response
    kwargs = {
        "model": MODEL_NAME,
        "messages": messages,
        "options": {"num_predict": NUM_PREDICT, "num_ctx": NUM_CTX, "num_gpu": NUM_GPU},
    }
    if with_tools:
        kwargs["tools"] = TOOL_DEFINITIONS
    response = ollama.chat(**kwargs, keep_alive="1m")
    record_output(len(response["message"].get("content", "")))
    return response


def _parse_text_tool_calls(text: str) -> list[dict] | None:
    patterns = [
        r'\{[^{}]*"name"\s*:\s*"(web_search|news_search|finance_lookup|browse_url|set_reminder|get_reminders|delete_reminder)"[^{}]*"arguments"\s*:\s*(\{[^{}]*\})[^{}]*\}',
        r'\{[^{}]*"name"\s*:\s*"(web_search|news_search|finance_lookup|browse_url|set_reminder|get_reminders|delete_reminder)"[^{}]*"parameters"\s*:\s*(\{[^{}]*\})[^{}]*\}',
    ]

    found_calls = []

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.DOTALL):
            func_name = match.group(1)
            try:
                args = json.loads(match.group(2))
            except json.JSONDecodeError:
                continue

            found_calls.append({
                "function": {
                    "name": func_name,
                    "arguments": args,
                }
            })

    return found_calls if found_calls else None


def _run_tool_calls(tool_calls: list[dict]) -> list[str]:
    calls = [
        {
            "name": tc["function"]["name"],
            "arguments": tc["function"].get("arguments", {}),
        }
        for tc in tool_calls
    ]

    return asyncio.run(execute_tools_parallel(calls))
