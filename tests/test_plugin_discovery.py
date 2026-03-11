from services.mcp_server.plugins import load_tools


def test_load_tools_returns_tools_and_meta():
    tools, meta = load_tools()
    assert isinstance(tools, dict)
    assert isinstance(meta, list)
    assert len(tools) > 0
    assert len(meta) > 0


def test_all_plugins_discovered():
    _, meta = load_tools()
    plugin_ids = {m.plugin_id for m in meta}
    expected = {
        "mythosaur.time",
        "mythosaur.git",
        "mythosaur.search",
        "mythosaur.fetch",
        "mythosaur.transcript",
        "mythosaur.filesystem",
        "mythosaur.browser",
        "mythosaur.google_workspace",
        "mythosaur.pii",
    }
    assert expected == plugin_ids


def test_aliases_resolve_to_same_tool():
    tools, _ = load_tools()
    if "osaurus.current_time" in tools:
        assert tools["osaurus.current_time"] is tools["current_time"]


def test_plugin_meta_has_correct_counts():
    _, meta = load_tools()
    for m in meta:
        assert m.tool_count == len(m.tool_names)
        assert m.tool_count > 0
