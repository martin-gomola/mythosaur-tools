from __future__ import annotations

import shlex
import subprocess
from typing import Final

from .common import JsonDict, ToolDef, err, now_ms, ok, parse_int, resolve_under_workspace

PLUGIN_ID: Final = "mythosaur.git"
MAX_DIFF_TARGET_TOKENS: Final = 4


def _repo_arg(arguments: JsonDict) -> str:
    return str(arguments.get("repo") or ".").strip()


def _run_git(repo: str, args: list[str]) -> tuple[int, str, str]:
    repo_path = resolve_under_workspace(repo)
    cmd = ["git", "-C", str(repo_path), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _git_result(tool_name: str, repo: str, started: int, args: list[str], data: JsonDict) -> JsonDict:
    try:
        code, stdout, stderr = _run_git(repo, args)
    except Exception as exc:
        return err(tool_name, "git_error", str(exc), "git", started)
    if code != 0:
        return err(tool_name, "git_failed", stderr or stdout or f"{tool_name} failed", "git", started)
    return ok(tool_name, data | {"repo": repo, "output": stdout}, "git", started)


def _status(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    repo = _repo_arg(arguments)
    return _git_result("git_status", repo, started, ["status", "--short", "--branch"], {})


def _log(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    repo = _repo_arg(arguments)
    limit = parse_int(arguments.get("limit"), default=20, minimum=1, maximum=100)
    return _git_result("git_log", repo, started, ["log", f"-n{limit}", "--oneline", "--decorate"], {"limit": limit})


def _diff(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    repo = _repo_arg(arguments)
    target = str(arguments.get("target") or "").strip()
    diff_args = ["diff"]
    if target:
        parts = shlex.split(target)
        if len(parts) > MAX_DIFF_TARGET_TOKENS:
            return err("git_diff", "invalid_target", "target accepts at most 4 tokens", "git", started)
        diff_args.extend(parts)
    return _git_result("git_diff", repo, started, diff_args, {"target": target})


def _branch(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    repo = _repo_arg(arguments)
    show_all = bool(arguments.get("all", False))
    args = ["branch", "--list"]
    if show_all:
        args.append("--all")
    return _git_result("git_branch", repo, started, args, {"all": show_all})


def get_tools() -> list[ToolDef]:
    schema_repo = {"repo": {"type": "string", "default": "."}}
    return [
        ToolDef(
            name="git_status",
            plugin_id=PLUGIN_ID,
            description="Git repository status (read-only).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": schema_repo,
                "required": [],
            },
            handler=_status,
            aliases=["osaurus.git_status"],
        ),
        ToolDef(
            name="git_log",
            plugin_id=PLUGIN_ID,
            description="Git log (read-only).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **schema_repo,
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                },
                "required": [],
            },
            handler=_log,
            aliases=["osaurus.git_log"],
        ),
        ToolDef(
            name="git_diff",
            plugin_id=PLUGIN_ID,
            description="Git diff (read-only).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **schema_repo,
                    "target": {"type": "string", "description": "Optional git diff args (limited)."},
                },
                "required": [],
            },
            handler=_diff,
            aliases=["osaurus.git_diff"],
        ),
        ToolDef(
            name="git_branch",
            plugin_id=PLUGIN_ID,
            description="Git branch listing (read-only).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **schema_repo,
                    "all": {"type": "boolean", "default": False},
                },
                "required": [],
            },
            handler=_branch,
            aliases=["osaurus.git_branch"],
        ),
    ]
