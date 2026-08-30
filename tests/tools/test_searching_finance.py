import pytest
from tools.searchingFinance import finance_lookup_handler

@pytest.mark.asyncio
async def test_finance_lookup_ihsg():
    result = await finance_lookup_handler("IHSG")
    assert isinstance(result, str)
    assert "JKSE" in result or "price" in result.lower()

@pytest.mark.asyncio
async def test_finance_lookup_nasdaq():
    result = await finance_lookup_handler("nasdaq")
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_finance_lookup_invalid():
    result = await finance_lookup_handler("INVALID_SYMBOL_XYZ")
    assert isinstance(result, str)
