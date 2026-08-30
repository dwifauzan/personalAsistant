import asyncio
import ssl
from typing import Optional

import aiohttp
import certifi

from config import FETCH_TIMEOUT, MAX_RETRIES


async def fetch(url: str, timeout: Optional[int] = None) -> str:
    timeout = timeout or FETCH_TIMEOUT
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
                    }
                ) as response:
                    return await response.text()
            except Exception:
                if attempt == MAX_RETRIES - 1:
                    return ""
                await asyncio.sleep(0.5)
    return ""


async def fetch_json(url: str, timeout: Optional[int] = None) -> dict:
    text = await fetch(url, timeout)
    if not text:
        return {}
    import json
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
