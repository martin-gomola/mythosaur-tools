from __future__ import annotations

import json
import re
from typing import Final

import httpx
from bs4 import BeautifulSoup

from .common import JsonDict, ToolDef, err, now_ms, ok, parse_int, resolve_under_workspace, validate_fetch_url
from .content_extraction import clip_text, extract_html_content

PLUGIN_ID: Final = "mythosaur.fetch"
PLUGIN_SOURCE: Final = "fetch"
SENSITIVE_HEADERS: Final = frozenset({"authorization", "cookie"})


def _int_arg(arguments: JsonDict, key: str, *, default: int, minimum: int, maximum: int) -> int:
    return parse_int(arguments.get(key), default=default, minimum=minimum, maximum=maximum)


async def _fetch_core(
    url: str, headers: dict[str, str], timeout: int, max_bytes: int
) -> tuple[int, dict[str, str], bytes, str]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        async with client.stream("GET", url, headers=headers, timeout=timeout) as resp:
            content = bytearray()
            async for chunk in resp.aiter_bytes(chunk_size=8192):
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise ValueError(f"response exceeds max_bytes={max_bytes}")
            return resp.status_code, dict(resp.headers), bytes(content), str(resp.url)


def _safe_headers(raw: JsonDict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (raw or {}).items():
        k = str(key).strip()
        v = str(value).strip()
        if not k:
            continue
        if k.lower() in SENSITIVE_HEADERS:
            continue
        out[k] = v
    return out


def _text_content_type(headers: dict[str, str]) -> str:
    for key, value in headers.items():
        if key.lower() == "content-type":
            return str(value or "")
    return ""


def _validate_url(tool_name: str, arguments: JsonDict, started: int) -> str | JsonDict:
    """Extract and validate URL from arguments."""
    url = str(arguments.get("url") or "").strip()
    if not url:
        return err(tool_name, "missing_url", "url is required", PLUGIN_SOURCE, started)
    try:
        validate_fetch_url(url)
    except ValueError as exc:
        return err(tool_name, "blocked_url", str(exc), PLUGIN_SOURCE, started)
    return url


async def _run_fetch_request(
    tool_name: str,
    arguments: JsonDict,
    *,
    default_timeout: int,
    default_max_bytes: int,
) -> tuple[int, dict[str, str], bytes, str] | JsonDict:
    started = now_ms()
    url = _validate_url(tool_name, arguments, started)
    if isinstance(url, dict):
        return url
    timeout = _int_arg(arguments, "timeout", default=default_timeout, minimum=1, maximum=120)
    max_bytes = _int_arg(arguments, "max_bytes", default=default_max_bytes, minimum=1024, maximum=100_000_000)
    headers = _safe_headers(arguments.get("headers") or {})
    try:
        return await _fetch_core(url, headers, timeout, max_bytes)
    except Exception as exc:
        return err(tool_name, "fetch_failed", str(exc), PLUGIN_SOURCE, started)


async def _fetch(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    response = await _run_fetch_request(
        "fetch",
        arguments,
        default_timeout=12,
        default_max_bytes=500_000,
    )
    if isinstance(response, dict):
        return response
    status, resp_headers, raw, final_url = response
    text = raw.decode("utf-8", errors="replace")

    return ok(
        "fetch",
        {
            "url": final_url,
            "status_code": status,
            "headers": resp_headers,
            "body": text,
        },
        PLUGIN_SOURCE,
        started,
    )


async def _fetch_json(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    response = await _run_fetch_request(
        "fetch_json",
        arguments,
        default_timeout=12,
        default_max_bytes=1_000_000,
    )
    if isinstance(response, dict):
        return response
    status, resp_headers, raw, final_url = response
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return err("fetch_json", "invalid_json", str(exc), PLUGIN_SOURCE, started)

    return ok(
        "fetch_json",
        {
            "url": final_url,
            "status_code": status,
            "headers": resp_headers,
            "json": payload,
        },
        PLUGIN_SOURCE,
        started,
    )


async def _fetch_html(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    selector = str(arguments.get("selector") or "").strip()
    response = await _run_fetch_request(
        "fetch_html",
        arguments,
        default_timeout=12,
        default_max_bytes=1_000_000,
    )
    if isinstance(response, dict):
        return response
    status, resp_headers, raw, final_url = response
    html = raw.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    extracted = [node.get_text(" ", strip=True) for node in soup.select(selector)] if selector else [soup.get_text(" ", strip=True)]

    return ok(
        "fetch_html",
        {
            "url": final_url,
            "status_code": status,
            "headers": resp_headers,
            "selector": selector,
            "text": extracted,
        },
        PLUGIN_SOURCE,
        started,
    )


async def _extract_content(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    selector = str(arguments.get("selector") or "").strip()
    max_chars = _int_arg(arguments, "max_chars", default=12_000, minimum=500, maximum=50_000)
    response = await _run_fetch_request(
        "extract_content",
        arguments,
        default_timeout=12,
        default_max_bytes=1_000_000,
    )
    if isinstance(response, dict):
        return response
    status, resp_headers, raw, final_url = response
    content_type = _text_content_type(resp_headers).lower()
    decoded = raw.decode("utf-8", errors="replace")

    if "html" in content_type or decoded.lstrip().startswith("<"):
        extracted = extract_html_content(
            decoded,
            final_url=final_url,
            selector=selector,
            max_chars=max_chars,
        )
    else:
        text, truncated = clip_text(re.sub(r"\s+", " ", decoded).strip(), max_chars=max_chars)
        extracted = {
            "source_type": "url",
            "title": "",
            "canonical_url": final_url,
            "text": text,
            "truncated": truncated,
            "metadata": {
                "selector": selector,
                "text_length": len(text),
                "word_count": len(text.split()),
            },
        }

    metadata = extracted.get("metadata")
    if isinstance(metadata, dict):
        metadata["status_code"] = status
        metadata["content_type"] = content_type

    return ok("extract_content", extracted, PLUGIN_SOURCE, started)


async def _download(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    url_val = str(arguments.get("url") or "").strip()
    path = str(arguments.get("path") or "").strip()
    if not url_val or not path:
        return err("download", "missing_input", "url and path are required", PLUGIN_SOURCE, started)
    url = _validate_url("download", arguments, started)
    if isinstance(url, dict):
        return url
    overwrite = bool(arguments.get("overwrite", False))
    timeout = _int_arg(arguments, "timeout", default=20, minimum=1, maximum=120)
    max_bytes = _int_arg(arguments, "max_bytes", default=20_000_000, minimum=1024, maximum=100_000_000)

    try:
        dst = resolve_under_workspace(path)
    except Exception as exc:
        return err("download", "invalid_path", str(exc), PLUGIN_SOURCE, started)

    if dst.exists() and not overwrite:
        return err("download", "exists", f"destination already exists: {dst}", PLUGIN_SOURCE, started)

    headers = _safe_headers(arguments.get("headers") or {})

    try:
        status, resp_headers, raw, final_url = await _fetch_core(url, headers, timeout, max_bytes)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(raw)
    except Exception as exc:
        return err("download", "download_failed", str(exc), PLUGIN_SOURCE, started)

    return ok(
        "download",
        {
            "url": final_url,
            "status_code": status,
            "headers": resp_headers,
            "path": str(dst),
            "bytes": len(raw),
        },
        PLUGIN_SOURCE,
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
            plugin_id=PLUGIN_ID,
            description="Fetch URL and return text body + metadata.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": common,
                "required": ["url"],
            },
            handler=_fetch,
            aliases=["osaurus.fetch"],
            is_async=True,
        ),
        ToolDef(
            name="fetch_json",
            plugin_id=PLUGIN_ID,
            description="Fetch JSON from URL.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": common,
                "required": ["url"],
            },
            handler=_fetch_json,
            aliases=["osaurus.fetch_json"],
            is_async=True,
        ),
        ToolDef(
            name="fetch_html",
            plugin_id=PLUGIN_ID,
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
            is_async=True,
        ),
        ToolDef(
            name="extract_content",
            plugin_id=PLUGIN_ID,
            description="Fetch a URL and return normalized extracted content for local summarization.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **common,
                    "selector": {"type": "string"},
                    "max_chars": {"type": "integer", "minimum": 500, "maximum": 50000},
                },
                "required": ["url"],
            },
            handler=_extract_content,
            aliases=["osaurus.extract_content"],
            is_async=True,
        ),
        ToolDef(
            name="download",
            plugin_id=PLUGIN_ID,
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
            is_async=True,
        ),
    ]
