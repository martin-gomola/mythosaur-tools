import asyncio

from services.mcp_server.plugins.search_tools import get_tools


def _tool(name: str):
    for t in get_tools():
        if t.name == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_search_missing_query():
    payload = _run(_tool("search").handler({}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_query"


def test_search_no_searxng_url(monkeypatch):
    monkeypatch.delenv("MYTHOSAUR_TOOLS_SEARXNG_URL", raising=False)
    payload = _run(_tool("search").handler({"query": "test"}))
    assert payload["status"] == "error"
    assert "not configured" in payload["error"]["message"]


def test_search_news_missing_query():
    payload = _run(_tool("search_news").handler({}))
    assert payload["status"] == "error"


def test_search_images_missing_query():
    payload = _run(_tool("search_images").handler({}))
    assert payload["status"] == "error"


def test_all_search_tools_are_async():
    for tool in get_tools():
        assert tool.is_async is True, f"{tool.name} should be async"


def test_search_max_results_bounds():
    payload = _run(_tool("search").handler({"query": "test", "max_results": 999}))
    assert payload["status"] == "error"
