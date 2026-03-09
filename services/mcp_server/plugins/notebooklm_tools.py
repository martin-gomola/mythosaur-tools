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
    raw = (os.getenv("NOTEBOOKLM_MCP_CLI_PATH") or "/secrets/notebooklm").strip() or "/secrets/notebooklm"
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


def _create_notebook(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_create_notebook", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    title = (args.get("title") or "").strip()
    tool_name = "notebooklm_create_notebook"

    if not title:
        return err(tool_name, "missing_args", "title is required", "notebooklm", started)

    payload, error_result = _run_json_command(
        tool_name,
        [_tool_bin(), "notebook", "create", title, "--json", "--profile", profile],
        started_ms=started,
        timeout_seconds=timeout_seconds,
    )
    if error_result:
        return error_result

    if not isinstance(payload, dict):
        return err(tool_name, "notebooklm_output_invalid", "Unexpected CLI output.", "notebooklm", started)

    return ok(
        tool_name,
        {
            "profile": profile,
            "notebook_id": payload.get("notebook_id") or payload.get("id", ""),
            "title": payload.get("title", title),
            "url": payload.get("url", ""),
        },
        "notebooklm",
        started,
    )


def _list_sources(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_list_sources", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    notebook_id = (args.get("notebook_id") or "").strip()
    tool_name = "notebooklm_list_sources"

    if not notebook_id:
        return err(tool_name, "missing_args", "notebook_id is required", "notebooklm", started)

    payload, error_result = _run_json_command(
        tool_name,
        [_tool_bin(), "source", "list", notebook_id, "--json", "--profile", profile],
        started_ms=started,
        timeout_seconds=timeout_seconds,
    )
    if error_result:
        return error_result

    sources: list[Any] = []
    if isinstance(payload, dict):
        sources = list(payload.get("sources") or [])
    elif isinstance(payload, list):
        sources = list(payload)

    return ok(
        tool_name,
        {
            "profile": profile,
            "notebook_id": notebook_id,
            "source_count": len(sources),
            "sources": sources,
        },
        "notebooklm",
        started,
    )


_ALLOWED_SOURCE_TYPES = frozenset({"url", "text", "drive", "file"})


def _listify_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    return []


def _add_source(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_add_source", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    notebook_id = (args.get("notebook_id") or "").strip()
    source_type = (args.get("source_type") or "").strip().lower()
    source_value = (args.get("source_value") or "").strip()
    tool_name = "notebooklm_add_source"

    if not notebook_id or not source_type or not source_value:
        return err(
            tool_name, "missing_args",
            "notebook_id, source_type, and source_value are required",
            "notebooklm", started,
        )
    if source_type not in _ALLOWED_SOURCE_TYPES:
        return err(
            tool_name, "invalid_source_type",
            f"source_type must be one of: {', '.join(sorted(_ALLOWED_SOURCE_TYPES))}",
            "notebooklm", started,
        )

    cmd = [_tool_bin(), "source", "add", notebook_id, f"--{source_type}", source_value, "--json", "--profile", profile]

    payload, error_result = _run_json_command(
        tool_name, cmd, started_ms=started, timeout_seconds=timeout_seconds,
    )
    if error_result:
        return error_result

    if not isinstance(payload, dict):
        return err(tool_name, "notebooklm_output_invalid", "Unexpected CLI output.", "notebooklm", started)

    return ok(
        tool_name,
        {
            "profile": profile,
            "notebook_id": notebook_id,
            "source_type": source_type,
            "source_id": payload.get("source_id") or payload.get("id", ""),
            "title": payload.get("title", ""),
            "status": payload.get("status", "added"),
        },
        "notebooklm",
        started,
    )


_ALLOWED_STUDIO_TYPES = frozenset({"audio", "video", "mindmap", "infographic", "slides", "briefing"})


def _create_studio_content(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_create_studio_content", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    notebook_id = (args.get("notebook_id") or "").strip()
    content_type = (args.get("content_type") or "audio").strip().lower()
    instructions = (args.get("instructions") or "").strip()
    tool_name = "notebooklm_create_studio_content"

    if not notebook_id:
        return err(tool_name, "missing_args", "notebook_id is required", "notebooklm", started)
    if content_type not in _ALLOWED_STUDIO_TYPES:
        return err(
            tool_name, "invalid_content_type",
            f"content_type must be one of: {', '.join(sorted(_ALLOWED_STUDIO_TYPES))}",
            "notebooklm", started,
        )

    cmd = [_tool_bin(), "studio", "create", notebook_id, "--type", content_type, "--confirm", "--json", "--profile", profile]
    if instructions:
        cmd.extend(["--instructions", instructions])

    payload, error_result = _run_json_command(
        tool_name, cmd, started_ms=started, timeout_seconds=timeout_seconds,
    )
    if error_result:
        return error_result

    if not isinstance(payload, dict):
        return err(tool_name, "notebooklm_output_invalid", "Unexpected CLI output.", "notebooklm", started)

    return ok(
        tool_name,
        {
            "profile": profile,
            "notebook_id": notebook_id,
            "content_type": content_type,
            "artifact_id": payload.get("artifact_id") or payload.get("id", ""),
            "status": payload.get("status", ""),
            "url": payload.get("url", ""),
        },
        "notebooklm",
        started,
    )


def _download_artifact(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_download_artifact", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    notebook_id = (args.get("notebook_id") or "").strip()
    artifact_id = (args.get("artifact_id") or "").strip()
    artifact_type = (args.get("artifact_type") or "audio").strip().lower()
    tool_name = "notebooklm_download_artifact"

    if not notebook_id or not artifact_id:
        return err(
            tool_name, "missing_args",
            "notebook_id and artifact_id are required",
            "notebooklm", started,
        )

    cmd = [_tool_bin(), "download", artifact_type, notebook_id, artifact_id, "--json", "--profile", profile]

    payload, error_result = _run_json_command(
        tool_name, cmd, started_ms=started, timeout_seconds=timeout_seconds,
    )
    if error_result:
        return error_result

    if not isinstance(payload, dict):
        return err(tool_name, "notebooklm_output_invalid", "Unexpected CLI output.", "notebooklm", started)

    return ok(
        tool_name,
        {
            "profile": profile,
            "notebook_id": notebook_id,
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "file_path": payload.get("file_path") or payload.get("path", ""),
            "file_size": payload.get("file_size") or payload.get("size", 0),
            "status": payload.get("status", "downloaded"),
        },
        "notebooklm",
        started,
    )


def _share_notebook(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _enabled_guard("notebooklm_share", started)
    if blocked:
        return blocked
    profile = _profile(args)
    timeout_seconds = _timeout_seconds(args)
    notebook_id = (args.get("notebook_id") or "").strip()
    share_type = (args.get("share_type") or "public").strip().lower()
    tool_name = "notebooklm_share"

    if not notebook_id:
        return err(tool_name, "missing_args", "notebook_id is required", "notebooklm", started)
    if share_type not in ("public", "invite"):
        return err(tool_name, "invalid_share_type", "share_type must be 'public' or 'invite'", "notebooklm", started)

    cmd = [_tool_bin(), "share", share_type, notebook_id, "--json", "--profile", profile]

    payload, error_result = _run_json_command(
        tool_name, cmd, started_ms=started, timeout_seconds=timeout_seconds,
    )
    if error_result:
        return error_result

    if not isinstance(payload, dict):
        return err(tool_name, "notebooklm_output_invalid", "Unexpected CLI output.", "notebooklm", started)

    return ok(
        tool_name,
        {
            "profile": profile,
            "notebook_id": notebook_id,
            "share_type": share_type,
            "url": payload.get("url") or payload.get("share_url", ""),
            "status": payload.get("status", "shared"),
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
        ToolDef(
            name="notebooklm_create_notebook",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Create a new NotebookLM notebook with the given title.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string", "description": "Name for the new notebook."},
                    "profile": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["title"],
            },
            handler=_create_notebook,
            aliases=["osaurus.notebooklm_create_notebook"],
        ),
        ToolDef(
            name="notebooklm_list_sources",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="List sources attached to a NotebookLM notebook.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "notebook_id": {"type": "string"},
                    "profile": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["notebook_id"],
            },
            handler=_list_sources,
            aliases=["osaurus.notebooklm_list_sources"],
        ),
        ToolDef(
            name="notebooklm_add_source",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Add a source to a NotebookLM notebook. Supported types: url, text, drive, file.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "notebook_id": {"type": "string"},
                    "source_type": {
                        "type": "string",
                        "enum": ["url", "text", "drive", "file"],
                        "description": "Kind of source to add.",
                    },
                    "source_value": {
                        "type": "string",
                        "description": "URL, plain text, Google Drive file ID, or local file path.",
                    },
                    "profile": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["notebook_id", "source_type", "source_value"],
            },
            handler=_add_source,
            aliases=["osaurus.notebooklm_add_source"],
        ),
        ToolDef(
            name="notebooklm_create_studio_content",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Generate studio content from a notebook (audio podcast, video, mind map, infographic, slides, or briefing document).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "notebook_id": {"type": "string"},
                    "content_type": {
                        "type": "string",
                        "enum": ["audio", "video", "mindmap", "infographic", "slides", "briefing"],
                        "description": "Type of studio content to generate. Defaults to audio.",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Optional instructions or focus for the generated content.",
                    },
                    "profile": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["notebook_id"],
            },
            handler=_create_studio_content,
            aliases=["osaurus.notebooklm_create_studio_content"],
        ),
        ToolDef(
            name="notebooklm_download_artifact",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Download a generated artifact (audio, image, etc.) from a NotebookLM notebook.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "notebook_id": {"type": "string"},
                    "artifact_id": {"type": "string"},
                    "artifact_type": {
                        "type": "string",
                        "enum": ["audio", "image"],
                        "description": "Type of artifact to download. Defaults to audio.",
                    },
                    "profile": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["notebook_id", "artifact_id"],
            },
            handler=_download_artifact,
            aliases=["osaurus.notebooklm_download_artifact"],
        ),
        ToolDef(
            name="notebooklm_share",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Share a NotebookLM notebook publicly or via invite link.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "notebook_id": {"type": "string"},
                    "share_type": {
                        "type": "string",
                        "enum": ["public", "invite"],
                        "description": "Sharing mode. Defaults to public.",
                    },
                    "profile": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["notebook_id"],
            },
            handler=_share_notebook,
            aliases=["osaurus.notebooklm_share"],
        ),
    ]
