"""
Modul pencarian data keuangan (stock market, indeks saham).

Fungsi utama:
- finance_index(): Mendeteksi apakah query tentang indeks saham (IHSG, Nasdaq, dll)
- finance_search(): Mengambil data harga saham dari Yahoo Finance

Sumber data:
- Yahoo Finance API untuk data real-time stock market
- Mendukung indeks: IHSG (^JKSE), Nasdaq (^IXIC), Dow Jones (^DJI), S&P 500 (^GSPC)

Flow:
1. Cek apakah query menyebutkan indeks saham
2. Jika ya, ambil data dari Yahoo Finance
3. Return informasi harga, perubahan, dan riwayat harian
"""

import base64
import datetime
import html
import json
from mailbox import linesep
from posixpath import join
import re
from sre_parse import parse
import ssl
from sys import base_exec_prefix
from unittest import result
from unittest.loader import defaultTestLoader
import urllib.parse
import urllib.request
import webbrowser

import certifi
from config import OPEN_BROWSER
from bs4 import BeautifulSoup

# Mapping nama indeks ke symbol Yahoo Finance
# Format: "nama_query": ("symbol", "nama_lengkap")
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

def _fetch(url):
    """
    Mengambil konten dari URL dengan retry mechanism.
    
    Args:
        url: URL yang akan di-fetch
    
    Returns:
        String berisi konten atau empty string jika gagal
    
    Note:
        - Menggunakan 2 SSL context untuk kompatibilitas
        - Retry 2x untuk setiap context
        - Timeout 40 detik
    """
    req = urllib.request.Request(
        url,
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
        })
    contexts = [
        ssl.create_default_context(cafile=certifi.where()),
        ssl._create_unverified_context()
    ]

    for context in contexts:
        for _ in range(2):
            try:
                with urllib.request.urlopen(req, timeout=40, context=context) as resp:
                    return resp.read().decode("utf-8", "ignore")
            except Exception:
                continue
    return ""


def finance_index(query):
    """
    Cek apakah query tentang indeks saham dan return symbol-nya.
    
    Args:
        query: Input dari user
    
    Returns:
        Tuple (symbol, nama_lengkap) jika match, None jika tidak
    
    Example:
        finance_index("berapa IHSG hari ini")  # ("^JKSE", "IHSG (Jakarta Composite Index)")
        finance_index("harga saham BBCA")      # None
    """
    query_lower = query.lower()

    for key, value in FINANCE_INDEXES.items():
        if key in query_lower:
            return value

    return None


def finance_search(symbol, max_days=7):
    """
    Mengambil data harga saham/indeks dari Yahoo Finance.
    
    Args:
        symbol: Symbol Yahoo Finance (contoh: "^JKSE", "^IXIC")
        max_days: Jumlah hari riwayat harga yang dikembalikan (default 7)
    
    Returns:
        String berisi informasi harga terformat:
        - Harga saat ini
        - Perubahan dari previous close
        - Persentase perubahan
        - Riwayat harga harian
    
    Example:
        finance_search("^JKSE")
        # "Index: ^JKSE | Regular price: 7234.56\n..."
    
    Note:
        - Data dari Yahoo Finance API (v8/finance/chart)
        - Interval harian, range 1 bulan
        - Jika data tidak tersedia, return empty string
    """
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol)
        + "?interval=1d&range=1mo"
    )

    data = json.loads(_fetch(url) or "{}")
    result = data.get("chart", {}).get("result", [{}])[0]
    meta = result.get("meta", {})
    closing_prices = (
        result.get("indicators", {})
        .get("quote", [{}])[0]
        .get("close", [])
    )
    timestamps = result.get("timestamp", [])

    if not closing_prices:
        return ""

    prices = [
        price for price in closing_prices
        if price is not None
    ]

    if not prices:
        return ""

    current = prices[-1]
    previous_close = meta.get("previousClose") or (
        prices[-2] if len(prices) > 1 else prices[-1]
    )

    change = current - previous_close
    percentage = (
        change / previous_close * 100
        if previous_close
        else 0
    )

    lines = [
        f"Index: {symbol} | Regular price: {current:.2f}",
        (
            f"Previous close: {previous_close:.2f} | "
            f"Change: {change:+.2f} ({percentage:+.2f}%)"
        ),
    ]

    for index, timestamp in enumerate(timestamps):
        if closing_prices[index] is not None:
            day = datetime.datetime.utcfromtimestamp(
                timestamp
            ).strftime("%Y-%m-%d")

            lines.append(
                f"{day}: {closing_prices[index]:.2f}"
            )

        if len([line for line in lines if ":" in line]) > max_days + 1:
            break

    return "\n".join(lines)
