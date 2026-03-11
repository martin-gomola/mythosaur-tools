from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def clean_text_chunks(chunks: list[str]) -> str:
    cleaned: list[str] = []
    for chunk in chunks:
        text = re.sub(r"\s+", " ", str(chunk or "")).strip()
        if text:
            cleaned.append(text)
    return "\n\n".join(cleaned)


def clip_text(text: str, *, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    clipped = text[:max_chars].rstrip()
    last_space = clipped.rfind(" ")
    if last_space >= max_chars // 2:
        clipped = clipped[:last_space].rstrip()
    return clipped, True


def select_html_nodes(soup: BeautifulSoup, selector: str) -> list:
    if selector:
        return list(soup.select(selector))
    for preferred in ("article", "main", "[role='main']"):
        nodes = soup.select(preferred)
        if nodes:
            return list(nodes)
    if soup.body is not None:
        return [soup.body]
    return [soup]


def canonical_url(soup: BeautifulSoup, final_url: str) -> str:
    canonical = soup.find("link", rel=lambda value: value and "canonical" in str(value).lower())
    href = str(canonical.get("href") or "").strip() if canonical else ""
    return urljoin(final_url, href) if href else final_url


def extract_html_content(
    html: str,
    *,
    final_url: str,
    selector: str,
    max_chars: int,
    source_type: str = "url",
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script, style, noscript"):
        tag.decompose()

    nodes = select_html_nodes(soup, selector)
    text = clean_text_chunks([node.get_text(" ", strip=True) for node in nodes])
    text, truncated = clip_text(text, max_chars=max_chars)

    title = ""
    if soup.title is not None:
        title = re.sub(r"\s+", " ", soup.title.get_text(" ", strip=True)).strip()

    result = {
        "source_type": source_type,
        "title": title,
        "canonical_url": canonical_url(soup, final_url),
        "text": text,
        "truncated": truncated,
        "metadata": {
            "selector": selector,
            "text_length": len(text),
            "word_count": len(text.split()),
        },
    }
    if metadata:
        result["metadata"].update(metadata)
    return result
