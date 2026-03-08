import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_API_KEY", "test-key-123")
    monkeypatch.setenv("MYTHOSAUR_TOOLS_RATE_LIMIT", "0")


@pytest.fixture
def client():
    from services.mcp_server.app import app
    return TestClient(app)


def _auth():
    return {"Authorization": "Bearer test-key-123"}


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


class TestRateLimiting:
    def test_rate_limit_enforced(self, monkeypatch):
        monkeypatch.setenv("MYTHOSAUR_TOOLS_API_KEY", "test-key-123")
        monkeypatch.setenv("MYTHOSAUR_TOOLS_RATE_LIMIT", "3")

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
