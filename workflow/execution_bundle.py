"""Structured delivery bundle helpers for mythosaur-tools work."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecutionBundleRequest:
    title: str
    summary: str
    focus: tuple[str, ...]
    verification: tuple[str, ...]
    scope: str = "plugin"
    references: tuple[str, ...] = (
        "docs/catalog.md",
        "docs/integration.md",
    )


@dataclass(frozen=True)
class ExecutionBundleUpdate:
    status: str
    evidence: tuple[str, ...]
    summary: tuple[str, ...]


def execution_bundle_paths(root: Path) -> dict[str, Path]:
    base = root / "artifacts" / "execution"
    return {
        "request_packet": base / "request-packet.json",
        "implementation_contract": base / "implementation-contract.md",
        "verification_plan": base / "verification-plan.md",
        "evidence_bundle": base / "evidence-bundle.md",
        "completion_summary": base / "completion-summary.md",
        "architecture_decisions": root / "docs" / "architecture-decisions.md",
    }


def render_execution_bundle(root: Path, request: ExecutionBundleRequest) -> dict[Path, str]:
    paths = execution_bundle_paths(root)
    packet = {
        "repo": "mythosaur-tools",
        "project_root": str(root),
        "title": request.title,
        "summary": request.summary,
        "scope": request.scope,
        "implementation_focus": list(request.focus),
        "verification_commands": list(request.verification),
        "references": list(request.references),
    }
    focus_lines = _bullet_lines(request.focus)
    verification_lines = _bullet_lines(request.verification)
    return {
        paths["request_packet"]: json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
        paths["implementation_contract"]: (
            "# Implementation Contract\n\n"
            f"- Title: {request.title}\n"
            f"- Scope: `{request.scope}`\n\n"
            "## Summary\n\n"
            f"{request.summary}\n\n"
            "## Implementation focus\n\n"
            f"{focus_lines}\n"
            "## Non-goals\n\n"
            "- Do not widen behavior beyond the target plugin or shared helper boundary.\n"
            "- Do not duplicate execution logic that already belongs in an existing plugin.\n"
            "- Do not hide consumer-specific routing inside tool handlers.\n"
        ),
        paths["verification_plan"]: (
            "# Verification Plan\n\n"
            f"- Title: {request.title}\n\n"
            "## Required checks\n\n"
            f"{verification_lines}\n"
            "## Evidence expectations\n\n"
            "- Record exact command output or the reason a check could not run.\n"
            "- Capture boundary or catalog changes in the completion summary.\n"
        ),
        paths["evidence_bundle"]: (
            "# Evidence Bundle\n\n"
            f"- Title: {request.title}\n"
            "- Status: `pending`\n\n"
            "## Evidence\n\n"
            "- Execution not started yet.\n"
            "- Add test output, smoke checks, and affected plugin notes here.\n"
        ),
        paths["completion_summary"]: (
            "# Completion Summary\n\n"
            f"- Title: {request.title}\n"
            "- Status: `pending`\n\n"
            "## Summary\n\n"
            "- Execution bundle initialized.\n"
            "- Implementation and verification are still pending.\n"
        ),
        paths["architecture_decisions"]: (
            "# Architecture Decisions\n\n"
            f"## {request.title}\n\n"
            f"- Scope: `{request.scope}`\n"
            f"- Summary: {request.summary}\n"
            "- Decision framing: keep shared execution logic inside `mythosaur-tools`; keep consumer orchestration outside this repo.\n"
        ),
    }


def write_execution_bundle(root: Path, request: ExecutionBundleRequest, *, force: bool = False) -> list[Path]:
    rendered = render_execution_bundle(root, request)
    if not force:
        existing = [path for path in rendered if path.exists()]
        if existing:
            joined = ", ".join(str(path.relative_to(root)) for path in existing)
            raise FileExistsError(f"execution bundle already exists for: {joined}")

    written: list[Path] = []
    for path, content in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def update_execution_bundle(root: Path, update: ExecutionBundleUpdate) -> list[Path]:
    paths = execution_bundle_paths(root)
    request_packet = paths["request_packet"]
    if not request_packet.exists():
        raise FileNotFoundError("execution bundle request packet not found; initialize the bundle first")

    packet = json.loads(request_packet.read_text(encoding="utf-8"))
    title = str(packet.get("title") or "Unknown work item")

    evidence_path = paths["evidence_bundle"]
    completion_path = paths["completion_summary"]
    if not evidence_path.exists() or not completion_path.exists():
        raise FileNotFoundError("execution bundle markdown files not found; initialize the bundle first")

    evidence_content = _replace_status_line(evidence_path.read_text(encoding="utf-8"), update.status)
    completion_content = _replace_status_line(completion_path.read_text(encoding="utf-8"), update.status)

    evidence_content = _append_markdown_section(
        evidence_content,
        heading=f"Update ({update.status})",
        lines=update.evidence or ("No evidence details recorded.",),
    )
    completion_content = _append_markdown_section(
        completion_content,
        heading=f"Latest summary ({update.status})",
        lines=update.summary
        or (
            f"{title} moved to `{update.status}`.",
            "Add a more specific summary on the next update.",
        ),
    )

    evidence_path.write_text(evidence_content, encoding="utf-8")
    completion_path.write_text(completion_content, encoding="utf-8")
    return [evidence_path, completion_path]


def _bullet_lines(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _replace_status_line(content: str, status: str) -> str:
    updated, count = re.subn(r"^- Status: `[^`]+`$", f"- Status: `{status}`", content, count=1, flags=re.MULTILINE)
    if count:
        return updated
    return content.rstrip() + f"\n- Status: `{status}`\n"


def _append_markdown_section(content: str, *, heading: str, lines: tuple[str, ...]) -> str:
    body = "\n".join(f"- {line}" for line in lines if line)
    block = f"## {heading}\n\n{body}\n"
    return content.rstrip() + "\n\n" + block
