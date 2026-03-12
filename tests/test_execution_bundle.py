from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from workflow.execution_bundle import (
    ExecutionBundleRequest,
    ExecutionBundleUpdate,
    execution_bundle_paths,
    update_execution_bundle,
    write_execution_bundle,
)


def test_execution_bundle_core_flow(tmp_path: Path):
    written = write_execution_bundle(
        tmp_path,
        ExecutionBundleRequest(
            title="Add plugin smoke contract",
            summary="Keep plugin work packetized and auditable.",
            focus=("Add the shared helper.", "Document the usage."),
            verification=("uv run pytest tests/test_execution_bundle.py -q",),
        ),
    )

    paths = execution_bundle_paths(tmp_path)
    assert set(written) == set(paths.values())
    assert paths["request_packet"].exists()
    assert '"repo": "mythosaur-tools"' in paths["request_packet"].read_text(encoding="utf-8")
    assert "Do not duplicate execution logic" in paths["implementation_contract"].read_text(encoding="utf-8")

    written = update_execution_bundle(
        tmp_path,
        ExecutionBundleUpdate(
            status="completed",
            evidence=("uv run pytest tests/test_execution_bundle.py -q passed",),
            summary=("Completed the execution bundle helper update.",),
        ),
    )

    paths = execution_bundle_paths(tmp_path)
    assert written == [paths["evidence_bundle"], paths["completion_summary"]]
    evidence = paths["evidence_bundle"].read_text(encoding="utf-8")
    completion = paths["completion_summary"].read_text(encoding="utf-8")
    assert "- Status: `completed`" in evidence
    assert "## Update (completed)" in evidence
    assert "pytest tests/test_execution_bundle.py -q passed" in evidence
    assert "## Latest summary (completed)" in completion
    assert "Completed the execution bundle helper update." in completion


def test_execution_bundle_cli_flow(tmp_path: Path):
    init_script = Path("scripts/init_execution_bundle.py")
    update_script = Path("scripts/update_execution_bundle.py")
    init_result = subprocess.run(
        [
            sys.executable,
            str(init_script),
            "--root",
            str(tmp_path),
            "--title",
            "Add docs contract",
            "--summary",
            "Create a structured bundle for docs work.",
        ],
        check=True,
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )
    assert "artifacts/execution/request-packet.json" in init_result.stdout

    result = subprocess.run(
        [
            sys.executable,
            str(update_script),
            "--root",
            str(tmp_path),
            "--status",
            "in_progress",
            "--evidence",
            "Updated the README contract wording.",
            "--summary",
            "Started the docs execution pass.",
        ],
        check=True,
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    assert "artifacts/execution/evidence-bundle.md" in result.stdout
    evidence = (tmp_path / "artifacts" / "execution" / "evidence-bundle.md").read_text(encoding="utf-8")
    assert "- Status: `in_progress`" in evidence
    assert "Updated the README contract wording." in evidence
