from __future__ import annotations

import os
from typing import Final

import httpx

from .common import JsonDict, ToolDef, err, now_ms, ok, parse_int

PLUGIN_ID: Final = "mythosaur.search"
SEARCH_TIMEOUT_SECONDS: Final = 15


def _searx_base_url() -> str:
    base_url = (os.getenv("MYTHOSAUR_TOOLS_SEARXNG_URL") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("MYTHOSAUR_TOOLS_SEARXNG_URL is not configured")
    return base_url


def _searx_headers() -> dict[str, str]:
    token = (os.getenv("MYTHOSAUR_TOOLS_SEARXNG_TOKEN") or "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _normalized_search_result(item: JsonDict) -> JsonDict:
    return {
        "title": str(item.get("title") or ""),
        "url": str(item.get("url") or ""),
        "snippet": str(item.get("content") or item.get("snippet") or "").strip(),
        "engine": str(item.get("engine") or ""),
    }


async def _searx_search(query: str, categories: str, max_results: int) -> tuple[list[JsonDict], str]:
    base_url = _searx_base_url()
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
            headers=_searx_headers(),
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()

    payload = resp.json()
    results = payload.get("results") or []
    return [_normalized_search_result(item) for item in results[:max_results]], base_url


async def _search(arguments: JsonDict) -> JsonDict:
    return await _run_search("search", arguments, "general")


async def _search_news(arguments: JsonDict) -> JsonDict:
    return await _run_search("search_news", arguments, "news")


async def _search_images(arguments: JsonDict) -> JsonDict:
    return await _run_search("search_images", arguments, "images")


async def _run_search(tool_name: str, arguments: JsonDict, categories: str) -> JsonDict:
    started = now_ms()
    query = str(arguments.get("query") or "").strip()
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
            plugin_id=PLUGIN_ID,
            description="Web search (general).",
            input_schema=base_schema,
            handler=_search,
            aliases=["osaurus.search"],
            is_async=True,
        ),
        ToolDef(
            name="search_news",
            plugin_id=PLUGIN_ID,
            description="News search.",
            input_schema=base_schema,
            handler=_search_news,
            aliases=["osaurus.search_news"],
            is_async=True,
        ),
        ToolDef(
            name="search_images",
            plugin_id=PLUGIN_ID,
            description="Image search.",
            input_schema=base_schema,
            handler=_search_images,
            aliases=["osaurus.search_images"],
            is_async=True,
        ),
    ]
