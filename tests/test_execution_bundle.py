from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from workflow.execution_bundle import ExecutionBundleRequest, execution_bundle_paths, write_execution_bundle


def test_write_execution_bundle_creates_expected_files(tmp_path: Path):
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


def test_write_execution_bundle_refuses_to_overwrite_without_force(tmp_path: Path):
    write_execution_bundle(
        tmp_path,
        ExecutionBundleRequest(
            title="Initial bundle",
            summary="Create files once.",
            focus=("Focus item",),
            verification=("pytest",),
        ),
    )

    with pytest.raises(FileExistsError, match="execution bundle already exists"):
        write_execution_bundle(
            tmp_path,
            ExecutionBundleRequest(
                title="Second bundle",
                summary="Should fail without force.",
                focus=("Focus item",),
                verification=("pytest",),
            ),
        )


def test_init_execution_bundle_script_writes_files(tmp_path: Path):
    script = Path("scripts/init_execution_bundle.py")
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--root",
            str(tmp_path),
            "--title",
            "Add docs contract",
            "--summary",
            "Create a structured bundle for docs work.",
            "--scope",
            "docs",
            "--focus",
            "Update the README and integration docs.",
            "--verify",
            "uv run pytest tests/test_execution_bundle.py -q",
        ],
        check=True,
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    assert "artifacts/execution/request-packet.json" in result.stdout
    assert (tmp_path / "artifacts" / "execution" / "completion-summary.md").exists()
