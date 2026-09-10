# this file is used to execute all tools available in parallel using asyncio

import asyncio
from typing import Callable

from tools.searching import web_search_handler, news_search_handler, browse_url_handler
from tools.searchingFinance import finance_lookup_handler
from tools.reminder import set_reminder_handler, get_reminders_handler, delete_reminder_handler

TOOL_HANDLERS: dict[str, Callable] = {
    "web_search": web_search_handler,
    "news_search": news_search_handler,
    "finance_lookup": finance_lookup_handler,
    "browse_url": browse_url_handler,
    "set_reminder": set_reminder_handler,
    "get_reminders": get_reminders_handler,
    "delete_reminder": delete_reminder_handler,
}

async def execute_tool(name: str, arguments: dict) -> str:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"Error: Unknown tool '{name}'"

    try:
        # print ("dapet nih dari tools.executor ini name ", name)
        # print (f"dapet nih dari tools.executor ini arguments: {arguments}")
        return await handler(**arguments)
    except Exception as e:
        return f"Error executing {name}: {str(e)}"


async def execute_tools_parallel(calls: list[dict]) -> list[str]:
    tasks = [
        execute_tool(call["name"], call.get("arguments", {}))
        for call in calls
    ]
    return await asyncio.gather(*tasks)
