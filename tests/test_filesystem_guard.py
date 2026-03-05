import os
from pathlib import Path

from services.mcp_server.plugins.filesystem_tools import get_tools


def _tool(name: str):
    for t in get_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def test_read_file_workspace_guard(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    payload = _tool("read_file").handler({"path": "../outside.txt"})
    assert payload["status"] == "error"


def test_write_file_blocked_in_readonly(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("MYTHOSAUR_TOOLS_PROFILE", "readonly")
    payload = _tool("write_file").handler({"path": "a.txt", "content": "x"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "forbidden"
