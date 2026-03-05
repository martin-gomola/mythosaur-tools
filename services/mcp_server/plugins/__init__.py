from __future__ import annotations

from .browser_tools import get_tools as browser_tools
from .common import ToolDef
from .fetch_tools import get_tools as fetch_tools
from .filesystem_tools import get_tools as filesystem_tools
from .git_tools import get_tools as git_tools
from .search_tools import get_tools as search_tools
from .time_tools import get_tools as time_tools


def load_tools() -> dict[str, ToolDef]:
    tools: dict[str, ToolDef] = {}
    for provider in [
        time_tools,
        git_tools,
        browser_tools,
        fetch_tools,
        search_tools,
        filesystem_tools,
    ]:
        for tool in provider():
            tools[tool.name] = tool
            for alias in tool.aliases or []:
                tools[alias] = tool
    return tools
