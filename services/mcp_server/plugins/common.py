from __future__ import annotations

import asyncio
import ipaddress
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine, Union
from urllib.parse import urlparse

SyncHandler = Callable[[dict[str, Any]], dict[str, Any]]
AsyncHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]


@dataclass
class ToolDef:
    name: str
    plugin_id: str
    description: str
    input_schema: dict[str, Any]
    handler: Union[SyncHandler, AsyncHandler]
    aliases: list[str] | None = None
    is_async: bool = False

    async def invoke(self, args: dict[str, Any]) -> dict[str, Any]:
        if self.is_async:
            return await self.handler(args)
        return await asyncio.to_thread(self.handler, args)


def now_ms() -> int:
    return int(time.time() * 1000)


def ok(tool: str, data: dict[str, Any], source: str, started_ms: int) -> dict[str, Any]:
    return {
        "status": "ok",
        "tool": tool,
        "data": data,
        "error": None,
        "meta": {
            "duration_ms": max(0, now_ms() - started_ms),
            "source": source,
        },
    }


def err(tool: str, code: str, message: str, source: str, started_ms: int) -> dict[str, Any]:
    return {
        "status": "error",
        "tool": tool,
        "data": {},
        "error": {"code": code, "message": message},
        "meta": {
            "duration_ms": max(0, now_ms() - started_ms),
            "source": source,
        },
    }


def parse_int(value: Any, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        out = int(value)
    except Exception:
        out = default
    if minimum is not None:
        out = max(minimum, out)
    if maximum is not None:
        out = min(maximum, out)
    return out


def workspace_root() -> Path:
    raw = (os.getenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT") or "/workspace").strip() or "/workspace"
    return Path(raw).resolve()


def _resolve_path_under(path_value: str, base: Path, escape_message: str) -> Path:
    value = (path_value or "").strip()
    if not value:
        raise ValueError("path is required")
    if "\x00" in value:
        raise ValueError("path contains NUL byte")

    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base / candidate

    resolved = candidate.resolve(strict=False)
    if resolved == base:
        return resolved

    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(escape_message.format(path_value=path_value)) from exc
    return resolved


def resolve_under_workspace(path_value: str) -> Path:
    return _resolve_path_under(
        path_value,
        workspace_root(),
        "path escapes workspace root: {path_value}",
    )


def resolve_under_base(path_value: str, base_dir: str | Path) -> Path:
    return _resolve_path_under(
        path_value,
        Path(base_dir).resolve(),
        "path escapes base dir: {path_value}",
    )


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_fetch_url(url: str) -> None:
    """Reject URLs with non-http(s) schemes or targeting private/reserved addresses."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme not allowed: {parsed.scheme!r} (only http and https)")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("URL has no hostname")
    if hostname in ("localhost", "localhost.localdomain"):
        raise ValueError("localhost URLs are not allowed")

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return  # non-IP hostname (domain name) is fine
    for net in _BLOCKED_NETWORKS:
        if addr in net:
            raise ValueError(f"URL targets a blocked private/reserved network: {addr}")


def command_profile() -> str:
    return (os.getenv("MYTHOSAUR_TOOLS_PROFILE") or "readonly").strip().lower() or "readonly"


def is_readonly() -> bool:
    return command_profile() != "power"


def bool_env(name: str, default: bool = False) -> bool:
    """Parse a boolean from an environment variable (1, true, yes, on)."""
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def listify_strings(value: Any) -> list[str]:
    """Convert a string (comma-separated), list, or single value to a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
