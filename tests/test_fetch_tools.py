import asyncio
from pathlib import Path

import pytest

from services.mcp_server.plugins.fetch_tools import get_tools


def _tool(name: str):
    for t in get_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_fetch_missing_url():
    payload = _run(_tool("fetch").handler({}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_url"


def test_fetch_json_missing_url():
    payload = _run(_tool("fetch_json").handler({}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_url"


def test_fetch_html_missing_url():
    payload = _run(_tool("fetch_html").handler({}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_url"


def test_download_missing_input():
    payload = _run(_tool("download").handler({}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_input"


def test_download_path_escape(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    payload = _run(_tool("download").handler({"url": "http://example.com/f", "path": "../../etc/passwd"}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "invalid_path"


def test_download_exists_guard(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "existing.txt").write_text("data")
    payload = _run(_tool("download").handler({
        "url": "http://example.com/f",
        "path": "existing.txt",
        "overwrite": False,
    }))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "exists"


def test_fetch_invalid_url():
    payload = _run(_tool("fetch").handler({"url": "not-a-url"}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "fetch_failed"


def test_all_fetch_tools_are_async():
    for tool in get_tools():
        assert tool.is_async is True, f"{tool.name} should be async"
