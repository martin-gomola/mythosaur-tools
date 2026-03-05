from services.mcp_server.plugins.time_tools import get_tools


def _tool(name: str):
    for t in get_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def test_current_time_ok():
    payload = _tool("current_time").handler({"timezone": "UTC"})
    assert payload["status"] == "ok"
    assert payload["tool"] == "current_time"
    assert "iso" in payload["data"]


def test_format_date_error_missing_input():
    payload = _tool("format_date").handler({})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_input"
