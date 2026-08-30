import pytest
from tools.executor import execute_tool, execute_tools_parallel

@pytest.mark.asyncio
async def test_execute_tool_returns_string():
    result = await execute_tool("web_search", {"query": "test"})
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_execute_unknown_tool_returns_error():
    result = await execute_tool("nonexistent_tool", {})
    assert "error" in result.lower() or "unknown" in result.lower()

@pytest.mark.asyncio
async def test_execute_tools_parallel():
    calls = [
        {"name": "web_search", "arguments": {"query": "test 1"}},
        {"name": "web_search", "arguments": {"query": "test 2"}},
    ]
    results = await execute_tools_parallel(calls)
    assert len(results) == 2
    assert all(isinstance(r, str) for r in results)
