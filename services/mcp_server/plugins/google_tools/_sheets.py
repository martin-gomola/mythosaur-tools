from __future__ import annotations

from typing import Any

from . import _auth
from ..common import ToolDef, err, now_ms, ok


def _sheets_read_range(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _auth._capability_guard("google_sheets_read_range", "sheets_read", started)
    if blocked:
        return blocked
    spreadsheet_id = (args.get("spreadsheet_id") or "").strip()
    range_name = (args.get("range") or "").strip()
    if not spreadsheet_id or not range_name:
        return err(
            "google_sheets_read_range",
            "missing_args",
            "spreadsheet_id and range are required",
            "google",
            started,
        )

    try:
        service = _auth._build_service("sheets", "v4", _auth.SHEETS_SCOPES)
        payload = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    except Exception as exc:
        return err("google_sheets_read_range", "sheets_failed", _auth._safe_error_msg(exc), "google", started)

    return ok(
        "google_sheets_read_range",
        {
            "spreadsheet_id": spreadsheet_id,
            "range": range_name,
            "major_dimension": payload.get("majorDimension", "ROWS"),
            "values": payload.get("values") or [],
        },
        "google",
        started,
    )


def _sheets_write_range(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _auth._capability_guard("google_sheets_write_range", "sheets_write", started)
    if blocked:
        return blocked
    spreadsheet_id = (args.get("spreadsheet_id") or "").strip()
    range_name = (args.get("range") or "").strip()
    values = args.get("values")
    value_input_option = _auth._validate_enum(
        (args.get("value_input_option") or "USER_ENTERED").strip(),
        _auth._VALID_VALUE_INPUT_OPTIONS, "USER_ENTERED",
    )

    if not spreadsheet_id or not range_name or not isinstance(values, list):
        return err(
            "google_sheets_write_range",
            "missing_args",
            "spreadsheet_id, range, and values are required",
            "google",
            started,
        )

    try:
        service = _auth._build_service("sheets", "v4", _auth.SHEETS_WRITE_SCOPES)
        payload = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body={"values": values},
            )
            .execute()
        )
    except Exception as exc:
        return err("google_sheets_write_range", "sheets_write_failed", _auth._safe_error_msg(exc), "google", started)

    return ok(
        "google_sheets_write_range",
        {
            "spreadsheet_id": spreadsheet_id,
            "range": payload.get("updatedRange", range_name),
            "updated_rows": payload.get("updatedRows", 0),
            "updated_columns": payload.get("updatedColumns", 0),
            "updated_cells": payload.get("updatedCells", 0),
        },
        "google",
        started,
    )


def _sheets_append_rows(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _auth._capability_guard("google_sheets_append_rows", "sheets_write", started)
    if blocked:
        return blocked
    spreadsheet_id = (args.get("spreadsheet_id") or "").strip()
    range_name = (args.get("range") or "").strip()
    rows = args.get("rows")
    value_input_option = _auth._validate_enum(
        (args.get("value_input_option") or "USER_ENTERED").strip(),
        _auth._VALID_VALUE_INPUT_OPTIONS, "USER_ENTERED",
    )
    insert_data_option = _auth._validate_enum(
        (args.get("insert_data_option") or "INSERT_ROWS").strip(),
        _auth._VALID_INSERT_DATA_OPTIONS, "INSERT_ROWS",
    )

    if not spreadsheet_id or not range_name or not isinstance(rows, list):
        return err(
            "google_sheets_append_rows",
            "missing_args",
            "spreadsheet_id, range, and rows are required",
            "google",
            started,
        )

    try:
        service = _auth._build_service("sheets", "v4", _auth.SHEETS_WRITE_SCOPES)
        payload = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                insertDataOption=insert_data_option,
                body={"values": rows},
            )
            .execute()
        )
    except Exception as exc:
        return err("google_sheets_append_rows", "sheets_append_failed", _auth._safe_error_msg(exc), "google", started)

    updates = payload.get("updates") or {}
    return ok(
        "google_sheets_append_rows",
        {
            "spreadsheet_id": spreadsheet_id,
            "range": updates.get("updatedRange", range_name),
            "updated_rows": updates.get("updatedRows", 0),
            "updated_columns": updates.get("updatedColumns", 0),
            "updated_cells": updates.get("updatedCells", 0),
            "table_range": payload.get("tableRange", ""),
        },
        "google",
        started,
    )


def _sheets_create_sheet(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _auth._capability_guard("google_sheets_create_sheet", "sheets_write", started)
    if blocked:
        return blocked
    spreadsheet_id = (args.get("spreadsheet_id") or "").strip()
    sheet_title = (args.get("sheet_title") or "").strip()

    if not spreadsheet_id or not sheet_title:
        return err(
            "google_sheets_create_sheet",
            "missing_args",
            "spreadsheet_id and sheet_title are required",
            "google",
            started,
        )

    try:
        service = _auth._build_service("sheets", "v4", _auth.SHEETS_WRITE_SCOPES)
        payload = (
            service.spreadsheets()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_title}}}]},
            )
            .execute()
        )
    except Exception as exc:
        return err("google_sheets_create_sheet", "sheets_create_failed", _auth._safe_error_msg(exc), "google", started)

    replies = payload.get("replies") or []
    properties = ((replies[0] or {}).get("addSheet") or {}).get("properties", {}) if replies else {}
    return ok(
        "google_sheets_create_sheet",
        {
            "spreadsheet_id": spreadsheet_id,
            "sheet_id": properties.get("sheetId"),
            "sheet_title": properties.get("title", sheet_title),
            "index": properties.get("index"),
        },
        "google",
        started,
    )


def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="google_sheets_read_range",
            plugin_id=_auth.GOOGLE_PLUGIN_ID,
            description="Read a value range from Google Sheets.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "spreadsheet_id": {"type": "string"},
                    "range": {"type": "string"},
                },
                "required": ["spreadsheet_id", "range"],
            },
            handler=_sheets_read_range,
            aliases=["osaurus.google_sheets_read_range"],
        ),
        ToolDef(
            name="google_sheets_write_range",
            plugin_id=_auth.GOOGLE_PLUGIN_ID,
            description="Write values into a Google Sheets range.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "spreadsheet_id": {"type": "string"},
                    "range": {"type": "string"},
                    "values": {"type": "array", "items": {"type": "array", "items": {}}},
                    "value_input_option": {"type": "string"},
                },
                "required": ["spreadsheet_id", "range", "values"],
            },
            handler=_sheets_write_range,
            aliases=["osaurus.google_sheets_write_range"],
        ),
        ToolDef(
            name="google_sheets_append_rows",
            plugin_id=_auth.GOOGLE_PLUGIN_ID,
            description="Append rows to a Google Sheets range.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "spreadsheet_id": {"type": "string"},
                    "range": {"type": "string"},
                    "rows": {"type": "array", "items": {"type": "array", "items": {}}},
                    "value_input_option": {"type": "string"},
                    "insert_data_option": {"type": "string"},
                },
                "required": ["spreadsheet_id", "range", "rows"],
            },
            handler=_sheets_append_rows,
            aliases=["osaurus.google_sheets_append_rows"],
        ),
        ToolDef(
            name="google_sheets_create_sheet",
            plugin_id=_auth.GOOGLE_PLUGIN_ID,
            description="Create a new sheet tab in a Google spreadsheet.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "spreadsheet_id": {"type": "string"},
                    "sheet_title": {"type": "string"},
                },
                "required": ["spreadsheet_id", "sheet_title"],
            },
            handler=_sheets_create_sheet,
            aliases=["osaurus.google_sheets_create_sheet"],
        ),
    ]
