from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from config import AppConfig


EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
}


def _sanitize_name(raw: str) -> str:
    text = re.sub(r"[^\w\-\.]+", "_", raw.strip())
    text = text.strip("._")
    return text[:80] or "image"


def _guess_extension(image_url: str, content_type: str) -> str:
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime in EXT_BY_MIME:
        return EXT_BY_MIME[mime]
    suffix = Path(urlparse(image_url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".bin"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_image_fetch_save(args: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    del config
    image_url = str(args.get("imageUrl") or "").strip()
    if not image_url:
        return {
            "status": "error",
            "http_status": 400,
            "text": "image_fetch_save error: imageUrl is required.",
            "payload": {"error": "imageUrl is required"},
        }
    if not image_url.startswith(("http://", "https://")):
        return {
            "status": "error",
            "http_status": 400,
            "text": "image_fetch_save error: imageUrl must be http(s).",
            "payload": {"error": "imageUrl must be http(s)"},
        }

    request_id = _sanitize_name(str(args.get("requestId") or "").strip() or "adhoc")
    name_hint = _sanitize_name(str(args.get("nameHint") or "").strip() or "")
    source_page = str(args.get("sourcePage") or "").strip()

    try:
        response = requests.get(
            image_url,
            stream=True,
            timeout=25,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DemoImageFetcher/1.0)"},
        )
    except requests.RequestException as exc:
        return {
            "status": "error",
            "http_status": 503,
            "text": f"image_fetch_save error: request failed: {exc}",
            "payload": {"error": str(exc)},
        }

    http_status = response.status_code
    if http_status >= 400:
        return {
            "status": "error",
            "http_status": http_status,
            "text": f"image_fetch_save error: image URL returned {http_status}.",
            "payload": {"error": f"http {http_status}"},
        }

    content_type = str(response.headers.get("Content-Type") or "").strip()
    if not content_type.lower().startswith("image/"):
        return {
            "status": "error",
            "http_status": 415,
            "text": f"image_fetch_save error: unsupported content-type {content_type or 'unknown'}.",
            "payload": {"error": "non-image content", "contentType": content_type},
        }

    chunks: list[bytes] = []
    total = 0
    max_bytes = 20 * 1024 * 1024
    for chunk in response.iter_content(chunk_size=8192):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            return {
                "status": "error",
                "http_status": 413,
                "text": "image_fetch_save error: image exceeds 20MB limit.",
                "payload": {"error": "image too large"},
            }
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        return {
            "status": "error",
            "http_status": 502,
            "text": "image_fetch_save error: downloaded empty file.",
            "payload": {"error": "empty content"},
        }

    digest = hashlib.sha256(content).hexdigest()
    ext = _guess_extension(image_url, content_type)
    base_name = name_hint or Path(urlparse(image_url).path).stem or "image"
    safe_name = _sanitize_name(base_name)
    file_name = f"{safe_name}_{digest[:12]}{ext}"

    save_dir = _project_root() / "pic" / request_id
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / file_name
    save_path.write_bytes(content)

    relative_path = save_path.relative_to(_project_root()).as_posix()
    payload = {
        "requestId": request_id,
        "imageUrl": image_url,
        "sourcePage": source_page,
        "savedPath": relative_path,
        "publicUrl": f"/{relative_path}",
        "mime": content_type.split(";")[0].strip().lower(),
        "size": len(content),
        "sha256": digest,
        "fileName": file_name,
    }

    text = (
        f"Saved image successfully.\n"
        f"Path: {payload['savedPath']}\n"
        f"Mime: {payload['mime']}\n"
        f"Size: {payload['size']} bytes\n"
        f"SHA256: {payload['sha256']}\n"
        f"Source: {source_page or 'N/A'}"
    )
    return {
        "status": "ok",
        "http_status": 200,
        "text": text,
        "payload": payload,
    }
