import ollama
import asyncio
import json
import re
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

        results = _run_tool_calls(tool_calls)

        if message.get("tool_calls"):
            messages.append(message)
        else:
            messages.append({"role": "assistant", "content": message.get("content", "")})

        for tool_call, result in zip(tool_calls, results):
            name = tool_call["function"]["name"]
            messages.append({
                "role": "tool",
                "content": result,
                "name": name,
            })

    print(f"[Warning] Max tool rounds ({MAX_TOOL_ROUNDS}) reached, forcing final response")

    final_response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        options={"num_predict": NUM_PREDICT},
    )
    return final_response


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
