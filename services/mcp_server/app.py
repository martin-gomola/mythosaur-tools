from __future__ import annotations

import collections
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Final

from fastapi import FastAPI, Header, HTTPException, Request, Response

from plugins import load_tools
from plugins.common import ToolDef, bool_env, env_get
from plugins.google_tools import google_auth_status, google_capabilities

logging.basicConfig(level=getattr(logging, (env_get("MT_LOG_LEVEL", "INFO") or "INFO").upper(), logging.INFO))
logger = logging.getLogger(__name__)

API_VERSION: Final = "0.2.0"
MCP_PROTOCOL_VERSION: Final = "2024-11-05"
SERVICE_NAME: Final = "mythosaur-tools"
JSONRPC_VERSION: Final = "2.0"
READONLY_PROFILE: Final = "readonly"
SEARCH_PLUGIN_ID: Final = "mythosaur.search"
BROWSER_PLUGIN_ID: Final = "mythosaur.browser"
GOOGLE_PLUGIN_ID: Final = "mythosaur.google_workspace"
FETCH_PLUGIN_ID: Final = "mythosaur.fetch"
TRANSCRIPT_PLUGIN_ID: Final = "mythosaur.transcript"
TIME_PLUGIN_ID: Final = "mythosaur.time"
PII_PLUGIN_ID: Final = "mythosaur.pii"
DEFAULT_CONSUMER_ENV: Final = "MT_DEFAULT_CONSUMER"
CONSUMER_HEADER: Final = "X-Mythosaur-Consumer"
IDE_REMOTE_PLUGIN_IDS: Final = frozenset(
    {
        TIME_PLUGIN_ID,
        SEARCH_PLUGIN_ID,
        FETCH_PLUGIN_ID,
        TRANSCRIPT_PLUGIN_ID,
        BROWSER_PLUGIN_ID,
        GOOGLE_PLUGIN_ID,
        PII_PLUGIN_ID,
    }
)
CONSUMER_PLUGIN_FILTERS: Final[dict[str, set[str] | None]] = {
    "all": None,
    "default": None,
    "mythosaur-ai": None,
    "codex": set(IDE_REMOTE_PLUGIN_IDS),
    "cursor": set(IDE_REMOTE_PLUGIN_IDS),
    "claude-code": set(IDE_REMOTE_PLUGIN_IDS),
    "ide": set(IDE_REMOTE_PLUGIN_IDS),
}

app = FastAPI(title=SERVICE_NAME, version=API_VERSION)
TOOLS, PLUGINS_META = load_tools()
SESSIONS: dict[str, dict[str, float]] = {}
_SESSION_TTL_SEC = 3600
_RATE_WINDOW_SEC = 60
_RATE_MAX_CALLS = int(env_get("MT_RATE_LIMIT", "120") or "120")
_rate_ledger: dict[str, list[float]] = collections.defaultdict(list)
_last_cleanup_at = 0.0
_CLEANUP_INTERVAL_SEC = 300
_USAGE_LOG_EVERY = int(env_get("MT_USAGE_LOG_EVERY", "5") or "5")
_USAGE_SUMMARY_INTERVAL_SEC = int(env_get("MT_USAGE_LOG_INTERVAL_SEC", "60") or "60")
_usage_total_calls = 0
_usage_tool_counts: collections.Counter[str] = collections.Counter()
_usage_last_summary_at = 0.0

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class McpRequestContext:
    request_id: Any
    method: str
    params: JsonDict
    consumer_hint: str | None
    started_at: float


def _now() -> float:
    return time.time()


def _record_tool_usage(name: str, status: str, duration_ms: int) -> None:
    global _usage_total_calls, _usage_last_summary_at

    _usage_total_calls += 1
    _usage_tool_counts[name] += 1

    now = _now()
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
    expected = (env_get("MT_API_KEY", "") or "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="MT_API_KEY is not configured")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return token


def _session_payload() -> dict[str, float]:
    return {"created_at": _now()}


def _check_rate_limit(key: str) -> None:
    if _RATE_MAX_CALLS <= 0:
        return
    now = _now()
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
    now = _now()
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


def _resolve_consumer_plugin_filter(raw_value: Any) -> set[str] | None:
    if raw_value is None:
        return None
    consumer = str(raw_value).strip().lower()
    if not consumer:
        return None
    if consumer not in CONSUMER_PLUGIN_FILTERS:
        known = ", ".join(sorted(CONSUMER_PLUGIN_FILTERS))
        raise ValueError(f"unknown consumer: {consumer} (expected one of: {known})")
    plugin_filter = CONSUMER_PLUGIN_FILTERS[consumer]
    return None if plugin_filter is None else set(plugin_filter)


def _default_consumer_name() -> str | None:
    raw = (env_get(DEFAULT_CONSUMER_ENV, "") or "").strip()
    if not raw:
        return None
    _resolve_consumer_plugin_filter(raw)
    return raw


def _effective_consumer_name(explicit_value: Any, header_value: str | None = None) -> str | None:
    explicit = str(explicit_value).strip() if explicit_value is not None else ""
    if explicit:
        _resolve_consumer_plugin_filter(explicit)
        return explicit

    header = (header_value or "").strip()
    if header:
        _resolve_consumer_plugin_filter(header)
        return header

    return _default_consumer_name()


def _merge_plugin_filters(base: set[str], consumer_filter: set[str] | None) -> set[str] | None:
    if not base and consumer_filter is None:
        return None
    if not base:
        return consumer_filter
    if consumer_filter is None:
        return base
    return base & consumer_filter


def _build_health_plugins() -> list[JsonDict]:
    searxng_url = (env_get("MT_SEARXNG_URL", "") or "").strip()
    browser_enabled = bool_env("MT_BROWSER_ENABLED", False)

    plugins: list[JsonDict] = []
    for plugin_meta in PLUGINS_META:
        entry: JsonDict = {
            "plugin_id": plugin_meta.plugin_id,
            "tool_count": plugin_meta.tool_count,
            "tools": plugin_meta.tool_names,
        }
        if plugin_meta.plugin_id == SEARCH_PLUGIN_ID:
            entry["searxng_configured"] = bool(searxng_url)
        if plugin_meta.plugin_id == BROWSER_PLUGIN_ID:
            entry["browser_enabled"] = browser_enabled
        if plugin_meta.plugin_id == GOOGLE_PLUGIN_ID:
            entry["capabilities"] = google_capabilities()
            entry["auth"] = google_auth_status()
        plugins.append(entry)
    return plugins


def _build_schema_tools(plugin_filter: set[str] | None = None) -> list[JsonDict]:
    return sorted(
        [
            {
                "name": tool.name,
                "plugin_id": tool.plugin_id,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "aliases": tool.aliases or [],
            }
            for tool in _iter_unique_tools(plugin_filter)
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
        elapsed_ms = int((_now() - started_at) * 1000)
        return {
            "status": "error",
            "tool": tool.name,
            "data": {},
            "error": {"code": "internal_error", "message": str(exc)},
            "meta": {"duration_ms": elapsed_ms, "source": tool.plugin_id},
        }


def _log_tool_call(name: str, tool_result: JsonDict, started_at: float) -> int:
    elapsed_ms = int((_now() - started_at) * 1000)
    status = str(tool_result.get("status") or "unknown")
    logger.info(
        "mcp.tools.call name=%s status=%s duration_ms=%s",
        name,
        status,
        elapsed_ms,
    )
    _record_tool_usage(name, status, elapsed_ms)
    return elapsed_ms


def _profile_name() -> str:
    return (env_get("MT_PROFILE", READONLY_PROFILE) or READONLY_PROFILE).strip().lower()


async def _request_context(request: Request) -> McpRequestContext:
    payload = await request.json()
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        params = {}
    return McpRequestContext(
        request_id=payload.get("id"),
        method=str(payload.get("method") or ""),
        params=params,
        consumer_hint=None,
        started_at=_now(),
    )


def _handle_initialize(context: McpRequestContext, response: Response, session_id: str | None) -> JsonDict:
    return _response(context.request_id, result=_initialize_session(response, session_id))


def _handle_tools_list(context: McpRequestContext) -> JsonDict:
    plugin_filter = _parse_plugin_filter(context.params.get("plugins"))
    try:
        consumer_name = _effective_consumer_name(context.params.get("consumer"), context.consumer_hint)
        consumer_filter = _resolve_consumer_plugin_filter(consumer_name)
    except ValueError as exc:
        return _error_response(context.request_id, -32602, str(exc))
    effective_filter = _merge_plugin_filters(plugin_filter, consumer_filter)
    return _response(context.request_id, result={"tools": _build_tools_list(effective_filter or set())})


async def _handle_tools_call(context: McpRequestContext) -> JsonDict:
    name = str(context.params.get("name") or "").strip()
    args = context.params.get("arguments") or {}
    if not isinstance(args, dict):
        return _error_response(context.request_id, -32602, "arguments must be an object")

    tool = TOOLS.get(name)
    if tool is None:
        return _error_response(context.request_id, -32601, f"unknown tool: {name}")

    tool_result = await _invoke_tool(tool, args, context.started_at)
    _log_tool_call(name, tool_result, context.started_at)
    return _response(context.request_id, result=_to_mcp_content(tool_result))


async def _dispatch_mcp_request(
    context: McpRequestContext,
    response: Response,
    session_id: str | None,
) -> JsonDict:
    if context.method == "initialize":
        return _handle_initialize(context, response, session_id)
    if context.method == "tools/list":
        return _handle_tools_list(context)
    if context.method == "tools/call":
        return await _handle_tools_call(context)
    return _error_response(context.request_id, -32601, f"unsupported method: {context.method}")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    try:
        default_consumer = _default_consumer_name()
    except ValueError:
        default_consumer = "invalid"
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": API_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "profile": _profile_name(),
        "default_consumer": default_consumer or "default",
        "supported_consumers": sorted(CONSUMER_PLUGIN_FILTERS),
        "tools_count": len(_iter_unique_tools()),
        "plugins": _build_health_plugins(),
    }


@app.get("/schema")
def schema_endpoint(
    consumer: str | None = None,
    plugins: str | None = None,
    x_mythosaur_consumer: str | None = Header(default=None, alias=CONSUMER_HEADER),
) -> dict[str, Any]:
    """Export all tool schemas for client generation and validation."""
    plugin_filter = _parse_plugin_filter(plugins)
    try:
        consumer_name = _effective_consumer_name(consumer, x_mythosaur_consumer)
        consumer_filter = _resolve_consumer_plugin_filter(consumer_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    effective_filter = _merge_plugin_filters(plugin_filter, consumer_filter)
    return {
        "version": API_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "tools": _build_schema_tools(effective_filter),
    }


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    mcp_session_id: str | None = Header(default=None, alias="Mcp-Session-Id"),
    x_mythosaur_consumer: str | None = Header(default=None, alias=CONSUMER_HEADER),
) -> dict[str, Any]:
    token = _require_auth(authorization)
    _check_rate_limit(token[:8])
    _periodic_cleanup()
    context = await _request_context(request)
    context = McpRequestContext(
        request_id=context.request_id,
        method=context.method,
        params=context.params,
        consumer_hint=x_mythosaur_consumer,
        started_at=context.started_at,
    )
    return await _dispatch_mcp_request(context, response, mcp_session_id)
