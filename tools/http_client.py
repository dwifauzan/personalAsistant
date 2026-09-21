import asyncio
import ssl
from typing import Optional

import aiohttp
import certifi

from app.config import FETCH_TIMEOUT, MAX_RETRIES


async def fetch(url: str, timeout: Optional[int] = None) -> str:
    timeout = timeout or FETCH_TIMEOUT
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    async with aiohttp.ClientSession(connector=connector) as session:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers=headers,
                ) as response:
                    if response.status >= 400:
                        if attempt == MAX_RETRIES - 1:
                            return ""
                        await asyncio.sleep(1 + attempt)
                        continue
                    return await response.text()
            except Exception:
                if attempt == MAX_RETRIES - 1:
                    return ""
                await asyncio.sleep(0.5)
    return ""


async def fetch_json(url: str, timeout: Optional[int] = None) -> Optional[dict]:
    text = await fetch(url, timeout)
    if not text:
        print(f"[fetch_json] Empty response from: {url}")
        return None
    import json
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[fetch_json] JSON parse error from {url}: {e}")
        return None
