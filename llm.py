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
