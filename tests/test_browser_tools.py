from services.mcp_server.plugins.browser_tools import get_tools


def _tool(name: str):
    for t in get_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def test_browser_navigate_disabled(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "false")
    payload = _tool("browser_navigate").handler({"url": "http://example.com"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "disabled"


def test_browser_snapshot_disabled(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "false")
    payload = _tool("browser_snapshot").handler({"session_id": "test"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "disabled"


def test_browser_click_disabled(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "false")
    payload = _tool("browser_click").handler({"session_id": "test", "selector": "#btn"})
    assert payload["status"] == "error"


def test_browser_navigate_missing_url(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")
    payload = _tool("browser_navigate").handler({})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_url"


def test_browser_click_missing_selector(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")
    payload = _tool("browser_click").handler({"session_id": "x"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_selector"


def test_browser_type_missing_selector(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")
    payload = _tool("browser_type").handler({"session_id": "x", "text": "hello"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_selector"


def test_browser_wait_for_missing_selector(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")
    payload = _tool("browser_wait_for").handler({"session_id": "x"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_selector"


def test_browser_press_key_missing_key(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")
    payload = _tool("browser_press_key").handler({"session_id": "x"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_key"


def test_browser_execute_script_missing_script(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")
    payload = _tool("browser_execute_script").handler({"session_id": "x"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_script"


def test_browser_select_missing_selector(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_BROWSER_ENABLED", "true")
    payload = _tool("browser_select").handler({"session_id": "x", "value": "opt"})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_selector"


def test_all_browser_tools_registered():
    names = {t.name for t in get_tools()}
    expected = {
        "browser_navigate", "browser_snapshot", "browser_click", "browser_type",
        "browser_select", "browser_hover", "browser_scroll", "browser_press_key",
        "browser_wait_for", "browser_screenshot", "browser_execute_script",
    }
    assert expected == names


def test_all_browser_tools_have_aliases():
    for tool in get_tools():
        assert tool.aliases, f"{tool.name} missing aliases"
        assert any(a.startswith("osaurus.") for a in tool.aliases), f"{tool.name} missing osaurus alias"
