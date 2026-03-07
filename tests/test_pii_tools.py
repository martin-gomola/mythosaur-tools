import subprocess
from pathlib import Path

from services.mcp_server.plugins.pii_tools import get_tools


def _tool(name: str):
    return next(t for t in get_tools() if t.name == name)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)


def test_scan_pii_staged_detects_home_path(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    home_path = "/".join(["", "Users", "example", "dev", "private"])
    (repo / "notes.md").write_text(f"Path: {home_path}\n", encoding="utf-8")
    subprocess.run(["git", "add", "notes.md"], cwd=repo, check=True)
    monkeypatch.setenv("MYTHOSAUR_TOOLS_PII_ROOT", str(tmp_path))

    payload = _tool("scan_pii_staged").handler({"repo": "repo"})

    assert payload["status"] == "ok"
    assert payload["data"]["blocking"] is True
    assert payload["data"]["findings_count"] == 1
    finding = payload["data"]["findings"][0]
    assert finding["kind"] == "user_home_path"
    assert finding["path"] == "notes.md"


def test_scan_pii_repo_detects_email(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "README.md").write_text("Contact: owner@example.com\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    monkeypatch.setenv("MYTHOSAUR_TOOLS_PII_ROOT", str(tmp_path))

    payload = _tool("scan_pii_repo").handler({"repo": "repo"})

    assert payload["status"] == "ok"
    assert payload["data"]["blocking"] is True
    assert payload["data"]["findings"][0]["kind"] == "email_address"


def test_install_pii_precommit_hook_writes_hook(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    monkeypatch.setenv("MYTHOSAUR_TOOLS_PII_ROOT", str(tmp_path))
    script_path = tmp_path / "pii_scan.py"
    script_path.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    monkeypatch.setenv("MYTHOSAUR_TOOLS_PII_SCRIPT_PATH", str(script_path))

    payload = _tool("install_pii_precommit_hook").handler({"repo": "repo"})

    assert payload["status"] == "ok"
    hook_path = Path(payload["data"]["hook_path"])
    assert hook_path.exists()
    hook_text = hook_path.read_text(encoding="utf-8")
    assert "Managed by mythosaur-tools PII pre-commit hook" in hook_text
    assert str(script_path) in hook_text


def test_install_pii_precommit_hook_preserves_existing_hook_with_force(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    monkeypatch.setenv("MYTHOSAUR_TOOLS_PII_ROOT", str(tmp_path))
    script_path = tmp_path / "pii_scan.py"
    script_path.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    monkeypatch.setenv("MYTHOSAUR_TOOLS_PII_SCRIPT_PATH", str(script_path))
    hook_dir = repo / ".git" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)
    (hook_dir / "pre-commit").write_text("#!/bin/sh\necho old\n", encoding="utf-8")

    payload = _tool("install_pii_precommit_hook").handler({"repo": "repo", "force": True})

    assert payload["status"] == "ok"
    backup_path = Path(payload["data"]["backup_path"])
    assert backup_path.exists()
    assert "echo old" in backup_path.read_text(encoding="utf-8")


def test_scan_pii_tools_reject_repo_outside_base(monkeypatch, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("MYTHOSAUR_TOOLS_PII_ROOT", str(tmp_path / "base"))

    payload = _tool("scan_pii_repo").handler({"repo": str(outside)})

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "pii_scan_error"
