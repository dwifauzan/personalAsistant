import datetime

from tools.http_client import fetch_json


FINANCE_INDEXES = {
    "ihsg": ("^JKSE", "IHSG (Jakarta Composite Index)"),
    "indeks harga saham gabungan": ("^JKSE", "IHSG (Jakarta Composite Index)"),
    "jkse": ("^JKSE", "IHSG (Jakarta Composite Index)"),
    "idx": ("^JKSE", "IHSG (Jakarta Composite Index)"),
    "nasdaq": ("^IXIC", "Nasdaq Composite"),
    "dow jones": ("^DJI", "Dow Jones Industrial Average"),
    "dowjones": ("^DJI", "Dow Jones Industrial Average"),
    "s&p 500": ("^GSPC", "S&P 500"),
    "sp500": ("^GSPC", "S&P 500"),
    "sandp": ("^GSPC", "S&P 500"),
}


def _resolve_symbol(symbol_or_name: str) -> str:
    query_lower = symbol_or_name.lower()

    for key, (symbol, _) in FINANCE_INDEXES.items():
        if key in query_lower:
            return symbol

    if symbol_or_name.startswith("^"):
        return symbol_or_name

    return symbol_or_name.upper()


async def finance_lookup_handler(symbol_or_name: str, max_days: int = 7) -> str:
    symbol = _resolve_symbol(symbol_or_name)

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + symbol
        + "?interval=1d&range=1mo"
    )

    data = await fetch_json(url)
    result = data.get("chart", {}).get("result", [{}])[0]
    meta = result.get("meta", {})
    closing_prices = (
        result.get("indicators", {})
        .get("quote", [{}])[0]
        .get("close", [])
    )
    timestamps = result.get("timestamp", [])

    if not closing_prices:
        return f"No data available for {symbol}"

    prices = [p for p in closing_prices if p is not None]

    if not prices:
        return f"No valid price data for {symbol}"

    current = prices[-1]
    previous_close = meta.get("previousClose") or (prices[-2] if len(prices) > 1 else prices[-1])

    change = current - previous_close
    percentage = (change / previous_close * 100) if previous_close else 0

    lines = [
        f"Index: {symbol} | Current price: {current:.2f}",
        f"Previous close: {previous_close:.2f} | Change: {change:+.2f} ({percentage:+.2f}%)",
    ]

    for i, timestamp in enumerate(timestamps):
        if closing_prices[i] is not None:
            day = datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
            lines.append(f"{day}: {closing_prices[i]:.2f}")

        if len([l for l in lines if ":" in l]) > max_days + 1:
            break

    return "\n".join(lines)
