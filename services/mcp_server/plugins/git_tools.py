from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from .common import ToolDef, err, now_ms, ok, parse_int, resolve_under_workspace


def _run_git(repo: str, args: list[str]) -> tuple[int, str, str]:
    repo_path = resolve_under_workspace(repo)
    cmd = ["git", "-C", str(repo_path), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _status(arguments: dict) -> dict:
    started = now_ms()
    repo = (arguments.get("repo") or ".").strip()
    try:
        code, out, err_text = _run_git(repo, ["status", "--short", "--branch"])
    except Exception as exc:
        return err("git_status", "git_error", str(exc), "git", started)
    if code != 0:
        return err("git_status", "git_failed", err_text or out or "git status failed", "git", started)
    return ok("git_status", {"repo": repo, "output": out}, "git", started)


def _log(arguments: dict) -> dict:
    started = now_ms()
    repo = (arguments.get("repo") or ".").strip()
    limit = parse_int(arguments.get("limit"), default=20, minimum=1, maximum=100)
    try:
        code, out, err_text = _run_git(repo, ["log", f"-n{limit}", "--oneline", "--decorate"])
    except Exception as exc:
        return err("git_log", "git_error", str(exc), "git", started)
    if code != 0:
        return err("git_log", "git_failed", err_text or out or "git log failed", "git", started)
    return ok("git_log", {"repo": repo, "limit": limit, "output": out}, "git", started)


def _diff(arguments: dict) -> dict:
    started = now_ms()
    repo = (arguments.get("repo") or ".").strip()
    target = (arguments.get("target") or "").strip()
    diff_args = ["diff"]
    if target:
        parts = shlex.split(target)
        if len(parts) > 4:
            return err("git_diff", "invalid_target", "target accepts at most 4 tokens", "git", started)
        diff_args.extend(parts)
    try:
        code, out, err_text = _run_git(repo, diff_args)
    except Exception as exc:
        return err("git_diff", "git_error", str(exc), "git", started)
    if code != 0:
        return err("git_diff", "git_failed", err_text or out or "git diff failed", "git", started)
    return ok("git_diff", {"repo": repo, "target": target, "output": out}, "git", started)


def _branch(arguments: dict) -> dict:
    started = now_ms()
    repo = (arguments.get("repo") or ".").strip()
    show_all = bool(arguments.get("all", False))
    args = ["branch", "--list"]
    if show_all:
        args.append("--all")
    try:
        code, out, err_text = _run_git(repo, args)
    except Exception as exc:
        return err("git_branch", "git_error", str(exc), "git", started)
    if code != 0:
        return err("git_branch", "git_failed", err_text or out or "git branch failed", "git", started)
    return ok("git_branch", {"repo": repo, "all": show_all, "output": out}, "git", started)


def get_tools() -> list[ToolDef]:
    schema_repo = {"repo": {"type": "string", "default": "."}}
    return [
        ToolDef(
            name="git_status",
            plugin_id="mythosaur.git",
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
            plugin_id="mythosaur.git",
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
            plugin_id="mythosaur.git",
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
            plugin_id="mythosaur.git",
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
