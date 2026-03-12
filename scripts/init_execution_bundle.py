#!/usr/bin/env python3
"""Initialize a structured execution bundle for mythosaur-tools work."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.execution_bundle import ExecutionBundleRequest, write_execution_bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Target repo root. Defaults to current directory.")
    parser.add_argument("--title", required=True, help="Short work title.")
    parser.add_argument("--summary", required=True, help="One-line summary of the work.")
    parser.add_argument(
        "--scope",
        default="plugin",
        choices=("plugin", "shared-skill", "infra", "docs"),
        help="Primary work boundary.",
    )
    parser.add_argument(
        "--focus",
        action="append",
        dest="focus_items",
        default=[],
        help="Implementation focus item. Repeat for multiple items.",
    )
    parser.add_argument(
        "--verify",
        action="append",
        dest="verification_items",
        default=[],
        help="Verification command or check. Repeat for multiple items.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing execution bundle.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = Path(args.root).resolve()
    focus = tuple(args.focus_items or ("Implement the smallest useful slice without crossing repo boundaries.",))
    verification = tuple(
        args.verification_items
        or (
            "uv run pytest -q",
            "Update docs for any catalog or contract change.",
        )
    )
    written = write_execution_bundle(
        root,
        ExecutionBundleRequest(
            title=args.title,
            summary=args.summary,
            scope=args.scope,
            focus=focus,
            verification=verification,
        ),
        force=args.force,
    )
    for path in written:
        print(path.relative_to(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
