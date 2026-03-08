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
from plugins.google_workspace_tools import google_capabilities

logging.basicConfig(level=getattr(logging, (os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO))

API_VERSION = "0.2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

app = FastAPI(title="mythosaur-tools", version=API_VERSION)
TOOLS, PLUGINS_META = load_tools()
SESSIONS: dict[str, dict[str, Any]] = {}
_RATE_WINDOW_SEC = 60
_RATE_MAX_CALLS = int(os.getenv("MYTHOSAUR_TOOLS_RATE_LIMIT", "120"))
_rate_ledger: dict[str, list[float]] = collections.defaultdict(list)


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
        return _response(request_id, result=_to_mcp_content(tool_result))

    return _response(
        request_id,
        error={"code": -32601, "message": f"unsupported method: {method}"},
    )
