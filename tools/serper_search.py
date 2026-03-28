from __future__ import annotations

from typing import Any

import requests

from config import AppConfig


DATA_RANGE_TO_TBS = {
    "past_hour": "qdr:h",
    "past_day": "qdr:d",
    "past_week": "qdr:w",
    "past_month": "qdr:m",
    "past_year": "qdr:y",
}

SEARCH_TYPE_TO_RESULT_KEY = {
    "search": "organic",
    "images": "images",
    "videos": "videos",
    "news": "news",
    "shopping": "shopping",
    "places": "places",
    "scholar": "scholar",
    "patents": "patents",
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


def _coerce_optional_bool(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        val = raw.strip().lower()
        if val in {"true", "1", "yes", "y"}:
            return True
        if val in {"false", "0", "no", "n"}:
            return False
    return None


def _pick_first(item: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _format_result_item(item: dict[str, Any]) -> str:
    title = _pick_first(item, ["title", "question", "query"], "No title")
    link = _pick_first(item, ["link", "website", "pdfLink", "imageUrl", "thumbnailUrl"], "No link")

    summary_fields = [
        _pick_first(item, ["snippet", "description"]),
        _pick_first(item, ["source"]),
        _pick_first(item, ["date"]),
        _pick_first(item, ["price"]),
        _pick_first(item, ["address"]),
    ]
    summary = " | ".join([field for field in summary_fields if field]) or "No summary"
    return f"{title}\nURL: {link}\nSummary: {summary}"


def _format_results(results: list[dict[str, Any]], query: str, result_key: str) -> str:
    if not results:
        return f"No {result_key} results found for query: {query}"

    lines: list[str] = [f"Search results ({result_key}) for: {query}"]
    for idx, item in enumerate(results[:8], start=1):
        lines.append(f"{idx}. {_format_result_item(item)}")
    return "\n\n".join(lines)


def run_web_search(args: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return {
            "status": "error",
            "http_status": 400,
            "text": "web_search error: query is required.",
            "payload": {"error": "query is required"},
        }

    if not config.serper_api_key:
        return {
            "status": "error",
            "http_status": 400,
            "text": "web_search error: missing SERPER_API_KEY.",
            "payload": {"error": "missing SERPER_API_KEY"},
        }

    requested_search_type = str(args.get("searchType") or args.get("type") or "search").strip().lower()
    if requested_search_type not in SEARCH_TYPE_TO_RESULT_KEY:
        return {
            "status": "error",
            "http_status": 400,
            "text": f"web_search error: unsupported search type '{requested_search_type}'.",
            "payload": {"error": "unsupported search type", "supported": list(SEARCH_TYPE_TO_RESULT_KEY.keys())},
        }

    body: dict[str, Any] = {
        "q": query,
        "type": requested_search_type,
        "gl": str(args.get("gl") or "us").strip() or "us",
        "hl": str(args.get("hl") or "en").strip() or "en",
        "num": _coerce_int(args.get("num"), 10, min_value=1, max_value=100),
    }

    page = _coerce_int(args.get("page"), 0, min_value=0)
    if page > 0:
        body["page"] = page

    location = str(args.get("location") or "").strip()
    if location:
        body["location"] = location

    safe = _coerce_optional_bool(args.get("safe"))
    if safe is not None:
        body["safe"] = safe

    autocorrect = _coerce_optional_bool(args.get("autocorrect"))
    if autocorrect is not None:
        body["autocorrect"] = autocorrect

    tbs = str(args.get("tbs") or "").strip()
    if tbs:
        body["tbs"] = tbs
    else:
        data_range = args.get("dataRange")
        if isinstance(data_range, str):
            mapped_tbs = DATA_RANGE_TO_TBS.get(data_range.strip())
            if mapped_tbs:
                body["tbs"] = mapped_tbs

    headers = {
        "X-API-KEY": config.serper_api_key,
        "Content-Type": "application/json",
    }
    url = f"{config.serper_base_url.rstrip('/')}/search"

    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return {
            "status": "error",
            "http_status": 503,
            "text": f"web_search error: request failed: {exc}",
            "payload": {"error": str(exc)},
        }

    http_status = response.status_code
    if http_status >= 400:
        mapped_error = _map_serper_error(http_status)
        return {
            "status": "error",
            "http_status": http_status,
            "text": f"web_search error: Serper returned {http_status} ({mapped_error}).",
            "payload": {"error": mapped_error, "response_text": response.text},
        }

    try:
        payload = response.json()
    except ValueError:
        return {
            "status": "error",
            "http_status": http_status,
            "text": "web_search error: invalid JSON response from Serper.",
            "payload": {"error": "invalid JSON response"},
        }

    result_key = SEARCH_TYPE_TO_RESULT_KEY[requested_search_type]
    results = payload.get(result_key) or []
    formatted_text = _format_results(results, query, result_key)
    return {
        "status": "ok",
        "http_status": http_status,
        "text": formatted_text,
        "payload": payload,
    }
