#!/usr/bin/env python3
"""Update evidence and completion status for a structured execution bundle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.execution_bundle import ExecutionBundleUpdate, update_execution_bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Target repo root. Defaults to current directory.")
    parser.add_argument(
        "--status",
        required=True,
        choices=("pending", "in_progress", "completed", "blocked", "failed"),
        help="Bundle status to record.",
    )
    parser.add_argument(
        "--evidence",
        action="append",
        dest="evidence_items",
        default=[],
        help="Evidence line to record. Repeat for multiple items.",
    )
    parser.add_argument(
        "--summary",
        action="append",
        dest="summary_items",
        default=[],
        help="Summary line to record. Repeat for multiple items.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = Path(args.root).resolve()
    written = update_execution_bundle(
        root,
        ExecutionBundleUpdate(
            status=args.status,
            evidence=tuple(args.evidence_items),
            summary=tuple(args.summary_items),
        ),
    )
    for path in written:
        print(path.relative_to(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
