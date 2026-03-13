import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from services.mcp_server.plugins import load_tools
from services.mcp_server.plugins.search_tools import get_tools as get_search_tools
from services.mcp_server.plugins.time_tools import get_tools as get_time_tools


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("MT_API_KEY", "test-key-123")
    monkeypatch.setenv("MT_RATE_LIMIT", "0")


@pytest.fixture
def client():
    from importlib import reload
    import services.mcp_server.app as app_module

    reload(app_module)
    return TestClient(app_module.app)


def _auth():
    return {"Authorization": "Bearer test-key-123"}


def _reload_client(monkeypatch, *, default_consumer: str | None = None) -> TestClient:
    monkeypatch.setenv("MT_API_KEY", "test-key-123")
    monkeypatch.setenv("MT_RATE_LIMIT", "0")
    if default_consumer is None:
        monkeypatch.delenv("MT_DEFAULT_CONSUMER", raising=False)
    else:
        monkeypatch.setenv("MT_DEFAULT_CONSUMER", default_consumer)

    from importlib import reload
    import services.mcp_server.app as app_module

    reload(app_module)
    return TestClient(app_module.app)


def _assert_codex_catalog(plugin_ids: set[str]) -> None:
    assert "mythosaur.search" in plugin_ids
    assert "mythosaur.fetch" in plugin_ids
    assert "mythosaur.google_workspace" in plugin_ids
    assert "mythosaur.filesystem" not in plugin_ids
    assert "mythosaur.git" not in plugin_ids


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _search_tool(name: str):
    for t in get_search_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def _time_tool(name: str):
    for t in get_time_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


class TestHealthz:
    def test_returns_ok(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"]
        assert body["protocol_version"]

    def test_includes_plugins(self, client):
        resp = client.get("/healthz")
        body = resp.json()
        assert "plugins" in body
        assert len(body["plugins"]) > 0
        plugin_ids = {p["plugin_id"] for p in body["plugins"]}
        assert "mythosaur.time" in plugin_ids

    def test_search_plugin_shows_config(self, client):
        resp = client.get("/healthz")
        body = resp.json()
        search_plugin = next(p for p in body["plugins"] if p["plugin_id"] == "mythosaur.search")
        assert "searxng_configured" in search_plugin

    def test_browser_plugin_shows_config(self, client):
        resp = client.get("/healthz")
        body = resp.json()
        browser_plugin = next(p for p in body["plugins"] if p["plugin_id"] == "mythosaur.browser")
        assert "browser_enabled" in browser_plugin

    def test_google_plugin_shows_capabilities(self, client):
        resp = client.get("/healthz")
        body = resp.json()
        google_plugin = next(p for p in body["plugins"] if p["plugin_id"] == "mythosaur.google_workspace")
        assert "capabilities" in google_plugin
        assert "gmail_send" in google_plugin["capabilities"]
        assert "auth" in google_plugin
        assert "granted_scopes" in google_plugin["auth"]
        assert "service_checks" in google_plugin["auth"]
        assert "maps" in google_plugin["auth"]["service_checks"]

    def test_reports_default_consumer(self, client):
        resp = client.get("/healthz")
        body = resp.json()
        assert body["default_consumer"] == "default"
        assert "codex" in body["supported_consumers"]

    def test_legacy_env_aliases_still_work(self, monkeypatch):
        monkeypatch.delenv("MT_API_KEY", raising=False)
        monkeypatch.delenv("MT_RATE_LIMIT", raising=False)
        monkeypatch.setenv("MYTHOSAUR_TOOLS_API_KEY", "legacy-key")
        monkeypatch.setenv("MYTHOSAUR_TOOLS_RATE_LIMIT", "0")

        from importlib import reload
        import services.mcp_server.app as app_module

        reload(app_module)
        client = TestClient(app_module.app)
        resp = client.post(
            "/mcp",
            headers={"Authorization": "Bearer legacy-key", "Content-Type": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"},
                },
            },
        )

        assert resp.status_code == 200


class TestSchema:
    def test_returns_tools(self, client):
        resp = client.get("/schema")
        assert resp.status_code == 200
        body = resp.json()
        assert "version" in body
        assert "tools" in body
        assert len(body["tools"]) > 0

    def test_tool_has_required_fields(self, client):
        resp = client.get("/schema")
        tool = resp.json()["tools"][0]
        assert "name" in tool
        assert "plugin_id" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert "aliases" in tool

    def test_tools_are_sorted(self, client):
        resp = client.get("/schema")
        names = [t["name"] for t in resp.json()["tools"]]
        assert names == sorted(names)

    @pytest.mark.parametrize(
        ("query", "headers", "default_consumer"),
        [
            ("?consumer=codex", None, None),
            ("", {"X-Mythosaur-Consumer": "codex"}, None),
            ("", None, "codex"),
        ],
    )
    def test_schema_consumer_filter_flow(self, monkeypatch, query, headers, default_consumer):
        flow_client = _reload_client(monkeypatch, default_consumer=default_consumer)
        resp = flow_client.get(f"/schema{query}", headers=headers or {})
        assert resp.status_code == 200
        _assert_codex_catalog({t["plugin_id"] for t in resp.json()["tools"]})

    def test_schema_invalid_consumer_returns_400(self, client):
        resp = client.get("/schema?consumer=unknown")
        assert resp.status_code == 400

    def test_tools_list_consumer_intersects_plugin_filter(self, client):
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {
                    "consumer": "codex",
                    "plugins": "mythosaur.search,mythosaur.fetch,mythosaur.git",
                },
            },
            headers=_auth(),
        )
        body = resp.json()
        tools = body["result"]["tools"]
        plugin_ids = {t["annotations"]["pluginId"] for t in tools}
        assert plugin_ids == {"mythosaur.search", "mythosaur.fetch"}


class TestMcpAuth:
    def test_missing_auth(self, client):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert resp.status_code == 401

    def test_wrong_token(self, client):
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401


class TestMcpInitialize:
    def test_initialize(self, client):
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers=_auth(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["serverInfo"]["name"] == "mythosaur-tools"
        assert "Mcp-Session-Id" in resp.headers


class TestMcpToolsList:
    def test_list_all(self, client):
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=_auth(),
        )
        body = resp.json()
        tools = body["result"]["tools"]
        assert len(tools) > 0
        names = {t["name"] for t in tools}
        assert "current_time" in names
        assert "scan_pii_staged" in names

    def test_filter_by_plugin(self, client):
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"plugins": "mythosaur.time"}},
            headers=_auth(),
        )
        body = resp.json()
        tools = body["result"]["tools"]
        plugin_ids = {t["annotations"]["pluginId"] for t in tools}
        assert plugin_ids == {"mythosaur.time"}

    @pytest.mark.parametrize(
        ("params", "headers", "default_consumer"),
        [
            ({"consumer": "codex"}, None, None),
            ({}, {"X-Mythosaur-Consumer": "codex"}, None),
            ({}, None, "codex"),
        ],
    )
    def test_filter_by_consumer_flow(self, monkeypatch, params, headers, default_consumer):
        flow_client = _reload_client(monkeypatch, default_consumer=default_consumer)
        resp = flow_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": params},
            headers={**_auth(), **(headers or {})},
        )
        body = resp.json()
        tools = body["result"]["tools"]
        _assert_codex_catalog({t["annotations"]["pluginId"] for t in tools})

    def test_invalid_consumer_returns_error(self, client):
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"consumer": "unknown"}},
            headers=_auth(),
        )
        body = resp.json()
        assert body["error"]["code"] == -32602


class TestMcpToolsCall:
    def test_call_current_time(self, client):
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "current_time", "arguments": {"timezone": "UTC"}},
            },
            headers=_auth(),
        )
        body = resp.json()
        structured = body["result"]["structuredContent"]
        assert structured["status"] == "ok"
        assert structured["tool"] == "current_time"
        assert structured["meta"]["duration_ms"] >= 0

    def test_unknown_tool(self, client):
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            },
            headers=_auth(),
        )
        body = resp.json()
        assert body["error"]["code"] == -32601

    def test_invalid_arguments(self, client):
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "current_time", "arguments": "not-an-object"},
            },
            headers=_auth(),
        )
        body = resp.json()
        assert body["error"]["code"] == -32602

    def test_unsupported_method(self, client):
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 5, "method": "bogus/method"},
            headers=_auth(),
        )
        body = resp.json()
        assert body["error"]["code"] == -32601

    def test_alias_resolves(self, client):
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "osaurus.current_time", "arguments": {"timezone": "UTC"}},
            },
            headers=_auth(),
        )
        body = resp.json()
        assert body["result"]["structuredContent"]["status"] == "ok"

    def test_usage_summary_logs_on_first_call(self, client, caplog):
        caplog.set_level("INFO")

        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "current_time", "arguments": {"timezone": "UTC"}},
            },
            headers=_auth(),
        )

        assert resp.status_code == 200
        assert "mcp.usage total_calls=1 unique_tools=1 top_tools=current_time:1" in caplog.text

    def test_usage_summary_logs_after_configured_call_interval(self, monkeypatch, caplog):
        monkeypatch.setenv("MT_API_KEY", "test-key-123")
        monkeypatch.setenv("MT_RATE_LIMIT", "0")
        monkeypatch.setenv("MT_USAGE_LOG_EVERY", "2")
        monkeypatch.setenv("MT_USAGE_LOG_INTERVAL_SEC", "3600")

        from importlib import reload
        import services.mcp_server.app as app_module

        reload(app_module)
        rate_client = TestClient(app_module.app)
        caplog.set_level("INFO")

        for request_id in (8, 9):
            resp = rate_client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {"name": "current_time", "arguments": {"timezone": "UTC"}},
                },
                headers=_auth(),
            )
            assert resp.status_code == 200

        usage_lines = [line for line in caplog.messages if line.startswith("mcp.usage ")]
        assert len(usage_lines) == 2
        assert "total_calls=2" in usage_lines[-1]
        assert "top_tools=current_time:2" in usage_lines[-1]


class TestRateLimiting:
    def test_rate_limit_enforced(self, monkeypatch):
        monkeypatch.setenv("MT_API_KEY", "test-key-123")
        monkeypatch.setenv("MT_RATE_LIMIT", "3")

        from importlib import reload
        import services.mcp_server.app as app_module
        reload(app_module)
        rate_client = TestClient(app_module.app)

        for _ in range(3):
            resp = rate_client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                headers=_auth(),
            )
            assert resp.status_code == 200

        resp = rate_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers=_auth(),
        )
        assert resp.status_code == 429


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
    for meta_item in meta:
        assert meta_item.tool_count == len(meta_item.tool_names)
        assert meta_item.tool_count > 0


def test_search_missing_query():
    payload = _run(_search_tool("search").handler({}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_query"


def test_search_no_searxng_url(monkeypatch):
    monkeypatch.delenv("MT_SEARXNG_URL", raising=False)
    payload = _run(_search_tool("search").handler({"query": "test"}))
    assert payload["status"] == "error"
    assert "not configured" in payload["error"]["message"]


def test_search_news_missing_query():
    payload = _run(_search_tool("search_news").handler({}))
    assert payload["status"] == "error"


def test_search_images_missing_query():
    payload = _run(_search_tool("search_images").handler({}))
    assert payload["status"] == "error"


def test_all_search_tools_are_async():
    for tool in get_search_tools():
        assert tool.is_async is True, f"{tool.name} should be async"


def test_search_max_results_bounds():
    payload = _run(_search_tool("search").handler({"query": "test", "max_results": 999}))
    assert payload["status"] == "error"


def test_current_time_ok():
    payload = _time_tool("current_time").handler({"timezone": "UTC"})
    assert payload["status"] == "ok"
    assert payload["tool"] == "current_time"
    assert "iso" in payload["data"]


def test_format_date_error_missing_input():
    payload = _time_tool("format_date").handler({})
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_input"
