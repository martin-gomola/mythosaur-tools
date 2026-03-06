from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .common import ToolDef, err, now_ms, ok, parse_int

GOOGLE_PLUGIN_ID = "mythosaur.google_workspace"
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _google_modules():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    return Request, Credentials, build


def _token_file() -> Path:
    raw = (os.getenv("MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE") or "/data/google-token.json").strip()
    return Path(raw)


def _credentials_file() -> Path:
    raw = (os.getenv("MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE") or "/data/google-credentials.json").strip()
    return Path(raw)


def _get_credentials(scopes: list[str]):
    Request, Credentials, _build = _google_modules()
    token_file = _token_file()
    if not token_file.exists():
        raise FileNotFoundError(
            f"google token file not found: {token_file}. Create an authorized token for the configured scopes."
        )
    creds = Credentials.from_authorized_user_file(str(token_file), scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.write_text(creds.to_json(), encoding="utf-8")
    if not creds.valid:
        creds_file = _credentials_file()
        raise ValueError(
            f"google token is invalid for scopes {scopes}. Refresh {token_file} using credentials from {creds_file}."
        )
    return creds


def _build_service(name: str, version: str, scopes: list[str]):
    _Request, _Credentials, build = _google_modules()
    creds = _get_credentials(scopes)
    return build(name, version, credentials=creds, cache_discovery=False)


def _calendar_events(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    time_min = (args.get("time_min") or "").strip()
    time_max = (args.get("time_max") or "").strip()
    calendar_id = (args.get("calendar_id") or "primary").strip() or "primary"
    max_results = parse_int(args.get("max_results"), 10, minimum=1, maximum=50)

    if not time_min or not time_max:
        return err("google_calendar_events", "missing_window", "time_min and time_max are required", "google", started)

    try:
        service = _build_service("calendar", "v3", CALENDAR_SCOPES)
        payload = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except Exception as exc:
        return err("google_calendar_events", "calendar_failed", str(exc), "google", started)

    events = []
    for item in payload.get("items") or []:
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
        events.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary", ""),
                "start": start,
                "end": end,
                "html_link": item.get("htmlLink", ""),
            }
        )
    return ok(
        "google_calendar_events",
        {
            "calendar_id": calendar_id,
            "time_min": time_min,
            "time_max": time_max,
            "events": events,
        },
        "google",
        started,
    )


def _gmail_unread(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    max_results = parse_int(args.get("max_results"), 10, minimum=1, maximum=50)
    include_snippets = bool(args.get("include_snippets", False))
    label_ids = args.get("label_ids") or ["INBOX", "UNREAD"]

    try:
        service = _build_service("gmail", "v1", GMAIL_SCOPES)
        list_payload = service.users().messages().list(userId="me", labelIds=label_ids, maxResults=max_results).execute()
    except Exception as exc:
        return err("gmail_unread", "gmail_failed", str(exc), "google", started)

    messages = []
    for item in list_payload.get("messages") or []:
        detail = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()
        headers = {header["name"].lower(): header["value"] for header in detail.get("payload", {}).get("headers", [])}
        row = {
            "id": item["id"],
            "thread_id": detail.get("threadId", ""),
            "subject": headers.get("subject", ""),
            "from": headers.get("from", ""),
            "date": headers.get("date", ""),
        }
        if include_snippets:
            row["snippet"] = detail.get("snippet", "")
        messages.append(row)

    return ok(
        "gmail_unread",
        {
            "unread_count": list_payload.get("resultSizeEstimate", len(messages)),
            "messages": messages,
        },
        "google",
        started,
    )


def _drive_recent_files(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    max_results = parse_int(args.get("max_results"), 10, minimum=1, maximum=50)
    query = (args.get("query") or "").strip()

    try:
        service = _build_service("drive", "v3", DRIVE_SCOPES)
        payload = (
            service.files()
            .list(
                pageSize=max_results,
                q=query or None,
                orderBy="modifiedTime desc",
                fields="files(id,name,mimeType,modifiedTime,webViewLink)",
            )
            .execute()
        )
    except Exception as exc:
        return err("google_drive_recent_files", "drive_failed", str(exc), "google", started)

    return ok(
        "google_drive_recent_files",
        {"files": payload.get("files") or []},
        "google",
        started,
    )


def _sheets_read_range(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
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
        service = _build_service("sheets", "v4", SHEETS_SCOPES)
        payload = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    except Exception as exc:
        return err("google_sheets_read_range", "sheets_failed", str(exc), "google", started)

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


def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="google_calendar_events",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="List Google Calendar events in a time window.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "time_min": {"type": "string"},
                    "time_max": {"type": "string"},
                    "calendar_id": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["time_min", "time_max"],
            },
            handler=_calendar_events,
            aliases=["osaurus.google_calendar_events"],
        ),
        ToolDef(
            name="gmail_unread",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Return unread Gmail messages for the active account.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "max_results": {"type": "integer"},
                    "include_snippets": {"type": "boolean"},
                    "label_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [],
            },
            handler=_gmail_unread,
            aliases=["osaurus.gmail_unread"],
        ),
        ToolDef(
            name="google_drive_recent_files",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="List recently modified Google Drive files.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "max_results": {"type": "integer"},
                    "query": {"type": "string"},
                },
                "required": [],
            },
            handler=_drive_recent_files,
            aliases=["osaurus.google_drive_recent_files"],
        ),
        ToolDef(
            name="google_sheets_read_range",
            plugin_id=GOOGLE_PLUGIN_ID,
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
    ]
