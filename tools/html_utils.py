import re

from bs4 import BeautifulSoup


def extract_text(html: str, max_chars: int = 6000) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "noscript", "form", "iframe", "svg", "button"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()

    return text[:max_chars]
