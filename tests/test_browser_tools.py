import pytest

from services.mcp_server.plugins.browser_tools import get_tools


def _tool(name: str):
    for t in get_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("browser_navigate", {"url": "http://example.com"}),
        ("browser_snapshot", {"session_id": "test"}),
        ("browser_extract_content", {"url": "https://example.com"}),
        ("browser_click", {"session_id": "test", "selector": "#btn"}),
    ],
)
def test_browser_tools_return_disabled_when_browser_is_off(monkeypatch, tool_name, arguments):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "false")
    payload = _tool(tool_name).handler(arguments)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "disabled"


def test_browser_extract_content_returns_normalized_payload(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")

    class _FakePage:
        url = "https://example.com/rendered"

        def goto(self, url: str, wait_until: str, timeout: int):
            self.url = url

        def wait_for_timeout(self, timeout: int):
            return None

        def content(self) -> str:
            return """
            <html>
              <head>
                <title>Rendered Story</title>
                <link rel="canonical" href="/canonical-rendered" />
              </head>
              <body>
                <main>
                  <h1>Browser Content</h1>
                  <p>This text only exists after the page renders in a browser context.</p>
                </main>
              </body>
            </html>
            """

    class _FakeSession:
        session_id = "browser-extract-test"
        page = _FakePage()

    monkeypatch.setattr("services.mcp_server.plugins.browser_tools.BROWSER.get", lambda *args, **kwargs: _FakeSession())
    monkeypatch.setattr("services.mcp_server.plugins.browser_tools.BROWSER.close", lambda session_id: None)

    payload = _tool("browser_extract_content").handler({"url": "https://example.com/rendered"})

    assert payload["status"] == "ok"
    data = payload["data"]
    assert data["source_type"] == "url"
    assert data["title"] == "Rendered Story"
    assert data["canonical_url"] == "https://example.com/canonical-rendered"
    assert "Browser Content" in data["text"]
    assert data["metadata"]["browser_used"] is True


@pytest.mark.parametrize(
    ("tool_name", "arguments", "error_code"),
    [
        ("browser_navigate", {}, "missing_url"),
        ("browser_extract_content", {}, "missing_url"),
        ("browser_click", {"session_id": "x"}, "missing_selector"),
        ("browser_type", {"session_id": "x", "text": "hello"}, "missing_selector"),
        ("browser_wait_for", {"session_id": "x"}, "missing_selector"),
        ("browser_press_key", {"session_id": "x"}, "missing_key"),
        ("browser_execute_script", {"session_id": "x"}, "missing_script"),
        ("browser_select", {"session_id": "x", "value": "opt"}, "missing_selector"),
    ],
)
def test_browser_tools_validate_required_arguments(monkeypatch, tool_name, arguments, error_code):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")
    payload = _tool(tool_name).handler(arguments)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == error_code


def test_all_browser_tools_registered():
    names = {t.name for t in get_tools()}
    expected = {
        "browser_navigate", "browser_extract_content", "browser_snapshot", "browser_click", "browser_type",
        "browser_select", "browser_hover", "browser_scroll", "browser_press_key",
        "browser_wait_for", "browser_screenshot", "browser_execute_script",
    }
    assert expected == names


def test_all_browser_tools_have_aliases():
    for tool in get_tools():
        assert tool.aliases, f"{tool.name} missing aliases"
        assert any(a.startswith("osaurus.") for a in tool.aliases), f"{tool.name} missing osaurus alias"
