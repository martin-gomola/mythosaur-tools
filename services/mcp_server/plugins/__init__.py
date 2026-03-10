from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Callable, Final

from .common import ToolDef

logger = logging.getLogger(__name__)
PLUGIN_MODULE_SUFFIX: Final = "_tools"
DEFAULT_PACKAGE_NAME: Final = "plugins"


@dataclass
class PluginMeta:
    plugin_id: str
    tool_count: int
    tool_names: list[str]


def _plugin_module_names() -> list[str]:
    package_path = __path__
    return sorted(
        module_name
        for _, module_name, _ in pkgutil.iter_modules(package_path)
        if module_name.endswith(PLUGIN_MODULE_SUFFIX)
    )


def _import_plugin_module(package_name: str, module_name: str) -> ModuleType | None:
    module_fqn = f"{package_name}.{module_name}"
    try:
        return importlib.import_module(module_fqn)
    except Exception:
        logger.exception("failed to import plugin module %s", module_fqn)
        return None


def _plugin_tools(module: ModuleType, package_name: str) -> list[ToolDef]:
    module_fqn = f"{package_name}.{module.__name__.split('.')[-1]}"
    get_tools_fn = getattr(module, "get_tools", None)
    if not callable(get_tools_fn):
        logger.warning("module %s has no get_tools() callable, skipping", module_fqn)
        return []

    try:
        return get_tools_fn()
    except Exception:
        logger.exception("get_tools() failed in %s", module_fqn)
        return []


def _register_tool(tool_map: dict[str, ToolDef], tool: ToolDef) -> None:
    tool_map[tool.name] = tool
    for alias in tool.aliases or []:
        tool_map[alias] = tool


def _plugin_metadata(seen_plugins: dict[str, list[str]]) -> list[PluginMeta]:
    return [
        PluginMeta(plugin_id=plugin_id, tool_count=len(names), tool_names=names)
        for plugin_id, names in seen_plugins.items()
    ]


def load_tools() -> tuple[dict[str, ToolDef], list[PluginMeta]]:
    """Auto-discover *_tools.py modules and aggregate their tools.

    Each module must expose a ``get_tools() -> list[ToolDef]`` function.
    Returns the merged tool dict (name+aliases → ToolDef) and per-plugin metadata.
    """
    tools: dict[str, ToolDef] = {}
    plugins_meta: list[PluginMeta] = []
    seen_plugins: dict[str, list[str]] = {}

    package_name = __package__ or DEFAULT_PACKAGE_NAME

    for module_name in _plugin_module_names():
        module = _import_plugin_module(package_name, module_name)
        if module is None:
            continue

        for tool in _plugin_tools(module, package_name):
            _register_tool(tools, tool)
            seen_plugins.setdefault(tool.plugin_id, []).append(tool.name)

    plugins_meta = _plugin_metadata(seen_plugins)

    logger.info(
        "loaded %d tools from %d plugins: %s",
        len({t.name for t in tools.values()}),
        len(plugins_meta),
        [p.plugin_id for p in plugins_meta],
    )
    return tools, plugins_meta
