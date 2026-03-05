from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from typing import Any

from .common import ToolDef

logger = logging.getLogger(__name__)


@dataclass
class PluginMeta:
    plugin_id: str
    tool_count: int
    tool_names: list[str]


def load_tools() -> tuple[dict[str, ToolDef], list[PluginMeta]]:
    """Auto-discover *_tools.py modules and aggregate their tools.

    Each module must expose a ``get_tools() -> list[ToolDef]`` function.
    Returns the merged tool dict (name+aliases → ToolDef) and per-plugin metadata.
    """
    tools: dict[str, ToolDef] = {}
    plugins_meta: list[PluginMeta] = []
    seen_plugins: dict[str, list[str]] = {}

    package = __package__ or "plugins"
    pkg_path = __path__

    for finder, module_name, _is_pkg in pkgutil.iter_modules(pkg_path):
        if not module_name.endswith("_tools"):
            continue

        fqn = f"{package}.{module_name}"
        try:
            mod = importlib.import_module(fqn)
        except Exception:
            logger.exception("failed to import plugin module %s", fqn)
            continue

        get_tools_fn = getattr(mod, "get_tools", None)
        if not callable(get_tools_fn):
            logger.warning("module %s has no get_tools() callable, skipping", fqn)
            continue

        try:
            plugin_tools = get_tools_fn()
        except Exception:
            logger.exception("get_tools() failed in %s", fqn)
            continue

        for tool in plugin_tools:
            tools[tool.name] = tool
            for alias in tool.aliases or []:
                tools[alias] = tool

            pid = tool.plugin_id
            seen_plugins.setdefault(pid, []).append(tool.name)

    for pid, names in seen_plugins.items():
        plugins_meta.append(PluginMeta(plugin_id=pid, tool_count=len(names), tool_names=names))

    logger.info(
        "loaded %d tools from %d plugins: %s",
        len({t.name for t in tools.values()}),
        len(plugins_meta),
        [p.plugin_id for p in plugins_meta],
    )
    return tools, plugins_meta
