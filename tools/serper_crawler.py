from __future__ import annotations

from typing import Any

import requests

from config import AppConfig


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


def run_web_crawler(args: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    url = str(args.get("url") or "").strip()
    if not url:
        return {
            "status": "error",
            "http_status": 400,
            "text": "web_crawler error: url is required.",
            "payload": {"error": "url is required"},
        }

    if not config.serper_api_key:
        return {
            "status": "error",
            "http_status": 400,
            "text": "web_crawler error: missing SERPER_API_KEY.",
            "payload": {"error": "missing SERPER_API_KEY"},
        }

    include_markdown = args.get("includeMarkdown")
    if isinstance(include_markdown, str):
        include_markdown = include_markdown.strip().lower() in {"true", "1", "yes", "y"}
    if not isinstance(include_markdown, bool):
        include_markdown = True

    headers = {
        "X-API-KEY": config.serper_api_key,
        "Content-Type": "application/json",
    }
    body = {"url": url, "includeMarkdown": include_markdown}

    try:
        response = requests.post(
            config.serper_scrape_base_url.rstrip("/"),
            json=body,
            headers=headers,
            timeout=45,
        )
    except requests.RequestException as exc:
        return {
            "status": "error",
            "http_status": 503,
            "text": f"web_crawler error: request failed: {exc}",
            "payload": {"error": str(exc)},
        }

    http_status = response.status_code
    if http_status >= 400:
        mapped_error = _map_serper_error(http_status)
        return {
            "status": "error",
            "http_status": http_status,
            "text": f"web_crawler error: Serper returned {http_status} ({mapped_error}).",
            "payload": {"error": mapped_error, "response_text": response.text},
        }

    try:
        payload = response.json()
    except ValueError:
        return {
            "status": "error",
            "http_status": http_status,
            "text": "web_crawler error: invalid JSON response from Serper.",
            "payload": {"error": "invalid JSON response"},
        }

    markdown = str(payload.get("markdown") or "").strip()
    text = str(payload.get("text") or "").strip()
    content = markdown or text
    if not content:
        return {
            "status": "error",
            "http_status": http_status,
            "text": "web_crawler error: empty content from Serper scrape response.",
            "payload": payload,
        }

    if len(content) > 12000:
        content = f"{content[:12000]}\n\n[Content truncated]"

    return {
        "status": "ok",
        "http_status": http_status,
        "text": f"Crawled content from {url}:\n\n{content}",
        "payload": payload,
    }
