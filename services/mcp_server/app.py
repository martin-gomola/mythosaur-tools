from __future__ import annotations

import collections
import json
import logging
import os
import secrets
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response

from plugins import load_tools
from plugins.google_workspace_tools import google_auth_status, google_capabilities

logging.basicConfig(level=getattr(logging, (os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO))

API_VERSION = "0.2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

app = FastAPI(title="mythosaur-tools", version=API_VERSION)
TOOLS, PLUGINS_META = load_tools()
SESSIONS: dict[str, dict[str, Any]] = {}
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
    logging.info(
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


def _response(id_value: Any, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> dict:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": id_value}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result or {}
    return payload


def _to_mcp_content(tool_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(tool_result, ensure_ascii=False),
            }
        ],
        "structuredContent": tool_result,
    }


def _unique_tools() -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for tool in TOOLS.values():
        if tool.name in seen:
            continue
        seen.add(tool.name)
        out.append(tool)
    return out


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    searxng_url = (os.getenv("MYTHOSAUR_TOOLS_SEARXNG_URL") or "").strip()
    browser_enabled = (os.getenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED") or "false").strip().lower() in {
        "1", "true", "yes", "on",
    }

    plugins = []
    for pm in PLUGINS_META:
        entry: dict[str, Any] = {
            "plugin_id": pm.plugin_id,
            "tool_count": pm.tool_count,
            "tools": pm.tool_names,
        }
        if pm.plugin_id == "mythosaur.search":
            entry["searxng_configured"] = bool(searxng_url)
        if pm.plugin_id == "mythosaur.browser":
            entry["browser_enabled"] = browser_enabled
        if pm.plugin_id == "mythosaur.google_workspace":
            entry["capabilities"] = google_capabilities()
            entry["auth"] = google_auth_status()
        plugins.append(entry)

    return {
        "status": "ok",
        "service": "mythosaur-tools",
        "version": API_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "profile": (os.getenv("MYTHOSAUR_TOOLS_PROFILE") or "readonly").strip().lower(),
        "tools_count": len(_unique_tools()),
        "plugins": plugins,
    }


@app.get("/schema")
def schema_endpoint() -> dict[str, Any]:
    """Export all tool schemas for client generation and validation."""
    tools = []
    for tool in _unique_tools():
        tools.append({
            "name": tool.name,
            "plugin_id": tool.plugin_id,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "aliases": tool.aliases or [],
        })
    return {
        "version": API_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "tools": sorted(tools, key=lambda x: x["name"]),
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

    started = time.time()
    payload = await request.json()
    method = str(payload.get("method") or "")
    request_id = payload.get("id")

    if method == "initialize":
        sid = mcp_session_id or secrets.token_hex(12)
        SESSIONS[sid] = {"created_at": time.time()}
        response.headers["Mcp-Session-Id"] = sid
        result = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "serverInfo": {"name": "mythosaur-tools", "version": API_VERSION},
            "capabilities": {"tools": {"listChanged": False}},
        }
        logging.info("mcp.initialize sid=%s", sid)
        return _response(request_id, result=result)

    if method == "tools/list":
        params = payload.get("params") or {}
        plugin_filter_raw = (params.get("plugins") or "").strip()
        plugin_filter = {p.strip() for p in plugin_filter_raw.split(",") if p.strip()} if plugin_filter_raw else set()

        tools = []
        seen: set[str] = set()
        for tool in TOOLS.values():
            if tool.name in seen:
                continue
            if plugin_filter and tool.plugin_id not in plugin_filter:
                continue
            seen.add(tool.name)
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                    "annotations": {
                        "pluginId": tool.plugin_id,
                        "aliases": tool.aliases or [],
                    },
                }
            )
        return _response(request_id, result={"tools": sorted(tools, key=lambda x: x["name"])})

    if method == "tools/call":
        params = payload.get("params") or {}
        name = str(params.get("name") or "").strip()
        args = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            return _response(
                request_id,
                error={"code": -32601, "message": f"unknown tool: {name}"},
            )
        if not isinstance(args, dict):
            return _response(
                request_id,
                error={"code": -32602, "message": "arguments must be an object"},
            )

        try:
            tool_result = await tool.invoke(args)
        except Exception as exc:
            logging.exception("tool execution error name=%s", name)
            elapsed_err = int((time.time() - started) * 1000)
            tool_result = {
                "status": "error",
                "tool": tool.name,
                "data": {},
                "error": {"code": "internal_error", "message": str(exc)},
                "meta": {"duration_ms": elapsed_err, "source": tool.plugin_id},
            }

        elapsed_ms = int((time.time() - started) * 1000)
        logging.info(
            "mcp.tools.call name=%s status=%s duration_ms=%s",
            name,
            tool_result.get("status"),
            elapsed_ms,
        )
        _record_tool_usage(name, str(tool_result.get("status") or "unknown"), elapsed_ms)
        return _response(request_id, result=_to_mcp_content(tool_result))

    return _response(
        request_id,
        error={"code": -32601, "message": f"unsupported method: {method}"},
    )
