from __future__ import annotations

import json
import logging
import os
import secrets
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response

from plugins import load_tools

logging.basicConfig(level=getattr(logging, (os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO))

app = FastAPI(title="mythosaur-tools", version="0.1.0")
TOOLS = load_tools()
SESSIONS: dict[str, dict[str, Any]] = {}


def _require_auth(auth_header: str | None) -> None:
    expected = (os.getenv("MYTHOSAUR_TOOLS_API_KEY") or "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="MYTHOSAUR_TOOLS_API_KEY is not configured")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid bearer token")


def _response(id_value: Any, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": id_value}
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


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "mythosaur-tools",
        "tools_count": len({t.name: t for t in TOOLS.values()}),
    }


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    mcp_session_id: str | None = Header(default=None, alias="Mcp-Session-Id"),
) -> dict[str, Any]:
    _require_auth(authorization)

    started = time.time()
    payload = await request.json()
    method = str(payload.get("method") or "")
    request_id = payload.get("id")

    if method == "initialize":
        sid = mcp_session_id or secrets.token_hex(12)
        SESSIONS[sid] = {"created_at": time.time()}
        response.headers["Mcp-Session-Id"] = sid
        result = {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "mythosaur-tools", "version": "0.1.0"},
            "capabilities": {"tools": {"listChanged": False}},
        }
        logging.info("mcp.initialize sid=%s", sid)
        return _response(request_id, result=result)

    if method == "tools/list":
        tools = []
        seen: set[str] = set()
        for name, tool in TOOLS.items():
            if tool.name in seen:
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
            tool_result = tool.handler(args)
        except Exception as exc:
            logging.exception("tool execution error name=%s", name)
            tool_result = {
                "status": "error",
                "tool": tool.name,
                "data": {},
                "error": {"code": "internal_error", "message": str(exc)},
                "meta": {"duration_ms": 0, "source": tool.plugin_id},
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
