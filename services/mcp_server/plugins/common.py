from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ToolDef:
    name: str
    plugin_id: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    aliases: list[str] | None = None


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


def resolve_under_workspace(path_value: str) -> Path:
    root = workspace_root()
    value = (path_value or "").strip()
    if not value:
        raise ValueError("path is required")

    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate

    resolved = candidate.resolve(strict=False)
    if resolved == root:
        return resolved

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace root: {path_value}") from exc
    return resolved


def command_profile() -> str:
    return (os.getenv("MYTHOSAUR_TOOLS_PROFILE") or "readonly").strip().lower() or "readonly"


def is_readonly() -> bool:
    return command_profile() != "power"
