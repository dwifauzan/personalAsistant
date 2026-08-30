"""
Modul pencarian web dan news untuk voice assistant.

Fungsi utama:
- search_for_context(): Fungsi utama yang menentukan jenis pencarian dan mengambil konten
- news_search_rss(): Mencari berita via Google News RSS
- web_search_full_pages(): Mencari web dan mengambil konten halaman penuh
- web_engine_search(): Pencarian web biasa (snippet only)

Flow pencarian:
1. Analisis apakah user butuh info real-time, news, atau general web
2. Pilih route yang tepat (finance/news/web)
3. Fetch konten dari sumber yang sesuai
4. Return konten untuk AI agar bisa menjawab dengan data terkini

Konfigurasi:
- SEARCH_RESULTS: jumlah hasil pencarian default
- OPEN_BROWSER: apakah browser otomatis terbuka saat search
"""

import base64
import datetime
import html
import json
from mailbox import linesep
import os
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
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings

# Suppress warning ketika parse XML (RSS) sebagai HTML
# html.parser cukup untuk menangani RSS feed
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .searchingFinance import finance_index, finance_search

SEARCH_RESULTS = 5

_patterns_path = os.path.join(os.path.dirname(__file__), "wordpattern.json")
with open(_patterns_path, "r", encoding="utf-8") as _f:
    _patterns = json.load(_f)

UNCERTAINTY_PATTERNS = _patterns["uncertainty_patterns"]
CURRENT_INFO_PATTERNS = _patterns["current_info_patterns"]
SEARCH_REQUEST_PATTERNS = _patterns["search_request_patterns"]
WEB_ROUTE_PATTERNS = _patterns["web_route_patterns"]
NEWS_ROUTE_PATTERNS = _patterns["news_route_patterns"]
FOLLOWUP_PATTERNS = _patterns["followup_patterns"]
CLEAN_WORDS = _patterns["clean_words"]
NEWS_FILLER_WORDS = _patterns["news_filler_words"]

# Menyimpan query dan route terakhir untuk follow-up questions
_last_query = ""
_last_route = ""

def _fetch(url):
    """
    Mengambil konten dari URL dengan retry mechanism.
    
    Args:
        url: URL halaman yang akan di-fetch
    
    Returns:
        String berisi konten halaman, atau empty string jika gagal
    
    Note:
        - Menggunakan 2 SSL context (verified & unverified) untuk kompatibilitas
        - Retry 2x untuk setiap context jika gagal
        - Timeout 40 detik per request
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

def extract_text_from_html(page_html, max_chars=6000):
    """
    Mengekstrak text bersih dari HTML dengan menghapus tag tidak perlu.
    
    Args:
        page_html: String HTML yang akan diekstrak
        max_chars: Maksimum karakter yang dikembalikan (default 6000)
    
    Returns:
        String text bersih tanpa tag HTML
    
    Note:
        Menghapus tag: script, style, nav, footer, header, aside, 
        noscript, form, iframe, svg, button
    """
    if not page_html:
        return ""

    soup = BeautifulSoup(page_html, "html.parser")

    for tag in soup(
        [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "nonscript",
            "form",
            "iframe",
            "svg",
            "button"
        ]
    ):
        tag.decompose()

    text = soup.get_text(" ", strip = True)
    text = re.sub(r"\s+", " ", text).strip()

    return text[:max_chars]

def fetch_page_text(url, max_chars=6000):
    """
    Mengambil halaman web dan mengekstrak text-nya.
    
    Args:
        url: URL halaman yang akan diambil
        max_chars: Maksimum karakter text yang dikembalikan
    
    Returns:
        String text bersih dari halaman web
    """
    return extract_text_from_html(_fetch(url), max_chars)

def _decode_google_url(href):
    """
    Decode URL redirect Google (/url?q=) menjadi URL asli.
    
    Args:
        href: URL yang mungkin berupa Google redirect
    
    Returns:
        URL asli tujuan redirect
    """
    print("doing get content page on google ")
    href = html.unescape(href)
    parsed = urllib.parse.urlparse(href)

    if parsed.path == "/url":
        parameters = urllib.parse.parse_qs(parsed.query)
        return parameters.get("q", parameters.get("url", [href]))[0]

    return href

def _has_snippet_class(value):
    """
    Cek apakah element memiliki class yang menandakan Google search snippet.
    
    Args:
        value: Class attribute value (string atau list)
    
    Returns:
        True jika memiliki class VwiC3b atau yXK7Qe (Google snippet classes)
    """
    if isinstance(value, list):
        classes = value
    else:
        classes = str(value or "").split()

    return bool({"VwiC3b", "yXK7Qe"} & set(classes))

def _find_google_snippet(anchor):
    """
    Mencari snippet text di parent element dari sebuah anchor/link.
    
    Args:
        anchor: BeautifulSoup element (link/tag a)
    
    Returns:
        String snippet text atau empty string jika tidak ditemukan
    """
    for parent in anchor.parents:
        snippet = parent.find("div", class_=_has_snippet_class)

        if snippet:
            return snippet.get_text(" ", strip=True)

    return ""

def _decode_bing_url(href):
    """
    Decode URL redirect Bing menjadi URL asli tujuan.
    
    Args:
        href: URL yang mungkin berupa Bing redirect
    
    Returns:
        URL asli tujuan
    
    Note:
        Bing menggunakan base64 encoding untuk URL di parameter 'u'
    """
    if "bing.com/ck" not in href:
        return href

    href = html.unescape(href)
    parsed = urllib.parse.urlparse(href)
    params = urllib.parse.parse_qs(parsed.query)

    if "u" in params:
        encoded_url = params["u"][0]
        if encoded_url.startswith("a1"):
            try:
                decoded_bytes = base64.b64decode(encoded_url[2:])
                return decoded_bytes.decode("utf-8")
            except Exception:
                pass

    return href


def _extract_search_results(query, max_results=SEARCH_RESULTS):
    """
    Ekstrak hasil pencarian dari Bing search.
    
    Args:
        query: Kata kunci pencarian
        max_results: Jumlah maksimum hasil yang dikembalikan
    
    Returns:
        List of dict dengan keys: 'title', 'url', 'snippet'
    
    Note:
        Menggunakan Bing karena lebih mudah di-parse dibanding Google.
        URL redirect Bing akan di-decode menjadi URL asli.
    """
    url = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {
            "q": query,
            "count": max_results,
        }
    )

    page_html = _fetch(url)

    if not page_html:
        return []

    soup = BeautifulSoup(page_html, "html.parser")
    results = []
    seen_links = set()

    for result_li in soup.find_all("li", class_="b_algo"):
        if len(results) >= max_results:
            break

        h2_tag = result_li.find("h2")
        if not h2_tag:
            continue

        link_tag = h2_tag.find("a")
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        actual_url = _decode_bing_url(href)
        parsed_link = urllib.parse.urlparse(actual_url)

        if parsed_link.scheme not in ("http", "https"):
            continue

        if actual_url in seen_links:
            continue

        title = link_tag.get_text(" ", strip=True)

        if not title:
            continue

        seen_links.add(actual_url)

        snippet_tag = result_li.find("p") or result_li.find("div", class_="b_caption")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        results.append(
            {
                "title": title,
                "url": actual_url,
                "snippet": snippet,
            }
        )

    return results


def web_engine_search(query, max_results=SEARCH_RESULTS):
    """
    Pencarian web biasa yang mengembalikan snippet saja (tanpa full page).
    
    Args:
        query: Kata kunci pencarian
        max_results: Jumlah maksimum hasil
    
    Returns:
        String berisi hasil pencarian terformat (nomor, judul, snippet)
    
    Example:
        "1. Judul Artikel\n   Snippet text...\n2. ..."
    """
    results = _extract_search_results(query, max_results)

    return "\n".join(
        f"{index}. {result['title']}\n   {result['snippet']}"
        for index, result in enumerate(results, start=1)
    )


def news_search_rss(query, max_results=SEARCH_RESULTS):
    """
    Search Google News RSS for articles matching the query.
    
    Args:
        query: Search terms for news articles
        max_results: Maximum number of results to return
    
    Returns:
        List of dicts with 'title', 'url', and 'snippet' keys
    
    Note:
        Google News RSS has empty <link> tags, so we extract URLs from
        the text content that follows the link tag, or from the description.
    """
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {
            "q": query,
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        }
    )

    feed = _fetch(url)

    if not feed:
        return []

    soup = BeautifulSoup(feed, "html.parser")
    results = []

    for item in soup.find_all("item"):
        if len(results) >= max_results:
            break

        title_tag = item.find("title")
        link_tag = item.find("link")
        description_tag = item.find("description")
        guid_tag = item.find("guid")

        if not title_tag:
            continue

        title = title_tag.get_text(" ", strip=True)
        
        # Google News RSS has empty <link/> tags
        # URL is in the text after link tag, or in guid, or in description href
        link = ""
        if link_tag and link_tag.next_sibling:
            sibling_text = str(link_tag.next_sibling).strip()
            if sibling_text.startswith("http"):
                link = sibling_text
        
        if not link and guid_tag:
            guid_text = guid_tag.get_text(strip=True)
            if guid_text.startswith("http"):
                link = guid_text
            elif guid_text.startswith("CB"):
                # Google News internal ID, construct URL
                link = f"https://news.google.com/rss/articles/{guid_text}"
        
        if not link and description_tag:
            # Extract URL from description's href attribute
            desc_soup = BeautifulSoup(description_tag.get_text(), "html.parser")
            a_tag = desc_soup.find("a")
            if a_tag and a_tag.get("href"):
                link = a_tag["href"]

        snippet = (
            description_tag.get_text(" ", strip=True)
            if description_tag
            else ""
        )

        if title and link:
            results.append(
                {
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                }
            )

    return results


def _collect_full_pages(
    results,
    max_results,
    chars_per_page,
    min_chars,
):
    """
    Mengambil konten full dari halaman-hasil pencarian.
    
    Args:
        results: List of dict dengan keys 'title', 'url', 'snippet'
        max_results: Jumlah maksimum halaman yang diambil
        chars_per_page: Maksimum karakter per halaman
        min_chars: Minimum karakter agar halaman dianggap valid
    
    Returns:
        String berisi konten halaman terformat, dipisahkan oleh "---"
    
    Note:
        Jika halaman terlalu pendek (< min_chars), akan menggunakan snippet sebagai fallback.
    """
    parts = []

    for result in results:
        if len(parts) >= max_results:
            break

        page_text = fetch_page_text(
            result["url"],
            max_chars=chars_per_page,
        )

        if len(page_text) < min_chars:
            page_text = (
                result["snippet"]
                if len(result["snippet"]) >= min_chars
                else ""
            )

        if not page_text:
            continue

        parts.append(
            f"Sumber {len(parts) + 1}: {result['title']}\n"
            f"URL: {result['url']}\n"
            f"Ringkasan hasil pencarian:\n{result['snippet']}\n\n"
            f"Isi halaman:\n{page_text}\n"
        )

    return "\n---\n".join(parts)


def web_search_full_pages(
    query,
    max_results=3,
    chars_per_page=5000,
    min_chars=300,
):
    """
    Pencarian web umum dengan mengambil konten full halaman.
    
    Args:
        query: Kata kunci pencarian
        max_results: Jumlah maksimum halaman (default 3)
        chars_per_page: Maksimum karakter per halaman (default 5000)
        min_chars: Minimum karakter agar valid (default 300)
    
    Returns:
        String berisi konten halaman dari hasil pencarian
    
    Flow:
        1. Cari di Bing dengan query
        2. Ambil konten full dari halaman-halaman hasil
        3. Return konten untuk AI
    """
    results = _extract_search_results(
        query,
        max_results=max_results * 2,
    )

    return _collect_full_pages(
        results,
        max_results,
        chars_per_page,
        min_chars,
    )


def news_full_pages(
    query,
    max_results=3,
    chars_per_page=5000,
    min_chars=300,
):
    """
    Pencarian berita dengan mengambil konten full dari artikel.
    
    Args:
        query: Kata kunci pencarian berita
        max_results: Jumlah maksimum artikel (default 3)
        chars_per_page: Maksimum karakter per artikel (default 5000)
        min_chars: Minimum karakter agar valid (default 300)
    
    Returns:
        String berisi konten artikel berita
    
    Flow:
        1. Cari di Google News RSS
        2. Ambil konten full dari artikel-artikel
        3. Return konten untuk AI
    """
    results = news_search_rss(
        query,
        max_results=max_results * 2,
    )

    return _collect_full_pages(
        results,
        max_results,
        chars_per_page,
        min_chars,
    )


def is_uncertain(text):
    """
    Cek apakah text menunjukkan AI ragu-ragu atau tidak yakin.
    
    Args:
        text: Response dari AI yang akan dicek
    
    Returns:
        True jika AI terlihat ragu/tidak yakin, False jika tidak
    
    Note:
        Jika True, akan trigger web search untuk mendapat info lebih akurat.
    """
    return bool(re.search("|".join(UNCERTAINTY_PATTERNS), text, re.I))


def needs_current_info(text):
    """
    Cek apakah pertanyaan membutuhkan informasi terkini/real-time.
    
    Args:
        text: Input dari user
    
    Returns:
        True jika pertanyaan tentang info terkini (now, today, latest, dll)
    """
    return bool(re.search("|".join(CURRENT_INFO_PATTERNS), text, re.I))


def search_requested(text):
    """
    Cek apakah user secara eksplisit meminta untuk mencari sesuatu.
    
    Args:
        text: Input dari user
    
    Returns:
        True jika ada kata search, browse, find, look up, dll
    """
    return bool(re.search("|".join(SEARCH_REQUEST_PATTERNS), text, re.I))


def needs_general_web(text):
    """
    Cek apakah pertanyaan membutuhkan pencarian web umum.
    
    Args:
        text: Input dari user
    
    Returns:
        True jika pertanyaan cocok untuk web search umum
    """
    return bool(re.search("|".join(WEB_ROUTE_PATTERNS), text, re.I))


def needs_news(text):
    """
    Cek apakah pertanyaan membutuhkan pencarian berita/news.
    
    Args:
        text: Input dari user
    
    Returns:
        True jika pertanyaan tentang berita (news, breaking, latest, dll)
    """
    return bool(re.search("|".join(NEWS_ROUTE_PATTERNS), text, re.I))


def clean_query(query, extra_words=None):
    """
    Membersihkan query dari kata-kata tidak perlu untuk mendapat query inti.
    
    Args:
        query: Query asli dari user
        extra_words: List kata tambahan yang akan dihapus (opsional)
    
    Returns:
        String query yang sudah dibersihkan
    
    Example:
        "can you please search about indonesia" -> "indonesia"
    
    Note:
        - Menghapus kata seperti: please, can, you, search, about, dll
        - Menghapus "wikipedia" dan "browser"
        - Jika hasil kosong, return query asli
    """
    words = [
        word.strip(".,?;:!()'\"")
        for word in query.lower()
        .replace("wikipedia", " ")
        .replace("browser", " ")
        .split()
    ]

    stopwords = CLEAN_WORDS + (extra_words or [])

    kept_words = [
        word for word in words
        if word and word not in stopwords
    ]

    return " ".join(kept_words) or query

def is_followup(text):
    """
    Cek apakah text adalah follow-up question dari query sebelumnya.
    
    Args:
        text: Input dari user
    
    Returns:
        True jika ini pertanyaan lanjutan, False jika query baru
    
    Note:
        Follow-up = pertanyaan singkat yang terkait dengan query sebelumnya.
        Contoh: "and the price?" setelah tanya tentang stock
    """
    if _last_query and re.search(
        "|".join(FOLLOWUP_PATTERNS),
        text,
        re.I,
    ):
        return True

    cleaned = [
        word for word in clean_query(text).split()
        if word
    ]

    if len(cleaned) >= 3:
        return False

    return not (
        needs_current_info(text)
        or search_requested(text)
        or finance_index(text)
    )


def search_for_context(user_content, assistant_content):
    """
    Fungsi utama untuk menentukan jenis pencarian dan mengambil konten.
    
    Args:
        user_content: Input/pertanyaan dari user
        assistant_content: Response terakhir dari AI
    
    Returns:
        String berisi konten hasil pencarian (web/news/finance)
        atau empty string jika tidak perlu search
    
    Flow:
        1. Cek apakah perlu search (AI ragu, butuh info terkini, atau user minta search)
        2. Tentukan route: finance (stock/IHSG) -> news -> general web
        3. Fetch konten dari sumber yang sesuai
        4. Jika gagal, coba fallback ke sumber lain
        5. Return konten untuk AI
    
    Note:
        - Menyimpan _last_query dan _last_route untuk follow-up questions
        - Jika OPEN_BROWSER=True, browser akan otomatis terbuka
        - Ada fallback mechanism: Yahoo -> Google -> snippets
    """
    global _last_query, _last_route

    followup = is_followup(user_content) and _last_query
    topic = user_content if not followup else _last_query

    need_search = (
        is_uncertain(assistant_content)
        or needs_current_info(user_content)
        or search_requested(user_content)
    )

    if followup:
        need_search = True

    if not need_search:
        return ""

    search_query = clean_query(topic)
    index = finance_index(topic)

    if index:
        symbol, name = index
        print(f"[Fetching {name} ({symbol}) from Yahoo Finance]")

        search_url = (
            "https://finance.yahoo.com/quote/"
            + urllib.parse.quote(symbol)
        )
        search_function = lambda query: finance_search(symbol)
        _last_route = "finance"

    elif needs_news(topic):
        news_query = clean_query(
            topic,
            extra_words=NEWS_FILLER_WORDS,
        )

        print("[Reading news pages for:", news_query, "]")

        search_url = (
            "https://news.google.com/search?"
            + urllib.parse.urlencode({"q": news_query})
        )
        search_function = lambda query: news_full_pages(news_query)
        _last_route = "news"

    else:
        print("[Reading full web pages for:", search_query, "]")

        search_url = (
            "https://www.google.com/search?"
            + urllib.parse.urlencode({"q": search_query})
        )
        search_function = web_search_full_pages
        _last_route = "web"

    _last_query = search_query

    if OPEN_BROWSER:
        webbrowser.open(search_url)

    try:
        search_text = search_function(search_query)
    except Exception:
        search_text = ""

    if index and not search_text:
        print("[Yahoo unavailable, trying Google instead]")
        search_text = web_engine_search(search_query)

    if _last_route == "news" and not search_text:
        print("[News read failed, trying general web pages]")
        search_text = web_search_full_pages(search_query)

    if _last_route in ("news", "web") and not search_text:
        print("[Full page read failed, falling back to snippets]")
        search_text = web_engine_search(search_query)

    return search_text
