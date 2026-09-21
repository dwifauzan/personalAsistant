from __future__ import annotations

import datetime
import re
from bs4 import BeautifulSoup

from tools.http_client import fetch, fetch_json
from tools.html_utils import extract_text


FINANCE_INDEXES = {
    "ihsg": ("^JKSE", "IHSG (Jakarta Composite Index)", "JKSE:IDX"),
    "indeks harga saham gabungan": ("^JKSE", "IHSG (Jakarta Composite Index)", "JKSE:IDX"),
    "jkse": ("^JKSE", "IHSG (Jakarta Composite Index)", "JKSE:IDX"),
    "idx": ("^JKSE", "IHSG (Jakarta Composite Index)", "JKSE:IDX"),
    "nasdaq": ("^IXIC", "Nasdaq Composite", "IXIC:INDEXNASDAQ"),
    "dow jones": ("^DJI", "Dow Jones Industrial Average", "DJI:INDEXDJX"),
    "dowjones": ("^DJI", "Dow Jones Industrial Average", "DJI:INDEXDJX"),
    "s&p 500": ("^GSPC", "S&P 500", "INX:INDEXSP"),
    "sp500": ("^GSPC", "S&P 500", "INX:INDEXSP"),
    "sandp": ("^GSPC", "S&P 500", "INX:INDEXSP"),
}


def _resolve_symbol(symbol_or_name: str) -> tuple[str, str]:
    query_lower = symbol_or_name.lower()

    for key, value in FINANCE_INDEXES.items():
        if key in query_lower:
            return value[0], value[2]

    if symbol_or_name.startswith("^"):
        return symbol_or_name, symbol_or_name

    return symbol_or_name.upper(), symbol_or_name.upper()


async def _fetch_yahoo_finance(symbol: str) -> dict:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        "?interval=1d&range=1mo"
    )
    print(f"[finance_lookup] Fetching Yahoo Finance for: {symbol}")
    return await fetch_json(url)


async def _fetch_google_finance(google_symbol: str) -> str:
    url = f"https://www.google.com/finance/quote/{google_symbol}"
    return await fetch(url)


def _parse_google_finance(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    price_elem = soup.find("div", class_="bpE1Je")
    if price_elem:
        price_text = price_elem.get_text(strip=True)
        price_text = re.sub(r"[^\d.,]", "", price_text)
        price_text = price_text.replace(",", "")
        try:
            result["price"] = float(price_text)
        except ValueError:
            pass

    change_elems = soup.find_all("span", class_="ymyBi")
    for elem in change_elems:
        text = elem.get_text(strip=True)
        if "%" in text:
            percent_text = re.sub(r"[^\d.\-+%]", "", text).replace("%", "")
            try:
                result["percent"] = float(percent_text)
            except ValueError:
                pass
        else:
            change_text = re.sub(r"[^\d.\-+]", "", text)
            try:
                result["change"] = float(change_text)
            except ValueError:
                pass

    return result


async def finance_lookup_handler(symbol_or_name: str, max_days: int | str = 7) -> str:
    max_days = int(max_days)
    yahoo_symbol, google_symbol = _resolve_symbol(symbol_or_name)
    print(f"[finance_lookup] Looking up: {symbol_or_name} → {yahoo_symbol}")

    data = await _fetch_yahoo_finance(yahoo_symbol)
    if not data:
        print(f"[finance_lookup] Yahoo Finance returned no data")
        data = {}
    result = data.get("chart", {}).get("result", [{}])[0]
    meta = result.get("meta", {})
    closing_prices = (
        result.get("indicators", {})
        .get("quote", [{}])[0]
        .get("close", [])
    )
    timestamps = result.get("timestamp", [])

    if closing_prices:
        prices = [p for p in closing_prices if p is not None]

        if prices:
            current = prices[-1]
            previous_close = meta.get("previousClose") or (prices[-2] if len(prices) > 1 else prices[-1])

            change = current - previous_close
            percentage = (change / previous_close * 100) if previous_close else 0

            lines = [
                f"Index: {yahoo_symbol} | Current price: {current:.2f}",
                f"Previous close: {previous_close:.2f} | Change: {change:+.2f} ({percentage:+.2f}%)",
            ]

            for i, timestamp in enumerate(timestamps):
                if closing_prices[i] is not None:
                    day = datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
                    lines.append(f"{day}: {closing_prices[i]:.2f}")

                if len([l for l in lines if ":" in l]) > max_days + 1:
                    break

            print(f"[finance_lookup] Got data from Yahoo Finance")
            return "\n".join(lines)

    print(f"[finance_lookup] TradingView failed, trying Google Finance...")
    html = await _fetch_google_finance(google_symbol)
    if html:
        google_data = _parse_google_finance(html)
        if google_data.get("price"):
            price = google_data["price"]
            change = google_data.get("change", 0)
            percent = google_data.get("percent", 0)

            print(f"[finance_lookup] Got data from Google Finance: {price}")
            return (
                f"Index: {yahoo_symbol} | Current price: {price:.2f}\n"
                f"Change: {change:+.2f} ({percent:+.2f}%)\n"
                f"(Source: Google Finance)"
            )

    print(f"[finance_lookup] No data available")
    return f"No data available for {yahoo_symbol}"
