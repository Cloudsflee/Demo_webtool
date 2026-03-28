from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import requests

from config import AppConfig


DATA_RANGE_TO_TBS = {
    "past_hour": "qdr:h",
    "past_day": "qdr:d",
    "past_week": "qdr:w",
    "past_month": "qdr:m",
    "past_year": "qdr:y",
}


def _map_serper_error(status_code: int) -> str:
    mapping = {
        401: "invalid api key",
        402: "insufficient credits",
        403: "forbidden",
        429: "rate limit exceeded",
    }
    if status_code in mapping:
        return mapping[status_code]
    if status_code >= 500:
        return "server error"
    return "unexpected serper error"


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


def _domain_from_url(raw_url: str) -> str:
    try:
        return urlparse(raw_url).netloc.strip()
    except Exception:
        return ""


def _normalize_items(raw_items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_items[:limit], start=1):
        image_url = str(row.get("imageUrl") or "").strip()
        if not image_url:
            continue
        page_url = str(row.get("link") or "").strip()
        domain = str(row.get("source") or "").strip() or _domain_from_url(page_url) or _domain_from_url(image_url)
        items.append(
            {
                "imageUrl": image_url,
                "title": str(row.get("title") or "").strip() or "Untitled image",
                "source": domain,
                "domain": domain,
                "link": page_url,
                "thumbnail": str(row.get("thumbnailUrl") or "").strip(),
                "position": idx,
            }
        )
    return items


def _format_text(query: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return f"No image results found for query: {query}"
    lines = [f"Image search results for: {query}", f"Found {len(items)} images (showing top {min(8, len(items))})."]
    for item in items[:8]:
        lines.append(
            f"{item['position']}. {item['title']}\n"
            f"Image: {item['imageUrl']}\n"
            f"Source: {item['source'] or 'unknown'}\n"
            f"Page: {item['link'] or 'N/A'}"
        )
    return "\n\n".join(lines)


def run_image_search(args: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return {
            "status": "error",
            "http_status": 400,
            "text": "image_search error: query is required.",
            "payload": {"error": "query is required"},
        }

    if not config.serper_api_key:
        return {
            "status": "error",
            "http_status": 400,
            "text": "image_search error: missing SERPER_API_KEY.",
            "payload": {"error": "missing SERPER_API_KEY"},
        }

    limit = _coerce_int(args.get("limit"), 10, min_value=1, max_value=20)
    body: dict[str, Any] = {
        "q": query,
        "type": "images",
        "gl": str(args.get("gl") or "us").strip() or "us",
        "hl": str(args.get("hl") or "en").strip() or "en",
        "num": limit,
    }

    time_range = str(args.get("timeRange") or "").strip()
    mapped_tbs = DATA_RANGE_TO_TBS.get(time_range)
    if mapped_tbs:
        body["tbs"] = mapped_tbs

    headers = {
        "X-API-KEY": config.serper_api_key,
        "Content-Type": "application/json",
    }
    url = f"{config.serper_base_url.rstrip('/')}/search"

    start = time.perf_counter()
    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return {
            "status": "error",
            "http_status": 503,
            "text": f"image_search error: request failed: {exc}",
            "payload": {"error": str(exc)},
        }

    http_status = response.status_code
    if http_status >= 400:
        mapped_error = _map_serper_error(http_status)
        return {
            "status": "error",
            "http_status": http_status,
            "text": f"image_search error: Serper returned {http_status} ({mapped_error}).",
            "payload": {"error": mapped_error, "response_text": response.text},
        }

    try:
        payload = response.json()
    except ValueError:
        return {
            "status": "error",
            "http_status": http_status,
            "text": "image_search error: invalid JSON response from Serper.",
            "payload": {"error": "invalid JSON response"},
        }

    raw_items = payload.get("images") or []
    if not isinstance(raw_items, list):
        raw_items = []
    items = _normalize_items(raw_items, limit)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    source_evidence = [item["link"] for item in items if item.get("link")]
    result_payload = {
        "items": items,
        "sourceEvidence": source_evidence,
        "metrics": {
            "total": len(items),
            "raw_total": len(raw_items),
            "filtered": max(len(raw_items) - len(items), 0),
            "elapsedMs": elapsed_ms,
        },
    }
    return {
        "status": "ok",
        "http_status": http_status,
        "text": _format_text(query, items),
        "payload": result_payload,
    }
