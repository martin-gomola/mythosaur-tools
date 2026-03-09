"""Google Workspace MCP tools subpackage.

Imports domain-specific handlers from internal modules and exposes
get_tools() plus google_capabilities / google_auth_status for the plugin loader and app.
"""

from __future__ import annotations

from ..common import ToolDef

from ._auth import google_auth_status, google_capabilities
from ._calendar import get_tools as _calendar_tools
from ._gmail import get_tools as _gmail_tools
from ._drive import get_tools as _drive_tools
from ._sheets import get_tools as _sheets_tools
from ._docs import get_tools as _docs_tools
from ._photos import get_tools as _photos_tools
from ._maps import get_tools as _maps_tools


def get_tools() -> list[ToolDef]:
    return [
        *_calendar_tools(),
        *_gmail_tools(),
        *_drive_tools(),
        *_sheets_tools(),
        *_docs_tools(),
        *_photos_tools(),
        *_maps_tools(),
    ]
