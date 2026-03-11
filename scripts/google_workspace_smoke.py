#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Final

import requests


DEFAULT_BASE_URL: Final = "http://127.0.0.1:8064"
DEFAULT_ORIGIN: Final = "Bratislava, Slovakia"
DEFAULT_DESTINATION: Final = "Oscadnica, Slovakia"
DEFAULT_TIMEOUT_SECONDS: Final = 30
GOOGLE_PLUGIN_ID: Final = "mythosaur.google_workspace"
MCP_PROTOCOL_VERSION: Final = "2024-11-05"


class SmokeFailure(RuntimeError):
    """Raised when the smoke test cannot validate the expected flow."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    return _utc_now().strftime("%Y-%m-%d %H:%M:%SZ")


def _run_suffix() -> str:
    return _utc_now().strftime("%Y%m%d-%H%M%S")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal Google Workspace smoke test against mythosaur-tools."
    )
    parser.add_argument(
        "--base-url",
        default=(os.getenv("MYTHOSAUR_TOOLS_BASE_URL") or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        help="Base URL for the mythosaur-tools HTTP service.",
    )
    parser.add_argument(
        "--api-key",
        default=(os.getenv("MYTHOSAUR_TOOLS_API_KEY") or "").strip(),
        help="Bearer token for mythosaur-tools. Defaults to MYTHOSAUR_TOOLS_API_KEY.",
    )
    parser.add_argument(
        "--spreadsheet-id",
        required=True,
        help="Target Google Sheets spreadsheet ID used to record the route link.",
    )
    parser.add_argument(
        "--sheet-title",
        default="Google Workspace Smoke",
        help="Sheet tab title to create for the smoke run.",
    )
    parser.add_argument(
        "--drive-folder-id",
        default="",
        help="Optional Google Drive folder ID for the smoke test file.",
    )
    parser.add_argument(
        "--origin",
        default=DEFAULT_ORIGIN,
        help="Route origin.",
    )
    parser.add_argument(
        "--destination",
        default=DEFAULT_DESTINATION,
        help="Route destination.",
    )
    parser.add_argument(
        "--travel-mode",
        default="driving",
        help="Travel mode for the Maps route link.",
    )
    return parser.parse_args()


def _headers(api_key: str, *, session_id: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return headers


def _require_api_key(api_key: str) -> str:
    if api_key:
        return api_key
    raise SystemExit("Missing API key. Set MYTHOSAUR_TOOLS_API_KEY or pass --api-key.")


def _healthz(base_url: str) -> dict[str, Any]:
    response = requests.get(f"{base_url.rstrip('/')}/healthz", timeout=5)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise SmokeFailure("Invalid /healthz response")
    return payload


def _initialize(base_url: str, api_key: str) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}/mcp",
        headers=_headers(api_key),
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "google-workspace-smoke", "version": "1.0.0"},
            },
        },
        timeout=10,
    )
    response.raise_for_status()
    session_id = response.headers.get("Mcp-Session-Id", "").strip()
    if not session_id:
        raise SmokeFailure("MCP initialize did not return Mcp-Session-Id")
    return session_id


def _call_tool(base_url: str, api_key: str, session_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}/mcp",
        headers=_headers(api_key, session_id=session_id),
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result") or {}
    structured = result.get("structuredContent") or {}
    if not isinstance(structured, dict):
        raise SmokeFailure(f"Tool {name} returned invalid structured content")
    if structured.get("status") == "error":
        error = structured.get("error") or {}
        message = error.get("message") or f"{name} failed"
        code = error.get("code") or "unknown_error"
        raise SmokeFailure(f"{name}: {code}: {message}")
    return structured


def _google_plugin(health: dict[str, Any]) -> dict[str, Any]:
    for plugin in health.get("plugins") or []:
        if isinstance(plugin, dict) and str(plugin.get("plugin_id") or "") == GOOGLE_PLUGIN_ID:
            return plugin
    raise SmokeFailure(f"{GOOGLE_PLUGIN_ID} plugin missing from /healthz")


def _check_google_auth(plugin: dict[str, Any]) -> None:
    auth = plugin.get("auth") or {}
    checks = auth.get("scope_checks") or {}
    required = {
        "gmail_send": "gmail.send",
        "drive_write": "drive.file",
        "sheets_write": "spreadsheets",
    }
    missing: list[str] = []
    for key, label in required.items():
        check = checks.get(key) or {}
        if not bool(check.get("granted", False)):
            missing_scopes = ", ".join(str(item) for item in (check.get("missing_scopes") or []))
            missing.append(f"{label} [{missing_scopes}]")
    if missing:
        raise SmokeFailure(
            "Google token is missing required scopes for this smoke test: " + "; ".join(missing)
        )


def _create_sheet_title(prefix: str) -> str:
    return f"{prefix} {_run_suffix()}"


def _route_link(args: argparse.Namespace, base_url: str, api_key: str, session_id: str) -> str:
    route = _call_tool(
        base_url,
        api_key,
        session_id,
        "google_maps_build_route_link",
        {
            "origin": args.origin,
            "destination": args.destination,
            "travel_mode": args.travel_mode,
        },
    )
    route_url = str(((route.get("data") or {}).get("url") or "")).strip()
    if not route_url:
        raise SmokeFailure("google_maps_build_route_link returned no URL")
    return route_url


def _append_sheet_row(
    args: argparse.Namespace,
    base_url: str,
    api_key: str,
    session_id: str,
    *,
    sheet_title: str,
    timestamp: str,
    route_url: str,
) -> dict[str, Any]:
    _call_tool(
        base_url,
        api_key,
        session_id,
        "google_sheets_create_sheet",
        {"spreadsheet_id": args.spreadsheet_id, "sheet_title": sheet_title},
    )
    return _call_tool(
        base_url,
        api_key,
        session_id,
        "google_sheets_append_rows",
        {
            "spreadsheet_id": args.spreadsheet_id,
            "range": f"{sheet_title}!A:D",
            "rows": [[timestamp, args.origin, args.destination, route_url]],
        },
    )


def _create_drive_file(
    args: argparse.Namespace,
    base_url: str,
    api_key: str,
    session_id: str,
    *,
    timestamp: str,
    route_url: str,
) -> dict[str, Any]:
    content = "\n".join(
        [
            "Google Workspace smoke test",
            f"Timestamp: {timestamp}",
            f"Origin: {args.origin}",
            f"Destination: {args.destination}",
            f"Route URL: {route_url}",
        ]
    )
    return _call_tool(
        base_url,
        api_key,
        session_id,
        "google_drive_create_text_file",
        {
            "file_name": f"google-workspace-smoke-{_run_suffix()}.txt",
            "parent_folder_id": args.drive_folder_id,
            "content": content,
        },
    )


def main() -> int:
    args = _parse_args()
    api_key = _require_api_key(args.api_key)
    health = _healthz(args.base_url)
    plugin = _google_plugin(health)
    _check_google_auth(plugin)
    session_id = _initialize(args.base_url, api_key)

    route_url = _route_link(args, args.base_url, api_key, session_id)
    timestamp = _timestamp()
    sheet_title = _create_sheet_title(args.sheet_title)
    sheet_append = _append_sheet_row(
        args,
        args.base_url,
        api_key,
        session_id,
        sheet_title=sheet_title,
        timestamp=timestamp,
        route_url=route_url,
    )
    drive_file = _create_drive_file(
        args,
        args.base_url,
        api_key,
        session_id,
        timestamp=timestamp,
        route_url=route_url,
    )

    summary = {
        "route_url": route_url,
        "spreadsheet_id": args.spreadsheet_id,
        "sheet_title": sheet_title,
        "sheet_append": (sheet_append.get("data") or {}),
        "drive_file": (drive_file.get("data") or {}),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
