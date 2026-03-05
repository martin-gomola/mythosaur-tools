from __future__ import annotations

import os

import httpx

from .common import ToolDef, err, now_ms, ok, parse_int


async def _searx_search(query: str, categories: str, max_results: int) -> tuple[list[dict], str]:
    base_url = (os.getenv("MYTHOSAUR_TOOLS_SEARXNG_URL") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("MYTHOSAUR_TOOLS_SEARXNG_URL is not configured")

    token = (os.getenv("MYTHOSAUR_TOOLS_SEARXNG_TOKEN") or "").strip()
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base_url}/search",
            params={
                "q": query,
                "format": "json",
                "categories": categories,
                "language": "en-US",
                "safesearch": "1",
            },
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()

    payload = resp.json()
    results = payload.get("results") or []
    clipped = []
    for item in results[:max_results]:
        clipped.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("content") or item.get("snippet") or "").strip(),
                "engine": str(item.get("engine") or ""),
            }
        )
    return clipped, base_url


async def _search(arguments: dict) -> dict:
    return await _run_search("search", arguments, "general")


async def _search_news(arguments: dict) -> dict:
    return await _run_search("search_news", arguments, "news")


async def _search_images(arguments: dict) -> dict:
    return await _run_search("search_images", arguments, "images")


async def _run_search(tool_name: str, arguments: dict, categories: str) -> dict:
    started = now_ms()
    query = (arguments.get("query") or "").strip()
    if not query:
        return err(tool_name, "missing_query", "query is required", "search", started)
    max_results = parse_int(arguments.get("max_results"), default=5, minimum=1, maximum=10)
    try:
        results, source = await _searx_search(query, categories, max_results)
    except Exception as exc:
        return err(tool_name, "search_failed", str(exc), "search", started)

    return ok(
        tool_name,
        {
            "query": query,
            "categories": categories,
            "results": results,
            "source": source,
        },
        "search",
        started,
    )


def get_tools() -> list[ToolDef]:
    base_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "required": ["query"],
    }

    return [
        ToolDef(
            name="search",
            plugin_id="mythosaur.search",
            description="Web search (general).",
            input_schema=base_schema,
            handler=_search,
            aliases=["osaurus.search"],
            is_async=True,
        ),
        ToolDef(
            name="search_news",
            plugin_id="mythosaur.search",
            description="News search.",
            input_schema=base_schema,
            handler=_search_news,
            aliases=["osaurus.search_news"],
            is_async=True,
        ),
        ToolDef(
            name="search_images",
            plugin_id="mythosaur.search",
            description="Image search.",
            input_schema=base_schema,
            handler=_search_images,
            aliases=["osaurus.search_images"],
            is_async=True,
        ),
    ]
