"""
Fallback LLM backend via LM Studio (OpenAI-compatible API).

Used automatically when Ollama is unreachable (e.g. second computer
running Ollama is turned off). Only uses the Python standard library,
so no extra entries in requirements.txt are needed.

Response shapes returned here intentionally mirror the `ollama` package:
- chat()   -> {"message": {"role", "content", "tool_calls": [...]}}
- generate() -> {"response": "..."}
"""

import json
import socket
import urllib.parse
import urllib.request

from config import (
    LMSTUDIO_BASE_URL,
    LMSTUDIO_MODEL_NAME,
    LMSTUDIO_TIMEOUT,
    NUM_PREDICT,
)


def is_connection_error(error: Exception) -> bool:
    """Heuristic: is this exception caused by the LLM server being down?"""
    text = f"{type(error).__name__}: {error}".lower()
    markers = (
        "connect",
        "connection",
        "refused",
        "unreachable",
        "timed out",
        "timeout",
        "failed to connect",
        "no route to host",
        "temporary failure",
    )
    return any(marker in text for marker in markers)


def is_available(timeout: float = 3) -> bool:
    """Quick check whether LM Studio is reachable (short timeout)."""
    try:
        parsed = urllib.parse.urlparse(LMSTUDIO_BASE_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 80
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Chat completion via LM Studio, returned in ollama response shape."""
    payload: dict = {
        "model": LMSTUDIO_MODEL_NAME,
        "messages": _to_openai_messages(messages),
        # Cap is a safety net only; the system prompt keeps answers short.
        # Well above NUM_PREDICT because reasoning models spend tokens
        # on hidden thinking before answering / calling tools.
        "max_tokens": max(NUM_PREDICT, 1024),
    }
    if tools is not None:
        payload["tools"] = tools

    data = _post("/chat/completions", payload)
    message = data["choices"][0]["message"]

    tool_calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
        tool_calls.append({
            "function": {
                "name": function.get("name", ""),
                "arguments": arguments,
            }
        })

    return {
        "message": {
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": tool_calls,
        }
    }


def generate(prompt: str) -> dict:
    """Single-prompt completion via LM Studio, in ollama generate shape."""
    data = _post("/chat/completions", {
        "model": LMSTUDIO_MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max(NUM_PREDICT, 1024),
    })
    return {"response": data["choices"][0]["message"].get("content") or ""}


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """Convert ollama-style history to OpenAI-style messages.

    - role "tool" has no OpenAI equivalent without call ids, so tool
      results are passed back as user messages with a name prefix.
    - assistant tool_calls get synthesized ids when missing.
    """
    converted = []
    for msg in messages:
        role = msg.get("role")
        if role == "tool":
            name = msg.get("name", "tool")
            converted.append({
                "role": "user",
                "content": f"[{name} result]: {msg.get('content', '')}",
            })
        elif role == "assistant" and msg.get("tool_calls"):
            calls = []
            for i, call in enumerate(msg["tool_calls"]):
                function = call.get("function", {})
                arguments = function.get("arguments", {})
                if not isinstance(arguments, str):
                    arguments = json.dumps(arguments)
                calls.append({
                    "id": call.get("id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": function.get("name", ""),
                        "arguments": arguments,
                    },
                })
            converted.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": calls,
            })
        else:
            converted.append({
                "role": role,
                "content": msg.get("content", ""),
            })
    return converted


def _post(path: str, payload: dict) -> dict:
    url = LMSTUDIO_BASE_URL.rstrip("/") + path
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=LMSTUDIO_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"LM Studio request failed: {e}") from e
