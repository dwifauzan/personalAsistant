import pytest
from tools.http_client import fetch

@pytest.mark.asyncio
async def test_fetch_returns_string():
    result = await fetch("https://httpbin.org/get")
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
async def test_fetch_empty_on_failure():
    result = await fetch("https://this-domain-does-not-exist-12345.com")
    assert result == ""
