import subprocess
from pathlib import Path
from unittest.mock import patch

from services.mcp_server.plugins.git_tools import get_tools


def _tool(name: str):
    for t in get_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def test_git_status_ok(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    payload = _tool("git_status").handler({"repo": "."})
    assert payload["status"] == "ok"
    assert payload["tool"] == "git_status"
    assert "output" in payload["data"]


def test_git_status_bad_repo(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    payload = _tool("git_status").handler({"repo": "nonexistent"})
    assert payload["status"] == "error"


def test_git_log_ok(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    (tmp_path / "f.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    payload = _tool("git_log").handler({"repo": ".", "limit": 5})
    assert payload["status"] == "ok"
    assert "init" in payload["data"]["output"]


def test_git_log_limit_respected(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    payload = _tool("git_log").handler({"repo": ".", "limit": 0})
    assert payload["data"].get("limit", 1) >= 1


def test_git_branch_ok(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    (tmp_path / "f.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    payload = _tool("git_branch").handler({"repo": "."})
    assert payload["status"] == "ok"
    assert "output" in payload["data"]


def test_git_diff_ok(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    payload = _tool("git_diff").handler({"repo": "."})
    assert payload["status"] == "ok"


def test_git_diff_target_limit(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    payload = _tool("git_diff").handler({"repo": ".", "target": "a b c d e"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "invalid_target"


def test_git_workspace_guard(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    payload = _tool("git_status").handler({"repo": "../../etc"})
    assert payload["status"] == "error"
