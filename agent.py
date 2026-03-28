from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from openai import OpenAI

from config import AppConfig
from schemas import SYSTEM_PROMPT, TOOL_SCHEMAS
from tools.image_crawl import run_image_crawl
from tools.image_fetch_save import run_image_fetch_save
from tools.image_search import run_image_search
from tools.serper_crawler import run_web_crawler
from tools.serper_search import run_web_search


def _build_client(config: AppConfig) -> OpenAI:
    return OpenAI(
        api_key=config.llm_gateway_token or "missing-token",
        base_url=config.llm_base_url,
    )


def _error_text(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        try:
            text = f"{text}; body={json.dumps(body, ensure_ascii=False)}"
        except Exception:
            pass
    return text


def _is_channel_or_model_error(exc: Exception) -> bool:
    lowered = _error_text(exc).lower()
    return any(
        token in lowered
        for token in ("model_not_found", "no available channel", "unknown model", "invalid model")
    )


def _list_gateway_models(client: OpenAI) -> list[str]:
    try:
        resp = client.models.list()
    except Exception as exc:
        if _is_channel_or_model_error(exc):
            raise ValueError("gateway has no available model channel") from exc
        raise RuntimeError(f"failed to list models from gateway: {_error_text(exc)}") from exc

    ids: list[str] = []
    for model in getattr(resp, "data", []) or []:
        model_id = str(getattr(model, "id", "") or "").strip()
        if model_id and model_id not in ids:
            ids.append(model_id)
    return ids


def _choose_model(config: AppConfig, client: OpenAI, *, exclude: set[str] | None = None) -> str:
    configured = config.llm_model.strip()
    excluded = exclude or set()
    if configured and configured not in excluded:
        return configured

    model_ids = _list_gateway_models(client)
    for model_id in model_ids:
        if model_id not in excluded:
            return model_id
    raise ValueError("gateway has no available model channel")


def _run_tool(name: str, args: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    if name == "web_search":
        return run_web_search(args, config)
    if name == "web_crawler":
        return run_web_crawler(args, config)
    if name == "image_search":
        return run_image_search(args, config)
    if name == "image_crawl":
        return run_image_crawl(args, config)
    if name == "image_fetch_save":
        return run_image_fetch_save(args, config)
    return {
        "status": "error",
        "http_status": 400,
        "text": f"Unknown tool: {name}",
        "payload": {"error": "unknown tool"},
    }


def _safe_json_loads(raw: str) -> tuple[dict[str, Any], str | None]:
    if not raw:
        return {}, None
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, f"invalid tool arguments JSON: {exc}"
    if not isinstance(loaded, dict):
        return {}, "tool arguments must be a JSON object"
    return loaded, None


def _new_request_id() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{timestamp}_{uuid4().hex[:8]}"


def _collect_downloaded_image(tool_result: dict[str, Any]) -> dict[str, Any] | None:
    payload = tool_result.get("payload")
    if not isinstance(payload, dict):
        return None

    saved_path = str(payload.get("savedPath") or "").strip()
    if not saved_path:
        return None

    return {
        "request_id": str(payload.get("requestId") or "").strip(),
        "image_url": str(payload.get("imageUrl") or "").strip(),
        "source_page": str(payload.get("sourcePage") or "").strip(),
        "saved_path": saved_path,
        "public_url": str(payload.get("publicUrl") or "").strip(),
        "file_name": str(payload.get("fileName") or "").strip(),
        "mime": str(payload.get("mime") or "").strip(),
        "size": int(payload.get("size") or 0),
        "sha256": str(payload.get("sha256") or "").strip(),
    }


def run_agent(user_input: str, max_turns: int, debug: bool, config: AppConfig) -> dict[str, Any]:
    if not user_input.strip():
        raise ValueError("user_input is required")

    if not config.llm_gateway_host:
        raise ValueError("missing LLM_GATEWAY_HOST")
    if not config.llm_gateway_token:
        raise ValueError("missing LLM_GATEWAY_TOKEN")

    client = _build_client(config)
    selected_model = _choose_model(config, client)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    tool_calls_log: list[dict[str, Any]] = []
    debug_logs: list[dict[str, Any]] = []
    downloaded_images: list[dict[str, Any]] = []
    last_answer = ""
    tried_models: set[str] = {selected_model}
    request_id = _new_request_id()
    request_pic_dir = (Path(__file__).resolve().parent / "pic" / request_id).resolve()
    request_pic_dir.mkdir(parents=True, exist_ok=True)

    if debug:
        debug_logs.append(
            {
                "selected_model": selected_model,
                "configured_model": config.llm_model or None,
                "auto_selected": not bool(config.llm_model),
            }
        )

    for turn in range(1, max_turns + 1):
        try:
            response = client.chat.completions.create(
                model=selected_model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                parallel_tool_calls=False,
            )
        except Exception as exc:
            if config.llm_model and _is_channel_or_model_error(exc):
                selected_model = _choose_model(config, client, exclude=tried_models)
                tried_models.add(selected_model)
                if debug:
                    debug_logs.append(
                        {
                            "turn": turn,
                            "fallback_model": selected_model,
                            "reason": _error_text(exc),
                        }
                    )
                response = client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                )
            else:
                if _is_channel_or_model_error(exc):
                    raise ValueError("gateway has no available model channel") from exc
                raise RuntimeError(_error_text(exc)) from exc
        message = response.choices[0].message
        last_answer = (message.content or "").strip()

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }

        raw_tool_calls = message.tool_calls or []
        if raw_tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in raw_tool_calls
            ]

        messages.append(assistant_message)

        if debug:
            debug_logs.append(
                {
                    "turn": turn,
                    "assistant_text_length": len(assistant_message["content"]),
                    "tool_calls_count": len(raw_tool_calls),
                }
            )

        if not raw_tool_calls:
            return {
                "answer": last_answer,
                "turns": turn,
                "request_id": request_id,
                "request_pic_dir": str(request_pic_dir),
                "downloaded_images": downloaded_images,
                "tool_calls": tool_calls_log,
                "debug_logs": debug_logs if debug else [],
            }

        for tool_call in raw_tool_calls:
            tool_name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"
            args, parse_error = _safe_json_loads(raw_args)

            if parse_error:
                tool_result = {
                    "status": "error",
                    "http_status": 400,
                    "text": f"{tool_name} error: {parse_error}",
                    "payload": {"error": parse_error},
                }
            else:
                if tool_name == "image_fetch_save":
                    args.setdefault("requestId", request_id)
                tool_result = _run_tool(tool_name, args, config)

            tool_text = str(tool_result.get("text") or "").strip() or "Tool returned empty text."
            http_status = int(tool_result.get("http_status") or 500)
            status = str(tool_result.get("status") or "error")
            if tool_name == "image_fetch_save" and status == "ok":
                image_record = _collect_downloaded_image(tool_result)
                if image_record:
                    downloaded_images.append(image_record)

            tool_calls_log.append(
                {
                    "name": tool_name,
                    "args": args,
                    "status": status,
                    "http_status": http_status,
                }
            )

            if debug:
                debug_logs.append(
                    {
                        "turn": turn,
                        "tool_name": tool_name,
                        "tool_args": args,
                        "tool_http_status": http_status,
                        "tool_text_length": len(tool_text),
                    }
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": tool_text,
                }
            )

    fallback = "Reached max turns before converging. Please refine your request and try again."
    return {
        "answer": last_answer or fallback,
        "turns": max_turns,
        "request_id": request_id,
        "request_pic_dir": str(request_pic_dir),
        "downloaded_images": downloaded_images,
        "tool_calls": tool_calls_log,
        "debug_logs": debug_logs if debug else [],
    }
