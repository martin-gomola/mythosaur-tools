#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.mcp_server.plugins.common import now_ms
from services.mcp_server.plugins.pii_tools import _git_staged_files, scan_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the mythosaur-tools PII scanner locally.")
    parser.add_argument("--repo", default=".", help="Repository path to scan")
    parser.add_argument("--staged", action="store_true", help="Scan staged files only")
    parser.add_argument("--include-untracked", action="store_true", help="Include untracked files with --staged")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    args = parser.parse_args()

    repo_path = Path(args.repo).expanduser().resolve()
    if not repo_path.exists():
        print(f"error: repo path does not exist: {repo_path}", file=sys.stderr)
        return 2

    if args.staged:
        if not (repo_path / ".git").exists():
            print(f"error: not a git repo: {repo_path}", file=sys.stderr)
            return 2
        try:
            paths = _git_staged_files(repo_path, include_untracked=args.include_untracked)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        result = scan_paths(repo_path, paths, scope="staged", tool_name="scan_pii_staged", started=now_ms())
    else:
        print("error: only --staged mode is currently supported by the local CLI", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        data = result.get("data") or {}
        findings = data.get("findings") or []
        if not findings:
            print(f"PII scan clean: {data.get('files_scanned', 0)} files scanned.")
        else:
            print(f"PII scan blocked: {len(findings)} finding(s) in {data.get('files_scanned', 0)} file(s).")
            for finding in findings:
                print(
                    f"- {finding.get('severity')} {finding.get('kind')} "
                    f"{finding.get('path')}:{finding.get('line')} {finding.get('snippet')}"
                )
    return 1 if (result.get("data") or {}).get("blocking") else 0


if __name__ == "__main__":
    raise SystemExit(main())
