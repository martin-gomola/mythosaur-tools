import json
import os
import stat
import subprocess
from pathlib import Path


SCRIPT = Path("scripts/export-skills.sh")


def _create_skill(root: Path, name: str, body: str = "") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n{body}\n", encoding="utf-8")
    return skill_dir


def test_export_writes_manifest_and_bundle(tmp_path: Path):
    shared = tmp_path / "shared"
    consumers = tmp_path / "consumers"
    dest = tmp_path / "skills" / "mythosaur"
    _create_skill(shared, "tool-intent-router", "shared")
    _create_skill(shared, "google-workspace-router", "google")
    _create_skill(consumers / "codex", "codex-mythosaur-orchestrator", "codex")

    env = os.environ | {
        "MYTHOSAUR_SHARED_SKILLS_DIR": str(shared),
        "MYTHOSAUR_CONSUMER_SKILLS_DIR": str(consumers),
    }
    subprocess.run(
        ["bash", str(SCRIPT), "--consumer", "codex", str(dest)],
        check=True,
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    assert (dest / "tool-intent-router" / "SKILL.md").exists()
    assert (dest / "google-workspace-router" / "SKILL.md").exists()
    assert (dest / "codex-mythosaur-orchestrator" / "SKILL.md").exists()

    manifest = json.loads((dest / ".export-manifest.json").read_text(encoding="utf-8"))
    assert manifest["consumer"] == "codex"
    assert manifest["copied_skills"] == [
        "codex-mythosaur-orchestrator",
        "google-workspace-router",
        "tool-intent-router",
    ]
    assert manifest["overwritten_sibling_skills"] == []


def test_export_overwrites_sibling_skill_and_deduplicates_bundle(tmp_path: Path):
    shared = tmp_path / "shared"
    consumers = tmp_path / "consumers"
    registry = tmp_path / "skills"
    dest = registry / "mythosaur"

    overwritten = _create_skill(shared, "agent-browser", "new version")
    (overwritten / "helper.sh").write_text("#!/bin/sh\necho new\n", encoding="utf-8")
    _create_skill(consumers / "codex", "codex-mythosaur-orchestrator", "codex")

    sibling = _create_skill(registry, "agent-browser", "old version")
    (sibling / "helper.sh").write_text("#!/bin/sh\necho old\n", encoding="utf-8")

    env = os.environ | {
        "MYTHOSAUR_SHARED_SKILLS_DIR": str(shared),
        "MYTHOSAUR_CONSUMER_SKILLS_DIR": str(consumers),
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), "--consumer", "codex", str(dest)],
        check=True,
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    assert "Overwrote sibling skill(s) in parent registry: agent-browser" in result.stdout
    assert (registry / "agent-browser" / "SKILL.md").read_text(encoding="utf-8").endswith("new version\n")
    assert not (dest / "agent-browser").exists()
    assert (dest / "codex-mythosaur-orchestrator" / "SKILL.md").exists()

    helper_mode = (registry / "agent-browser" / "helper.sh").stat().st_mode
    assert helper_mode & stat.S_IXUSR

    manifest = json.loads((dest / ".export-manifest.json").read_text(encoding="utf-8"))
    assert manifest["overwritten_sibling_skills"] == ["agent-browser"]
    assert manifest["copied_skills"] == ["agent-browser", "codex-mythosaur-orchestrator"]
