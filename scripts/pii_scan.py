#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

from services.mcp_server.plugins.common import now_ms
from services.mcp_server.plugins.pii_tools import _git_staged_files, scan_paths

EXIT_OK: Final = 0
EXIT_BLOCKING_FINDINGS: Final = 1
EXIT_USAGE_ERROR: Final = 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the mythosaur-tools PII scanner locally.")
    parser.add_argument("--repo", default=".", help="Repository path to scan")
    parser.add_argument("--staged", action="store_true", help="Scan staged files only")
    parser.add_argument("--include-untracked", action="store_true", help="Include untracked files with --staged")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    return parser.parse_args()


def _repo_path(repo: str) -> Path:
    return Path(repo).expanduser().resolve()


def _print_text_result(result: dict[str, Any]) -> None:
    data = result.get("data") or {}
    findings = data.get("findings") or []
    files_scanned = data.get("files_scanned", 0)
    if not findings:
        print(f"PII scan clean: {files_scanned} files scanned.")
        return

    print(f"PII scan blocked: {len(findings)} finding(s) in {files_scanned} file(s).")
    for finding in findings:
        print(
            f"- {finding.get('severity')} {finding.get('kind')} "
            f"{finding.get('path')}:{finding.get('line')} {finding.get('snippet')}"
        )


def _scan_staged(repo_path: Path, *, include_untracked: bool) -> dict[str, Any]:
    paths = _git_staged_files(repo_path, include_untracked=include_untracked)
    return scan_paths(repo_path, paths, scope="staged", tool_name="scan_pii_staged", started=now_ms())


def main() -> int:
    args = _parse_args()

    repo_path = _repo_path(args.repo)
    if not repo_path.exists():
        print(f"error: repo path does not exist: {repo_path}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    if not args.staged:
        print("error: only --staged mode is currently supported by the local CLI", file=sys.stderr)
        return EXIT_USAGE_ERROR

    if not (repo_path / ".git").exists():
        print(f"error: not a git repo: {repo_path}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        result = _scan_staged(repo_path, include_untracked=args.include_untracked)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        _print_text_result(result)
    return EXIT_BLOCKING_FINDINGS if (result.get("data") or {}).get("blocking") else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
