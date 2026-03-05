from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

from .common import ToolDef, err, now_ms, ok


def _current_time(args: dict) -> dict:
    started = now_ms()
    tz_name = (args.get("timezone") or "UTC").strip()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        return err("current_time", "invalid_timezone", f"Unknown timezone: {tz_name}", "time", started)

    now = datetime.now(tz)
    return ok(
        "current_time",
        {
            "timezone": tz_name,
            "iso": now.isoformat(),
            "human": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        },
        "time",
        started,
    )


def _format_date(args: dict) -> dict:
    started = now_ms()
    value = (args.get("input") or "").strip()
    fmt = (args.get("format") or "%Y-%m-%d %H:%M:%S").strip() or "%Y-%m-%d %H:%M:%S"
    tz_name = (args.get("timezone") or "UTC").strip()

    if not value:
        return err("format_date", "missing_input", "input is required", "time", started)

    try:
        dt = date_parser.parse(value)
    except Exception:
        return err("format_date", "invalid_input", "input is not a valid date/time", "time", started)

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        return err("format_date", "invalid_timezone", f"Unknown timezone: {tz_name}", "time", started)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)

    return ok(
        "format_date",
        {
            "timezone": tz_name,
            "format": fmt,
            "formatted": dt.strftime(fmt),
            "iso": dt.isoformat(),
        },
        "time",
        started,
    )


def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="current_time",
            plugin_id="mythosaur.time",
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
            plugin_id="mythosaur.time",
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
