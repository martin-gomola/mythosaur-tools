from __future__ import annotations

from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

from .common import JsonDict, ToolDef, err, now_ms, ok

PLUGIN_ID: Final = "mythosaur.time"
PLUGIN_SOURCE: Final = "time"
DEFAULT_TIMEZONE: Final = "UTC"
DEFAULT_FORMAT: Final = "%Y-%m-%d %H:%M:%S"


def _timezone(tool_name: str, timezone_name: str, started: int) -> ZoneInfo | JsonDict:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return err(tool_name, "invalid_timezone", f"Unknown timezone: {timezone_name}", PLUGIN_SOURCE, started)


def _current_time(args: JsonDict) -> JsonDict:
    started = now_ms()
    timezone_name = str(args.get("timezone") or DEFAULT_TIMEZONE).strip()
    timezone = _timezone("current_time", timezone_name, started)
    if isinstance(timezone, dict):
        return timezone

    now = datetime.now(timezone)
    return ok(
        "current_time",
        {
            "timezone": timezone_name,
            "iso": now.isoformat(),
            "human": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        },
        PLUGIN_SOURCE,
        started,
    )


def _format_date(args: JsonDict) -> JsonDict:
    started = now_ms()
    value = str(args.get("input") or "").strip()
    date_format = str(args.get("format") or DEFAULT_FORMAT).strip() or DEFAULT_FORMAT
    timezone_name = str(args.get("timezone") or DEFAULT_TIMEZONE).strip()

    if not value:
        return err("format_date", "missing_input", "input is required", PLUGIN_SOURCE, started)

    try:
        dt = date_parser.parse(value)
    except Exception:
        return err("format_date", "invalid_input", "input is not a valid date/time", PLUGIN_SOURCE, started)

    timezone = _timezone("format_date", timezone_name, started)
    if isinstance(timezone, dict):
        return timezone

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone)
    else:
        dt = dt.astimezone(timezone)

    return ok(
        "format_date",
        {
            "timezone": timezone_name,
            "format": date_format,
            "formatted": dt.strftime(date_format),
            "iso": dt.isoformat(),
        },
        PLUGIN_SOURCE,
        started,
    )


def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="current_time",
            plugin_id=PLUGIN_ID,
            description="Return current date/time in a timezone.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "timezone": {"type": "string", "description": "IANA timezone, e.g. Europe/Bratislava"}
                },
                "required": [],
            },
            handler=_current_time,
            aliases=["osaurus.current_time"],
        ),
        ToolDef(
            name="format_date",
            plugin_id=PLUGIN_ID,
            description="Format provided date/time input.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "input": {"type": "string"},
                    "format": {"type": "string"},
                    "timezone": {"type": "string"},
                },
                "required": ["input"],
            },
            handler=_format_date,
            aliases=["osaurus.format_date"],
        ),
    ]
