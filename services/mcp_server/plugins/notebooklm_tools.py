from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .common import ToolDef, err, now_ms, ok, parse_int

GOOGLE_PLUGIN_ID = "mythosaur.google_workspace"


def _tool_bin() -> str:
    return (os.getenv("MYTHOSAUR_TOOLS_NOTEBOOKLM_BIN") or "nlm").strip() or "nlm"


def _storage_dir() -> Path:
    raw = (os.getenv("NOTEBOOKLM_MCP_CLI_PATH") or "/data/notebooklm").strip() or "/data/notebooklm"
    return Path(raw)


def _default_profile() -> str:
    return (os.getenv("MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE") or "default").strip() or "default"


def _default_timeout() -> int:
    return parse_int(os.getenv("MYTHOSAUR_TOOLS_NOTEBOOKLM_TIMEOUT"), 120, minimum=10, maximum=600)


def _notebooklm_enabled() -> bool:
    raw = (os.getenv("MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _enabled_guard(tool_name: str, started: int) -> dict[str, Any] | None:
    if _notebooklm_enabled():
        return None
    return err(
        tool_name,
        "capability_disabled",
        "NotebookLM capability is disabled by configuration.",
        "notebooklm",
        started,
    )


def _profile(args: dict[str, Any]) -> str:
    return (args.get("profile") or _default_profile() or "default").strip()


def _timeout_seconds(args: dict[str, Any]) -> int:
    return parse_int(args.get("timeout_seconds"), _default_timeout(), minimum=10, maximum=600)


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("NOTEBOOKLM_MCP_CLI_PATH", str(_storage_dir()))
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _binary_exists() -> bool:
    tool_bin = _tool_bin()
    if "/" in tool_bin:
        return Path(tool_bin).exists()
    return shutil.which(tool_bin) is not None


def _run_command(cmd: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=_command_env(),
        timeout=timeout_seconds,
    )


def _failure_message(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stderr or "").strip() or (proc.stdout or "").strip() or f"NotebookLM CLI exited with code {proc.returncode}."


def _run_json_command(
    tool_name: str,
    cmd: list[str],
    *,
    started_ms: int,
    timeout_seconds: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not _binary_exists():
        return None, err(
            tool_name,
            "notebooklm_cli_missing",
            f"NotebookLM CLI '{_tool_bin()}' is not installed in the current runtime.",
            "notebooklm",
            started_ms,
        )

    try:
        proc = _run_command(cmd, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired:
        return None, err(
            tool_name,
            "notebooklm_timeout",
            f"NotebookLM CLI timed out after {timeout_seconds}s.",
            "notebooklm",
            started_ms,
        )
    except Exception as exc:
        return None, err(
            tool_name,
            "notebooklm_cli_failed",
            str(exc),
            "notebooklm",
            started_ms,
        )

    if proc.returncode != 0:
        return None, err(
            tool_name,
            "notebooklm_cli_failed",
            _failure_message(proc),
            "notebooklm",
            started_ms,
        )

    try:
        return json.loads(proc.stdout or "{}"), None
    except json.JSONDecodeError as exc:
        return None, err(
            tool_name,
            "notebooklm_output_invalid",
            f"NotebookLM CLI returned non-JSON output: {exc}",
            "notebooklm",
            started_ms,
        )


def _auth_status(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_auth_status", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    tool_name = "notebooklm_auth_status"

    if not _binary_exists():
        return err(
            tool_name,
            "notebooklm_cli_missing",
            f"NotebookLM CLI '{_tool_bin()}' is not installed in the current runtime.",
            "notebooklm",
            started,
        )

    try:
        proc = _run_command(
            [_tool_bin(), "login", "--check", "--profile", profile],
            timeout_seconds=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return err(
            tool_name,
            "notebooklm_timeout",
            f"NotebookLM auth check timed out after {timeout_seconds}s.",
            "notebooklm",
            started,
        )
    except Exception as exc:
        return err(tool_name, "notebooklm_cli_failed", str(exc), "notebooklm", started)

    message = _failure_message(proc)
    return ok(
        tool_name,
        {
            "authenticated": proc.returncode == 0,
            "needs_login": proc.returncode != 0,
            "profile": profile,
            "storage_dir": str(_storage_dir()),
            "message": message,
        },
        "notebooklm",
        started,
    )


def _list_notebooks(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_list_notebooks", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    max_results = parse_int(args.get("max_results"), 25, minimum=1, maximum=100)
    tool_name = "notebooklm_list_notebooks"

    payload, error_result = _run_json_command(
        tool_name,
        [_tool_bin(), "notebook", "list", "--json", "--profile", profile],
        started_ms=started,
        timeout_seconds=timeout_seconds,
    )
    if error_result:
        return error_result

    notebooks = []
    total_count = 0
    owned_count = 0
    shared_count = 0
    shared_by_me_count = 0
    if isinstance(payload, dict):
        notebooks = list(payload.get("notebooks") or [])
        total_count = parse_int(payload.get("count"), len(notebooks), minimum=0)
        owned_count = parse_int(payload.get("owned_count"), 0, minimum=0)
        shared_count = parse_int(payload.get("shared_count"), 0, minimum=0)
        shared_by_me_count = parse_int(payload.get("shared_by_me_count"), 0, minimum=0)
    elif isinstance(payload, list):
        notebooks = list(payload)
        total_count = len(notebooks)

    notebooks = notebooks[:max_results]
    return ok(
        tool_name,
        {
            "profile": profile,
            "storage_dir": str(_storage_dir()),
            "returned_count": len(notebooks),
            "total_count": total_count or len(notebooks),
            "owned_count": owned_count,
            "shared_count": shared_count,
            "shared_by_me_count": shared_by_me_count,
            "notebooks": notebooks,
        },
        "notebooklm",
        started,
    )


def _query_notebook(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_query_notebook", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    notebook_id = (args.get("notebook_id") or "").strip()
    question = (args.get("question") or "").strip()
    conversation_id = (args.get("conversation_id") or "").strip()
    source_ids = args.get("source_ids") or []
    tool_name = "notebooklm_query_notebook"

    if not notebook_id or not question:
        return err(
            tool_name,
            "missing_args",
            "notebook_id and question are required",
            "notebooklm",
            started,
        )

    cmd = [_tool_bin(), "notebook", "query", notebook_id, question, "--json", "--profile", profile]
    if conversation_id:
        cmd.extend(["--conversation-id", conversation_id])
    if isinstance(source_ids, str):
        source_ids = [item.strip() for item in source_ids.split(",") if item.strip()]
    if source_ids:
        cmd.extend(["--source-ids", ",".join(str(item).strip() for item in source_ids if str(item).strip())])
    cmd.extend(["--timeout", str(timeout_seconds)])

    payload, error_result = _run_json_command(
        tool_name,
        cmd,
        started_ms=started,
        timeout_seconds=timeout_seconds,
    )
    if error_result:
        return error_result

    if not isinstance(payload, dict):
        return err(
            tool_name,
            "notebooklm_output_invalid",
            "NotebookLM query returned an unexpected payload.",
            "notebooklm",
            started,
        )

    return ok(
        tool_name,
        {
            "profile": profile,
            "storage_dir": str(_storage_dir()),
            "notebook_id": notebook_id,
            "question": question,
            "answer": payload.get("answer", ""),
            "conversation_id": payload.get("conversation_id"),
            "sources_used": payload.get("sources_used") or [],
            "citations": payload.get("citations") or {},
        },
        "notebooklm",
        started,
    )


def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="notebooklm_auth_status",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Check whether the configured NotebookLM profile is authenticated.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "profile": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": [],
            },
            handler=_auth_status,
            aliases=["osaurus.notebooklm_auth_status"],
        ),
        ToolDef(
            name="notebooklm_list_notebooks",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="List NotebookLM notebooks available to the configured account.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "profile": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": [],
            },
            handler=_list_notebooks,
            aliases=["osaurus.notebooklm_list_notebooks"],
        ),
        ToolDef(
            name="notebooklm_query_notebook",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Ask a grounded question against a NotebookLM notebook.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "notebook_id": {"type": "string"},
                    "question": {"type": "string"},
                    "conversation_id": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                    "profile": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["notebook_id", "question"],
            },
            handler=_query_notebook,
            aliases=["osaurus.notebooklm_query_notebook"],
        ),
    ]
