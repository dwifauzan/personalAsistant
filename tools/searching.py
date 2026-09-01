import asyncio
import html
import urllib.parse
import warnings

from bs4 import XMLParsedAsHTMLWarning
from bs4 import BeautifulSoup
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from tools.http_client import fetch
from tools.html_utils import extract_text
from config import MAX_CONCURRENT_FETCHES


async def _extract_search_results_bing(query: str, max_results: int = 5) -> list[dict]:
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({
        "q": query,
        "count": max_results,
    })

    page_html = await fetch(url)
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

        if not actual_url.startswith("http"):
            continue

        if actual_url in seen_links:
            continue

        title = link_tag.get_text(" ", strip=True)
        if not title:
            continue

        seen_links.add(actual_url)

        snippet_tag = result_li.find("p") or result_li.find("div", class_="b_caption")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        results.append({
            "title": title,
            "url": actual_url,
            "snippet": snippet,
        })

    return results


def _decode_bing_url(href: str) -> str:
    if "bing.com/ck" not in href:
        return href

    href = html.unescape(href)
    parsed = urllib.parse.urlparse(href)
    params = urllib.parse.parse_qs(parsed.query)

    if "u" in params:
        encoded_url = params["u"][0]
        if encoded_url.startswith("a1"):
            try:
                import base64
                decoded_bytes = base64.b64decode(encoded_url[2:])
                return decoded_bytes.decode("utf-8")
            except Exception:
                pass

    return href


async def _fetch_pages_parallel(results: list[dict], max_chars: int = 5000) -> list[str]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def fetch_one(result: dict) -> str:
        async with semaphore:
            page_html = await fetch(result["url"])
            text = extract_text(page_html, max_chars=max_chars)
            if len(text) < 300:
                return result.get("snippet", "")
            return text

    tasks = [fetch_one(r) for r in results]
    return await asyncio.gather(*tasks)


async def web_search_handler(query: str, max_results: int = 3) -> str:
    print(f"[web_search] Searching Bing for: {query}")
    results = await _extract_search_results_bing(query, max_results=max_results * 2)

    if not results:
        print("[web_search] No results found")
        return "No search results found."

    print(f"[web_search] Found {len(results)} results, fetching top {min(max_results, len(results))} pages")
    page_texts = await _fetch_pages_parallel(results[:max_results])

    parts = []
    for i, (result, text) in enumerate(zip(results[:max_results], page_texts), 1):
        if text:
            print(f"[web_search] Source {i}: {result['title'][:50]}...")
            parts.append(
                f"Source {i}: {result['title']}\n"
                f"URL: {result['url']}\n"
                f"Content:\n{text}\n"
            )

    if parts:
        print(f"[web_search] Successfully retrieved {len(parts)} sources")
    else:
        print("[web_search] Could not retrieve any page content")

    return "\n---\n".join(parts) if parts else "Could not retrieve page content."


async def news_search_handler(query: str, max_results: int = 3) -> str:
    print(f"[news_search] Searching Google News for: {query}")
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })

    feed = await fetch(url)
    if not feed:
        print("[news_search] Failed to fetch RSS feed")
        return "No news results found."

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(feed, "html.parser")
    results = []

    for item in soup.find_all("item"):
        if len(results) >= max_results:
            break

        title_tag = item.find("title")
        if not title_tag:
            continue

        title = title_tag.get_text(" ", strip=True)

        link = ""
        link_tag = item.find("link")
        if link_tag:
            link = link_tag.get_text(strip=True)
            if not link.startswith("http"):
                link = ""

        if not link:
            guid_tag = item.find("guid")
            if guid_tag:
                guid_text = guid_tag.get_text(strip=True)
                if guid_text.startswith("http"):
                    link = guid_text
                elif guid_text.startswith("CB"):
                    link = "https://news.google.com/rss/" + guid_text

        description_tag = item.find("description")

        if not link and description_tag:
            desc_soup = BeautifulSoup(str(description_tag), "html.parser")
            a_tag = desc_soup.find("a")
            if a_tag and a_tag.get("href"):
                link = a_tag["href"]

        snippet = description_tag.get_text(" ", strip=True) if description_tag else ""

        if title:
            results.append({
                "title": title,
                "url": link,
                "snippet": snippet,
            })

    if not results:
        print("[news_search] No news articles found")
        return "No news articles found."

    print(f"[news_search] Found {len(results)} articles, fetching full content")
    page_texts = await _fetch_pages_parallel(results)

    parts = []
    for i, (result, text) in enumerate(zip(results, page_texts), 1):
        content = text if text else result.get("snippet", "")
        if content:
            print(f"[news_search] Article {i}: {result['title'][:50]}...")
            parts.append(
                f"News {i}: {result['title']}\n"
                f"URL: {result['url']}\n"
                f"Content:\n{content}\n"
            )

    if parts:
        print(f"[news_search] Successfully retrieved {len(parts)} articles")
    else:
        print("[news_search] Could not retrieve any article content")

    return "\n---\n".join(parts) if parts else "Could not retrieve news content."


async def browse_url_handler(url: str, max_chars: int = 5000) -> str:
    print(f"[browse_url] Fetching: {url}")
    page_html = await fetch(url)
    if not page_html:
        print(f"[browse_url] Failed to fetch URL")
        return f"Could not fetch URL: {url}"

    text = extract_text(page_html, max_chars=max_chars)
    if not text:
        print(f"[browse_url] No readable content found")
        return f"No readable content found at: {url}"

    print(f"[browse_url] Extracted {len(text)} characters")
    return f"Content from {url}:\n{text}"
