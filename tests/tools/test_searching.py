import pytest
from tools.searching import web_search_handler, news_search_handler, browse_url_handler

@pytest.mark.asyncio
async def test_web_search_returns_string():
    result = await web_search_handler("Python programming", max_results=2)
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
async def test_news_search_returns_string():
    result = await news_search_handler("technology", max_results=2)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_browse_url_returns_content():
    result = await browse_url_handler("https://example.com")
    assert isinstance(result, str)
    assert "Example" in result or "example" in result.lower()
