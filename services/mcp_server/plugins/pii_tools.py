from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Final

from .common import JsonDict, ToolDef, env_get, err, now_ms, ok, parse_int, resolve_under_base, workspace_root

PLUGIN_ID: Final = "mythosaur.pii"
PLUGIN_SOURCE: Final = "pii"
MAX_SCAN_BYTES: Final = 512 * 1024
HOOK_MARKER: Final = "# Managed by mythosaur-tools PII pre-commit hook"

PATTERNS: list[tuple[str, str, str, re.Pattern[str]]] = [
    ("user_home_path", "high", "Possible local home path", re.compile(r"(/Users/[^/\s]+|/home/[^/\s]+)(/[^\s`'\"<>()]+)?")),
    ("email_address", "medium", "Possible email address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("openai_key", "critical", "Possible OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github_token", "critical", "Possible GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("bearer_token", "high", "Possible bearer token", re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]{10,}", re.IGNORECASE)),
    ("private_key", "critical", "Private key marker", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


def pii_root() -> Path:
    raw = (env_get("MT_PII_ROOT", str(workspace_root())) or str(workspace_root())).strip() or str(workspace_root())
    return Path(raw).expanduser().resolve()


def tools_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def pii_script_path() -> Path:
    raw = (env_get("MT_PII_SCRIPT_PATH", "") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (tools_repo_root() / "scripts" / "pii_scan.py").resolve()


def resolve_repo(arguments: JsonDict) -> Path:
    repo = str(arguments.get("repo") or ".").strip() or "."
    return resolve_under_base(repo, pii_root())


def _run_git(repo_path: Path, args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _git_tracked_files(repo_path: Path) -> list[Path]:
    code, out, err_text = _run_git(repo_path, ["ls-files"])
    if code != 0:
        raise RuntimeError(err_text or out or "git ls-files failed")
    return [repo_path / line for line in out.splitlines() if line.strip()]


def _git_staged_files(repo_path: Path, *, include_untracked: bool) -> list[Path]:
    code, out, err_text = _run_git(repo_path, ["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if code != 0:
        raise RuntimeError(err_text or out or "git diff --cached failed")
    paths = [repo_path / line for line in out.splitlines() if line.strip()]
    if include_untracked:
        code, out, err_text = _run_git(repo_path, ["ls-files", "--others", "--exclude-standard"])
        if code != 0:
            raise RuntimeError(err_text or out or "git ls-files --others failed")
        paths.extend(repo_path / line for line in out.splitlines() if line.strip())
    return _unique_paths(paths)


def _walk_repo_files(repo_path: Path, *, max_files: int) -> list[Path]:
    files: list[Path] = []
    for path in sorted(repo_path.rglob("*")):
        if ".git" in path.parts:
            continue
        if not path.is_file():
            continue
        files.append(path)
        if len(files) >= max_files:
            break
    return files


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data


def _trim_snippet(text: str) -> str:
    text = " ".join(text.strip().split())
    if len(text) <= 160:
        return text
    return text[:157] + "..."


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _match_findings(repo_path: Path, path: Path, text: str) -> list[JsonDict]:
    rel_path = str(path.relative_to(repo_path))
    matches: list[JsonDict] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "pii:allow" in line:
            continue
        for kind, severity, description, pattern in PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            matches.append(
                {
                    "path": rel_path,
                    "line": line_no,
                    "kind": kind,
                    "severity": severity,
                    "description": description,
                    "snippet": _trim_snippet(line),
                }
            )
    return matches


def scan_paths(repo_path: Path, paths: list[Path], *, scope: str, tool_name: str, started: int) -> JsonDict:
    findings: list[JsonDict] = []
    files_scanned = 0

    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            raw = path.read_bytes()
        except Exception:
            continue
        if len(raw) > MAX_SCAN_BYTES or _is_binary(raw):
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("latin-1")
            except Exception:
                continue
        files_scanned += 1
        findings.extend(_match_findings(repo_path, path, text))

    return ok(
        tool_name,
        {
            "repo": str(repo_path),
            "scope": scope,
            "clean": not findings,
            "blocking": bool(findings),
            "files_scanned": files_scanned,
            "findings_count": len(findings),
            "findings": findings,
        },
        PLUGIN_SOURCE,
        started,
    )


def _scan_repo(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    try:
        repo_path = resolve_repo(arguments)
        max_files = parse_int(arguments.get("max_files"), default=5000, minimum=1, maximum=20000)
        if (repo_path / ".git").exists():
            paths = _git_tracked_files(repo_path)
        else:
            paths = _walk_repo_files(repo_path, max_files=max_files)
        return scan_paths(repo_path, paths[:max_files], scope="repo", tool_name="scan_pii_repo", started=started)
    except Exception as exc:
        return err("scan_pii_repo", "pii_scan_error", str(exc), PLUGIN_SOURCE, started)


def _scan_staged(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    try:
        repo_path = resolve_repo(arguments)
        include_untracked = bool(arguments.get("include_untracked", False))
        if not (repo_path / ".git").exists():
            return err("scan_pii_staged", "not_git_repo", f"git metadata not found: {repo_path}", PLUGIN_SOURCE, started)
        paths = _git_staged_files(repo_path, include_untracked=include_untracked)
        return scan_paths(repo_path, paths, scope="staged", tool_name="scan_pii_staged", started=started)
    except Exception as exc:
        return err("scan_pii_staged", "pii_scan_error", str(exc), PLUGIN_SOURCE, started)


def _git_hook_path(repo_path: Path) -> Path:
    code, out, err_text = _run_git(repo_path, ["rev-parse", "--git-path", "hooks/pre-commit"])
    if code != 0:
        raise RuntimeError(err_text or out or "git rev-parse --git-path failed")
    hook_path = Path(out)
    if not hook_path.is_absolute():
        hook_path = repo_path / hook_path
    return hook_path.resolve()


def _install_hook(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    try:
        repo_path = resolve_repo(arguments)
        if not (repo_path / ".git").exists():
            return err("install_pii_precommit_hook", "not_git_repo", f"git metadata not found: {repo_path}", PLUGIN_SOURCE, started)

        force = bool(arguments.get("force", False))
        hook_path = _git_hook_path(repo_path)
        hook_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = hook_path.with_name("pre-commit.local")
        script_path = pii_script_path()
        if not script_path.exists():
            return err("install_pii_precommit_hook", "missing_script", f"pii scan script not found: {script_path}", PLUGIN_SOURCE, started)

        existing = hook_path.read_text(encoding="utf-8") if hook_path.exists() else ""
        if hook_path.exists() and HOOK_MARKER not in existing:
            if not force:
                return err(
                    "install_pii_precommit_hook",
                    "hook_exists",
                    f"pre-commit hook already exists at {hook_path}; rerun with force=true to preserve it as pre-commit.local",
                    PLUGIN_SOURCE,
                    started,
                )
            if not backup_path.exists():
                backup_path.write_text(existing, encoding="utf-8")

        hook_text = (
            "#!/bin/sh\n"
            f"{HOOK_MARKER}\n"
            "set -eu\n\n"
            "HOOK_DIR=\"$(CDPATH= cd -- \"$(dirname \"$0\")\" && pwd)\"\n"
            "if [ -x \"$HOOK_DIR/pre-commit.local\" ]; then\n"
            "  \"$HOOK_DIR/pre-commit.local\"\n"
            "fi\n"
            f"python3 {str(script_path)!r} --staged --repo {str(repo_path)!r}\n"
        )
        hook_path.write_text(hook_text, encoding="utf-8")
        hook_path.chmod(0o755)

        return ok(
            "install_pii_precommit_hook",
            {
                "repo": str(repo_path),
                "hook_path": str(hook_path),
                "backup_path": str(backup_path) if backup_path.exists() else "",
                "script_path": str(script_path),
                "force": force,
            },
            PLUGIN_SOURCE,
            started,
        )
    except Exception as exc:
        return err("install_pii_precommit_hook", "hook_install_error", str(exc), PLUGIN_SOURCE, started)


def get_tools() -> list[ToolDef]:
    repo_schema = {
        "repo": {"type": "string", "default": "."},
    }
    return [
        ToolDef(
            name="scan_pii_staged",
            plugin_id=PLUGIN_ID,
            description="Scan staged files in a git repo for PII or secret-like values.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **repo_schema,
                    "include_untracked": {"type": "boolean", "default": False},
                },
                "required": [],
            },
            handler=_scan_staged,
            aliases=["osaurus.scan_pii_staged"],
        ),
        ToolDef(
            name="scan_pii_repo",
            plugin_id=PLUGIN_ID,
            description="Scan a repository or directory for PII or secret-like values.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **repo_schema,
                    "max_files": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 5000},
                },
                "required": [],
            },
            handler=_scan_repo,
            aliases=["osaurus.scan_pii_repo"],
        ),
        ToolDef(
            name="install_pii_precommit_hook",
            plugin_id=PLUGIN_ID,
            description="Install a local pre-commit hook that runs the mythosaur-tools PII scanner.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **repo_schema,
                    "force": {"type": "boolean", "default": False},
                },
                "required": [],
            },
            handler=_install_hook,
            aliases=["osaurus.install_pii_precommit_hook"],
        ),
    ]
