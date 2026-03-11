import asyncio
from pathlib import Path

import pytest

import services.mcp_server.plugins.fetch_tools as fetch_tools
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


def test_extract_content_missing_url():
    payload = _run(_tool("extract_content").handler({}))
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
    assert payload["error"]["code"] == "blocked_url"


def test_extract_content_returns_normalized_html(monkeypatch):
    async def _fake_fetch_core(url: str, headers: dict[str, str], timeout: int, max_bytes: int):
        html = b"""
        <html>
          <head>
            <title>Example Story</title>
            <link rel="canonical" href="/canonical-story" />
          </head>
              <body>
                <article>
                  <h1>Launch Notes</h1>
                  <p>The service shipped a cleaner extraction contract that keeps summary inputs narrow, auditable, and easy to test across clients without leaning on a shell wrapper. The service shipped a cleaner extraction contract that keeps summary inputs narrow, auditable, and easy to test across clients without leaning on a shell wrapper.</p>
                  <p>It also preserves title and canonical URL data while clipping oversized content before it reaches the local summarizer, which keeps prompts bounded and predictable for a fast runtime path. It also preserves title and canonical URL data while clipping oversized content before it reaches the local summarizer, which keeps prompts bounded and predictable for a fast runtime path.</p>
                  <p>This final paragraph exists only to push the extracted article well beyond the clipping threshold used in the test. This final paragraph exists only to push the extracted article well beyond the clipping threshold used in the test.</p>
                </article>
              </body>
            </html>
            """
        return 200, {"content-type": "text/html; charset=utf-8"}, html, url

    monkeypatch.setattr(fetch_tools, "_fetch_core", _fake_fetch_core)

    payload = _run(_tool("extract_content").handler({"url": "https://example.com/story", "max_chars": 500}))

    assert payload["status"] == "ok"
    data = payload["data"]
    assert data["source_type"] == "url"
    assert data["title"] == "Example Story"
    assert data["canonical_url"] == "https://example.com/canonical-story"
    assert data["truncated"] is True
    assert "Launch Notes" in data["text"]
    assert data["metadata"]["status_code"] == 200
    assert data["metadata"]["content_type"] == "text/html; charset=utf-8"


@pytest.mark.parametrize("url,tool_name", [
    ("file:///etc/passwd", "fetch"),
    ("ftp://internal.host/data", "fetch"),
    ("http://localhost/admin", "fetch"),
    ("http://127.0.0.1/admin", "fetch"),
    ("http://10.0.0.1/internal", "fetch"),
    ("http://192.168.1.1/admin", "fetch_json"),
    ("http://169.254.169.254/metadata", "fetch_html"),
])
def test_fetch_ssrf_blocked(url, tool_name):
    payload = _run(_tool(tool_name).handler({"url": url}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "blocked_url"


def test_download_ssrf_blocked(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    payload = _run(_tool("download").handler({"url": "http://127.0.0.1/secret", "path": "out.txt"}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "blocked_url"


def test_all_fetch_tools_are_async():
    for tool in get_tools():
        assert tool.is_async is True, f"{tool.name} should be async"
