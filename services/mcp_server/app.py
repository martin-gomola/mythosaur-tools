from __future__ import annotations

import collections
import json
import logging
import os
import secrets
import time
from typing import Any, Final

from fastapi import FastAPI, Header, HTTPException, Request, Response

from plugins import load_tools
from plugins.common import ToolDef, bool_env
from plugins.google_tools import google_auth_status, google_capabilities

logging.basicConfig(level=getattr(logging, (os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO))
logger = logging.getLogger(__name__)

API_VERSION: Final = "0.2.0"
MCP_PROTOCOL_VERSION: Final = "2024-11-05"
SERVICE_NAME: Final = "mythosaur-tools"
JSONRPC_VERSION: Final = "2.0"

app = FastAPI(title=SERVICE_NAME, version=API_VERSION)
TOOLS, PLUGINS_META = load_tools()
SESSIONS: dict[str, dict[str, float]] = {}
_SESSION_TTL_SEC = 3600
_RATE_WINDOW_SEC = 60
_RATE_MAX_CALLS = int(os.getenv("MYTHOSAUR_TOOLS_RATE_LIMIT", "120"))
_rate_ledger: dict[str, list[float]] = collections.defaultdict(list)
_last_cleanup_at = 0.0
_CLEANUP_INTERVAL_SEC = 300
_USAGE_LOG_EVERY = int(os.getenv("MYTHOSAUR_TOOLS_USAGE_LOG_EVERY", "5"))
_USAGE_SUMMARY_INTERVAL_SEC = int(os.getenv("MYTHOSAUR_TOOLS_USAGE_LOG_INTERVAL_SEC", "60"))
_usage_total_calls = 0
_usage_tool_counts: collections.Counter[str] = collections.Counter()
_usage_last_summary_at = 0.0

JsonDict = dict[str, Any]


def _record_tool_usage(name: str, status: str, duration_ms: int) -> None:
    global _usage_total_calls, _usage_last_summary_at

    _usage_total_calls += 1
    _usage_tool_counts[name] += 1

    now = time.time()
    due_by_count = _USAGE_LOG_EVERY > 0 and _usage_total_calls % _USAGE_LOG_EVERY == 0
    due_by_time = _USAGE_SUMMARY_INTERVAL_SEC > 0 and (now - _usage_last_summary_at) >= _USAGE_SUMMARY_INTERVAL_SEC
    if _usage_total_calls != 1 and not due_by_count and not due_by_time:
        return

    _usage_last_summary_at = now
    top_tools = ",".join(f"{tool}:{count}" for tool, count in _usage_tool_counts.most_common(3))
    logger.info(
        "mcp.usage total_calls=%s unique_tools=%s top_tools=%s last_tool=%s last_status=%s last_duration_ms=%s",
        _usage_total_calls,
        len(_usage_tool_counts),
        top_tools or "-",
        name,
        status,
        duration_ms,
    )


def _require_auth(auth_header: str | None) -> str:
    """Validate bearer token, return the token for rate-limit keying."""
    expected = (os.getenv("MYTHOSAUR_TOOLS_API_KEY") or "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="MYTHOSAUR_TOOLS_API_KEY is not configured")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return token


def _session_payload() -> dict[str, float]:
    return {"created_at": time.time()}


def _check_rate_limit(key: str) -> None:
    if _RATE_MAX_CALLS <= 0:
        return
    now = time.time()
    window = _rate_ledger[key]
    cutoff = now - _RATE_WINDOW_SEC
    _rate_ledger[key] = [ts for ts in window if ts > cutoff]
    if len(_rate_ledger[key]) >= _RATE_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded ({_RATE_MAX_CALLS} calls/{_RATE_WINDOW_SEC}s)",
        )
    _rate_ledger[key].append(now)


def _periodic_cleanup() -> None:
    global _last_cleanup_at
    now = time.time()
    if now - _last_cleanup_at < _CLEANUP_INTERVAL_SEC:
        return
    _last_cleanup_at = now

    session_cutoff = now - _SESSION_TTL_SEC
    stale_sids = [sid for sid, data in SESSIONS.items() if data.get("created_at", 0) < session_cutoff]
    for sid in stale_sids:
        SESSIONS.pop(sid, None)

    rate_cutoff = now - _RATE_WINDOW_SEC
    stale_keys = [k for k, ts_list in _rate_ledger.items() if not ts_list or ts_list[-1] < rate_cutoff]
    for k in stale_keys:
        _rate_ledger.pop(k, None)


def _response(id_value: Any, result: JsonDict | None = None, error: JsonDict | None = None) -> JsonDict:
    payload: JsonDict = {"jsonrpc": JSONRPC_VERSION, "id": id_value}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result or {}
    return payload


def _error_response(id_value: Any, code: int, message: str) -> JsonDict:
    return _response(id_value, error={"code": code, "message": message})


def _to_mcp_content(tool_result: JsonDict) -> JsonDict:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(tool_result, ensure_ascii=False),
            }
        ],
        "structuredContent": tool_result,
    }


def _iter_unique_tools(plugin_filter: set[str] | None = None) -> list[ToolDef]:
    seen: set[str] = set()
    unique_tools: list[ToolDef] = []
    for tool in TOOLS.values():
        if tool.name in seen:
            continue
        if plugin_filter and tool.plugin_id not in plugin_filter:
            continue
        seen.add(tool.name)
        unique_tools.append(tool)
    return unique_tools


def _parse_plugin_filter(raw_value: Any) -> set[str]:
    if not isinstance(raw_value, str):
        return set()
    return {plugin_id.strip() for plugin_id in raw_value.split(",") if plugin_id.strip()}


def _build_health_plugins() -> list[JsonDict]:
    searxng_url = (os.getenv("MYTHOSAUR_TOOLS_SEARXNG_URL") or "").strip()
    browser_enabled = bool_env("MYTHOSAUR_TOOLS_BROWSER_ENABLED", False)

    plugins: list[JsonDict] = []
    for plugin_meta in PLUGINS_META:
        entry: JsonDict = {
            "plugin_id": plugin_meta.plugin_id,
            "tool_count": plugin_meta.tool_count,
            "tools": plugin_meta.tool_names,
        }
        if plugin_meta.plugin_id == "mythosaur.search":
            entry["searxng_configured"] = bool(searxng_url)
        if plugin_meta.plugin_id == "mythosaur.browser":
            entry["browser_enabled"] = browser_enabled
        if plugin_meta.plugin_id == "mythosaur.google_workspace":
            entry["capabilities"] = google_capabilities()
            entry["auth"] = google_auth_status()
        plugins.append(entry)
    return plugins


def _build_schema_tools() -> list[JsonDict]:
    return sorted(
        [
            {
                "name": tool.name,
                "plugin_id": tool.plugin_id,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "aliases": tool.aliases or [],
            }
            for tool in _iter_unique_tools()
        ],
        key=lambda item: str(item["name"]),
    )


def _build_tools_list(plugin_filter: set[str]) -> list[JsonDict]:
    return sorted(
        [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "annotations": {
                    "pluginId": tool.plugin_id,
                    "aliases": tool.aliases or [],
                },
            }
            for tool in _iter_unique_tools(plugin_filter)
        ],
        key=lambda item: str(item["name"]),
    )


def _initialize_session(response: Response, requested_session_id: str | None) -> JsonDict:
    session_id = requested_session_id or secrets.token_hex(12)
    SESSIONS[session_id] = _session_payload()
    response.headers["Mcp-Session-Id"] = session_id
    logger.info("mcp.initialize sid=%s", session_id)
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "serverInfo": {"name": SERVICE_NAME, "version": API_VERSION},
        "capabilities": {"tools": {"listChanged": False}},
    }


async def _invoke_tool(tool: ToolDef, args: JsonDict, started_at: float) -> JsonDict:
    try:
        return await tool.invoke(args)
    except Exception as exc:
        logger.exception("tool execution error name=%s", tool.name)
        elapsed_ms = int((time.time() - started_at) * 1000)
        return {
            "status": "error",
            "tool": tool.name,
            "data": {},
            "error": {"code": "internal_error", "message": str(exc)},
            "meta": {"duration_ms": elapsed_ms, "source": tool.plugin_id},
        }


def _log_tool_call(name: str, tool_result: JsonDict, started_at: float) -> int:
    elapsed_ms = int((time.time() - started_at) * 1000)
    status = str(tool_result.get("status") or "unknown")
    logger.info(
        "mcp.tools.call name=%s status=%s duration_ms=%s",
        name,
        status,
        elapsed_ms,
    )
    _record_tool_usage(name, status, elapsed_ms)
    return elapsed_ms


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": API_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "profile": (os.getenv("MYTHOSAUR_TOOLS_PROFILE") or "readonly").strip().lower(),
        "tools_count": len(_iter_unique_tools()),
        "plugins": _build_health_plugins(),
    }


@app.get("/schema")
def schema_endpoint() -> dict[str, Any]:
    """Export all tool schemas for client generation and validation."""
    return {
        "version": API_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "tools": _build_schema_tools(),
    }


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    mcp_session_id: str | None = Header(default=None, alias="Mcp-Session-Id"),
) -> dict[str, Any]:
    token = _require_auth(authorization)
    _check_rate_limit(token[:8])
    _periodic_cleanup()

    started_at = time.time()
    payload = await request.json()
    method = str(payload.get("method") or "")
    request_id = payload.get("id")

    if method == "initialize":
        return _response(request_id, result=_initialize_session(response, mcp_session_id))

    if method == "tools/list":
        params = payload.get("params") or {}
        plugin_filter = _parse_plugin_filter(params.get("plugins"))
        return _response(request_id, result={"tools": _build_tools_list(plugin_filter)})

    if method == "tools/call":
        params = payload.get("params") or {}
        name = str(params.get("name") or "").strip()
        args = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            return _error_response(request_id, -32601, f"unknown tool: {name}")
        if not isinstance(args, dict):
            return _error_response(request_id, -32602, "arguments must be an object")

        tool_result = await _invoke_tool(tool, args, started_at)
        _log_tool_call(name, tool_result, started_at)
        return _response(request_id, result=_to_mcp_content(tool_result))

    return _error_response(request_id, -32601, f"unsupported method: {method}")
