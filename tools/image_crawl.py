from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from config import AppConfig


class _ImageCrawlerParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.current_heading = ""
        self.candidates: list[dict[str, str]] = []
        self._capture_heading = False
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): (v or "").strip() for k, v in attrs}
        lowered = tag.lower()
        if lowered in {"h1", "h2", "h3"}:
            self._capture_heading = True
            self._heading_parts = []
            return

        if lowered != "img":
            return

        src = attrs_map.get("src") or attrs_map.get("data-src") or attrs_map.get("data-original")
        if not src:
            return
        src = urljoin(self.base_url, src)
        if not src.startswith(("http://", "https://")):
            return

        alt = attrs_map.get("alt", "")
        title = attrs_map.get("title", "")
        caption = alt or title
        section = self.current_heading
        self.candidates.append(
            {
                "imageUrl": src,
                "alt": alt,
                "caption": caption,
                "section": section,
            }
        )

    def handle_data(self, data: str) -> None:
        if self._capture_heading:
            self._heading_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"h1", "h2", "h3"} and self._capture_heading:
            heading = html.unescape("".join(self._heading_parts)).strip()
            heading = re.sub(r"\s+", " ", heading)
            if heading:
                self.current_heading = heading[:120]
            self._capture_heading = False
            self._heading_parts = []


def _coerce_int(raw: Any, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    if min_value is not None and value < min_value:
        value = min_value
    if max_value is not None and value > max_value:
        value = max_value
    return value


def _domain(raw_url: str) -> str:
    try:
        return urlparse(raw_url).netloc.strip()
    except Exception:
        return ""


def _format(items: list[dict[str, Any]], url: str) -> str:
    if not items:
        return f"No candidate images found from page: {url}"
    lines = [f"Image crawl results from: {url}", f"Found {len(items)} image candidates (showing top {min(8, len(items))})."]
    for idx, item in enumerate(items[:8], start=1):
        lines.append(
            f"{idx}. Image: {item.get('imageUrl')}\n"
            f"Alt/Caption: {item.get('caption') or 'N/A'}\n"
            f"Section: {item.get('section') or 'N/A'}"
        )
    return "\n\n".join(lines)


def run_image_crawl(args: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    del config
    url = str(args.get("url") or "").strip()
    if not url:
        return {
            "status": "error",
            "http_status": 400,
            "text": "image_crawl error: url is required.",
            "payload": {"error": "url is required"},
        }
    if not url.startswith(("http://", "https://")):
        return {
            "status": "error",
            "http_status": 400,
            "text": "image_crawl error: url must be http(s).",
            "payload": {"error": "url must be http(s)"},
        }

    limit = _coerce_int(args.get("limit"), 20, min_value=1, max_value=100)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DemoImageCrawler/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
    except requests.RequestException as exc:
        return {
            "status": "error",
            "http_status": 503,
            "text": f"image_crawl error: request failed: {exc}",
            "payload": {"error": str(exc)},
        }

    http_status = response.status_code
    if http_status >= 400:
        return {
            "status": "error",
            "http_status": http_status,
            "text": f"image_crawl error: page returned {http_status}.",
            "payload": {"error": f"http {http_status}"},
        }

    content_type = str(response.headers.get("Content-Type") or "").lower()
    if "html" not in content_type:
        return {
            "status": "error",
            "http_status": 415,
            "text": "image_crawl error: target is not an HTML page.",
            "payload": {"error": "non-html response", "contentType": content_type},
        }

    parser = _ImageCrawlerParser(url)
    parser.feed(response.text)

    dedupe: set[str] = set()
    items: list[dict[str, Any]] = []
    for item in parser.candidates:
        image_url = str(item.get("imageUrl") or "").strip()
        if not image_url or image_url in dedupe:
            continue
        dedupe.add(image_url)
        items.append(
            {
                "imageUrl": image_url,
                "alt": str(item.get("alt") or "").strip(),
                "caption": str(item.get("caption") or "").strip(),
                "section": str(item.get("section") or "").strip(),
                "sourcePage": url,
                "domain": _domain(url),
            }
        )
        if len(items) >= limit:
            break

    return {
        "status": "ok",
        "http_status": 200,
        "text": _format(items, url),
        "payload": {
            "items": items,
            "metrics": {"total": len(items)},
            "sourceEvidence": [url],
        },
    }
