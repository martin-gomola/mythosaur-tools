from __future__ import annotations

import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .common import ToolDef, err, now_ms, ok, parse_int, resolve_under_workspace


def _safe_headers(raw: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (raw or {}).items():
        k = str(key).strip()
        v = str(value).strip()
        if not k:
            continue
        if k.lower() in {"authorization", "cookie"}:
            continue
        out[k] = v
    return out


def _fetch_core(url: str, headers: dict, timeout: int, max_bytes: int) -> tuple[int, dict, bytes, str]:
    with requests.get(url, headers=headers, timeout=timeout, stream=True) as resp:
        content = bytearray()
        for chunk in resp.iter_content(chunk_size=8192):
            if not chunk:
                continue
            content.extend(chunk)
            if len(content) > max_bytes:
                raise ValueError(f"response exceeds max_bytes={max_bytes}")
        return resp.status_code, dict(resp.headers), bytes(content), resp.url


def _fetch(arguments: dict) -> dict:
    started = now_ms()
    url = (arguments.get("url") or "").strip()
    if not url:
        return err("fetch", "missing_url", "url is required", "fetch", started)
    timeout = parse_int(arguments.get("timeout"), default=12, minimum=1, maximum=60)
    max_bytes = parse_int(arguments.get("max_bytes"), default=500_000, minimum=1024, maximum=20_000_000)
    headers = _safe_headers(arguments.get("headers") or {})

    try:
        status, resp_headers, raw, final_url = _fetch_core(url, headers, timeout, max_bytes)
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        return err("fetch", "fetch_failed", str(exc), "fetch", started)

    return ok(
        "fetch",
        {
            "url": final_url,
            "status_code": status,
            "headers": resp_headers,
            "body": text,
        },
        "fetch",
        started,
    )


def _fetch_json(arguments: dict) -> dict:
    started = now_ms()
    url = (arguments.get("url") or "").strip()
    if not url:
        return err("fetch_json", "missing_url", "url is required", "fetch", started)
    timeout = parse_int(arguments.get("timeout"), default=12, minimum=1, maximum=60)
    max_bytes = parse_int(arguments.get("max_bytes"), default=1_000_000, minimum=1024, maximum=20_000_000)
    headers = _safe_headers(arguments.get("headers") or {})

    try:
        status, resp_headers, raw, final_url = _fetch_core(url, headers, timeout, max_bytes)
        payload = requests.models.complexjson.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        return err("fetch_json", "fetch_failed", str(exc), "fetch", started)

    return ok(
        "fetch_json",
        {
            "url": final_url,
            "status_code": status,
            "headers": resp_headers,
            "json": payload,
        },
        "fetch",
        started,
    )


def _fetch_html(arguments: dict) -> dict:
    started = now_ms()
    url = (arguments.get("url") or "").strip()
    if not url:
        return err("fetch_html", "missing_url", "url is required", "fetch", started)
    selector = (arguments.get("selector") or "").strip()
    timeout = parse_int(arguments.get("timeout"), default=12, minimum=1, maximum=60)
    max_bytes = parse_int(arguments.get("max_bytes"), default=1_000_000, minimum=1024, maximum=20_000_000)
    headers = _safe_headers(arguments.get("headers") or {})

    try:
        status, resp_headers, raw, final_url = _fetch_core(url, headers, timeout, max_bytes)
        html = raw.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        if selector:
            nodes = soup.select(selector)
            extracted = [n.get_text(" ", strip=True) for n in nodes]
        else:
            extracted = [soup.get_text(" ", strip=True)]
    except Exception as exc:
        return err("fetch_html", "fetch_failed", str(exc), "fetch", started)

    return ok(
        "fetch_html",
        {
            "url": final_url,
            "status_code": status,
            "headers": resp_headers,
            "selector": selector,
            "text": extracted,
        },
        "fetch",
        started,
    )


def _download(arguments: dict) -> dict:
    started = now_ms()
    url = (arguments.get("url") or "").strip()
    path = (arguments.get("path") or "").strip()
    overwrite = bool(arguments.get("overwrite", False))
    timeout = parse_int(arguments.get("timeout"), default=20, minimum=1, maximum=120)
    max_bytes = parse_int(arguments.get("max_bytes"), default=20_000_000, minimum=1024, maximum=100_000_000)

    if not url or not path:
        return err("download", "missing_input", "url and path are required", "fetch", started)

    try:
        dst = resolve_under_workspace(path)
    except Exception as exc:
        return err("download", "invalid_path", str(exc), "fetch", started)

    if dst.exists() and not overwrite:
        return err("download", "exists", f"destination already exists: {dst}", "fetch", started)

    headers = _safe_headers(arguments.get("headers") or {})

    try:
        status, resp_headers, raw, final_url = _fetch_core(url, headers, timeout, max_bytes)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(raw)
    except Exception as exc:
        return err("download", "download_failed", str(exc), "fetch", started)

    return ok(
        "download",
        {
            "url": final_url,
            "status_code": status,
            "headers": resp_headers,
            "path": str(dst),
            "bytes": len(raw),
        },
        "fetch",
        started,
    )


def get_tools() -> list[ToolDef]:
    common = {
        "url": {"type": "string"},
        "headers": {"type": "object", "additionalProperties": {"type": "string"}},
        "timeout": {"type": "integer", "minimum": 1, "maximum": 120},
        "max_bytes": {"type": "integer", "minimum": 1024},
    }

    return [
        ToolDef(
            name="fetch",
            plugin_id="mythosaur.fetch",
            description="Fetch URL and return text body + metadata.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": common,
                "required": ["url"],
            },
            handler=_fetch,
            aliases=["osaurus.fetch"],
        ),
        ToolDef(
            name="fetch_json",
            plugin_id="mythosaur.fetch",
            description="Fetch JSON from URL.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": common,
                "required": ["url"],
            },
            handler=_fetch_json,
            aliases=["osaurus.fetch_json"],
        ),
        ToolDef(
            name="fetch_html",
            plugin_id="mythosaur.fetch",
            description="Fetch HTML and extract text via optional CSS selector.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **common,
                    "selector": {"type": "string"},
                },
                "required": ["url"],
            },
            handler=_fetch_html,
            aliases=["osaurus.fetch_html"],
        ),
        ToolDef(
            name="download",
            plugin_id="mythosaur.fetch",
            description="Download URL content into workspace path.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **common,
                    "path": {"type": "string"},
                    "overwrite": {"type": "boolean", "default": False},
                },
                "required": ["url", "path"],
            },
            handler=_download,
            aliases=["osaurus.download"],
        ),
    ]
