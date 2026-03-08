from __future__ import annotations

import base64
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .common import ToolDef, err, now_ms, ok, parse_int, resolve_under_workspace

GOOGLE_PLUGIN_ID = "mythosaur.google_workspace"
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CALENDAR_WRITE_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_SEND_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
DRIVE_WRITE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEETS_WRITE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DOCS_SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]
DOCS_WRITE_SCOPES = ["https://www.googleapis.com/auth/documents"]


def _google_modules():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    return Request, Credentials, build


def _token_file() -> Path:
    raw = (os.getenv("MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE") or "/secrets/google-token.json").strip()
    return Path(raw)


def _credentials_file() -> Path:
    raw = (os.getenv("MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE") or "/secrets/google-credentials.json").strip()
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


def _listify_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _bool_env(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def google_capabilities() -> dict[str, bool]:
    return {
        "calendar_read": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_CALENDAR_READ_ENABLED", True),
        "calendar_write": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_CALENDAR_WRITE_ENABLED", False),
        "gmail_read": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_GMAIL_READ_ENABLED", True),
        "gmail_send": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_GMAIL_SEND_ENABLED", False),
        "drive_read": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_DRIVE_READ_ENABLED", True),
        "drive_write": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_DRIVE_WRITE_ENABLED", False),
        "sheets_read": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_SHEETS_READ_ENABLED", True),
        "sheets_write": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_SHEETS_WRITE_ENABLED", False),
        "docs_read": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_DOCS_READ_ENABLED", True),
        "docs_write": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_DOCS_WRITE_ENABLED", False),
        "notebooklm": _bool_env("MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED", True),
        "maps": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_MAPS_ENABLED", True),
    }


def _capability_guard(tool_name: str, capability_key: str, started: int) -> dict[str, Any] | None:
    caps = google_capabilities()
    if caps.get(capability_key, False):
        return None
    return err(
        tool_name,
        "capability_disabled",
        f"Google capability '{capability_key}' is disabled by configuration.",
        "google",
        started,
    )


def _calendar_events(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_calendar_events", "calendar_read", started)
    if blocked:
        return blocked
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


def _calendar_create_event(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_calendar_create_event", "calendar_write", started)
    if blocked:
        return blocked

    calendar_id = (args.get("calendar_id") or "primary").strip() or "primary"
    summary = (args.get("summary") or "").strip()
    description = (args.get("description") or "").strip()
    location = (args.get("location") or "").strip()
    timezone = (args.get("timezone") or "UTC").strip() or "UTC"
    start_time = (args.get("start_time") or "").strip()
    end_time = (args.get("end_time") or "").strip()
    start_date = (args.get("start_date") or "").strip()
    end_date = (args.get("end_date") or "").strip()
    attendees = _listify_strings(args.get("attendees"))
    recurrence = _listify_strings(args.get("recurrence"))

    if not summary:
        return err(
            "google_calendar_create_event",
            "missing_args",
            "summary is required",
            "google",
            started,
        )

    body: dict[str, Any] = {"summary": summary}
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": email} for email in attendees]
    if recurrence:
        body["recurrence"] = recurrence

    if start_time and end_time:
        body["start"] = {"dateTime": start_time, "timeZone": timezone}
        body["end"] = {"dateTime": end_time, "timeZone": timezone}
    elif start_date and end_date:
        body["start"] = {"date": start_date}
        body["end"] = {"date": end_date}
    else:
        return err(
            "google_calendar_create_event",
            "missing_window",
            "provide either start_time and end_time, or start_date and end_date",
            "google",
            started,
        )

    try:
        service = _build_service("calendar", "v3", CALENDAR_WRITE_SCOPES)
        payload = (
            service.events()
            .insert(calendarId=calendar_id, body=body, sendUpdates=(args.get("send_updates") or "none"))
            .execute()
        )
    except Exception as exc:
        return err("google_calendar_create_event", "calendar_create_failed", str(exc), "google", started)

    event_start = payload.get("start", {}).get("dateTime") or payload.get("start", {}).get("date")
    event_end = payload.get("end", {}).get("dateTime") or payload.get("end", {}).get("date")
    return ok(
        "google_calendar_create_event",
        {
            "id": payload.get("id"),
            "calendar_id": calendar_id,
            "summary": payload.get("summary", summary),
            "start": event_start,
            "end": event_end,
            "html_link": payload.get("htmlLink", ""),
            "attendee_count": len(payload.get("attendees") or attendees),
        },
        "google",
        started,
    )


def _gmail_unread(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("gmail_unread", "gmail_read", started)
    if blocked:
        return blocked
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


def _gmail_send(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("gmail_send", "gmail_send", started)
    if blocked:
        return blocked
    to = _listify_strings(args.get("to"))
    cc = _listify_strings(args.get("cc"))
    bcc = _listify_strings(args.get("bcc"))
    subject = (args.get("subject") or "").strip()
    body_text = str(args.get("body_text") or "").strip()
    body_html = str(args.get("body_html") or "").strip()

    if not to or not subject or (not body_text and not body_html):
        return err(
            "gmail_send",
            "missing_args",
            "to, subject, and either body_text or body_html are required",
            "google",
            started,
        )

    message = EmailMessage()
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    message["Subject"] = subject

    if body_text:
        message.set_content(body_text)
        if body_html:
            message.add_alternative(body_html, subtype="html")
    else:
        message.set_content(body_html, subtype="html")

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    try:
        service = _build_service("gmail", "v1", GMAIL_SEND_SCOPES)
        payload = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except Exception as exc:
        return err("gmail_send", "gmail_send_failed", str(exc), "google", started)

    return ok(
        "gmail_send",
        {
            "id": payload.get("id"),
            "thread_id": payload.get("threadId", ""),
            "label_ids": payload.get("labelIds") or [],
            "to": to,
            "cc": cc,
            "bcc_count": len(bcc),
            "subject": subject,
        },
        "google",
        started,
    )


def _drive_recent_files(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_drive_recent_files", "drive_read", started)
    if blocked:
        return blocked
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


def _drive_create_folder(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_drive_create_folder", "drive_write", started)
    if blocked:
        return blocked
    folder_name = (args.get("folder_name") or "").strip()
    parent_folder_id = (args.get("parent_folder_id") or "").strip()
    if not folder_name:
        return err(
            "google_drive_create_folder",
            "missing_args",
            "folder_name is required",
            "google",
            started,
        )

    metadata: dict[str, Any] = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_folder_id:
        metadata["parents"] = [parent_folder_id]

    try:
        service = _build_service("drive", "v3", DRIVE_WRITE_SCOPES)
        payload = (
            service.files()
            .create(body=metadata, fields="id,name,mimeType,parents,webViewLink")
            .execute()
        )
    except Exception as exc:
        return err("google_drive_create_folder", "drive_create_failed", str(exc), "google", started)

    return ok(
        "google_drive_create_folder",
        {
            "id": payload.get("id"),
            "name": payload.get("name", folder_name),
            "mime_type": payload.get("mimeType", ""),
            "parent_folder_id": parent_folder_id,
            "web_view_link": payload.get("webViewLink", ""),
        },
        "google",
        started,
    )


def _drive_create_text_file(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_drive_create_text_file", "drive_write", started)
    if blocked:
        return blocked
    file_name = (args.get("file_name") or "").strip()
    content = args.get("content")
    parent_folder_id = (args.get("parent_folder_id") or "").strip()
    mime_type = (args.get("mime_type") or "text/plain").strip() or "text/plain"

    if not file_name:
        return err(
            "google_drive_create_text_file",
            "missing_args",
            "file_name is required",
            "google",
            started,
        )
    if content is None:
        content = ""
    if not isinstance(content, str):
        return err(
            "google_drive_create_text_file",
            "invalid_content",
            "content must be a string",
            "google",
            started,
        )

    metadata: dict[str, Any] = {"name": file_name}
    if parent_folder_id:
        metadata["parents"] = [parent_folder_id]

    try:
        from googleapiclient.http import MediaInMemoryUpload

        service = _build_service("drive", "v3", DRIVE_WRITE_SCOPES)
        media = MediaInMemoryUpload(content.encode("utf-8"), mimetype=mime_type, resumable=False)
        payload = (
            service.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id,name,mimeType,size,parents,webViewLink,webContentLink",
            )
            .execute()
        )
    except Exception as exc:
        return err("google_drive_create_text_file", "drive_create_failed", str(exc), "google", started)

    return ok(
        "google_drive_create_text_file",
        {
            "id": payload.get("id"),
            "name": payload.get("name", file_name),
            "mime_type": payload.get("mimeType", mime_type),
            "size": payload.get("size"),
            "parent_folder_id": parent_folder_id,
            "content_bytes": len(content.encode("utf-8")),
            "web_view_link": payload.get("webViewLink", ""),
            "web_content_link": payload.get("webContentLink", ""),
        },
        "google",
        started,
    )


def _drive_upload_file(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_drive_upload_file", "drive_write", started)
    if blocked:
        return blocked
    path_value = (args.get("path") or "").strip()
    file_name = (args.get("file_name") or "").strip()
    parent_folder_id = (args.get("parent_folder_id") or "").strip()
    mime_type = (args.get("mime_type") or "").strip()

    if not path_value:
        return err(
            "google_drive_upload_file",
            "missing_args",
            "path is required",
            "google",
            started,
        )

    try:
        path = resolve_under_workspace(path_value)
    except Exception as exc:
        return err("google_drive_upload_file", "invalid_path", str(exc), "google", started)

    if not path.exists() or not path.is_file():
        return err(
            "google_drive_upload_file",
            "file_not_found",
            f"file not found: {path}",
            "google",
            started,
        )

    upload_name = file_name or path.name
    upload_mime = mime_type or mimetypes.guess_type(upload_name)[0] or "application/octet-stream"
    metadata: dict[str, Any] = {"name": upload_name}
    if parent_folder_id:
        metadata["parents"] = [parent_folder_id]

    try:
        from googleapiclient.http import MediaFileUpload

        service = _build_service("drive", "v3", DRIVE_WRITE_SCOPES)
        media = MediaFileUpload(str(path), mimetype=upload_mime, resumable=False)
        payload = (
            service.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id,name,mimeType,size,parents,webViewLink,webContentLink",
            )
            .execute()
        )
    except Exception as exc:
        return err("google_drive_upload_file", "drive_upload_failed", str(exc), "google", started)

    return ok(
        "google_drive_upload_file",
        {
            "id": payload.get("id"),
            "name": payload.get("name", upload_name),
            "mime_type": payload.get("mimeType", upload_mime),
            "size": payload.get("size"),
            "parent_folder_id": parent_folder_id,
            "source_path": str(path),
            "web_view_link": payload.get("webViewLink", ""),
            "web_content_link": payload.get("webContentLink", ""),
        },
        "google",
        started,
    )


def _sheets_read_range(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_sheets_read_range", "sheets_read", started)
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


def _sheets_write_range(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_sheets_write_range", "sheets_write", started)
    if blocked:
        return blocked
    spreadsheet_id = (args.get("spreadsheet_id") or "").strip()
    range_name = (args.get("range") or "").strip()
    values = args.get("values")
    value_input_option = (args.get("value_input_option") or "USER_ENTERED").strip() or "USER_ENTERED"

    if not spreadsheet_id or not range_name or not isinstance(values, list):
        return err(
            "google_sheets_write_range",
            "missing_args",
            "spreadsheet_id, range, and values are required",
            "google",
            started,
        )

    try:
        service = _build_service("sheets", "v4", SHEETS_WRITE_SCOPES)
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
        return err("google_sheets_write_range", "sheets_write_failed", str(exc), "google", started)

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
    blocked = _capability_guard("google_sheets_append_rows", "sheets_write", started)
    if blocked:
        return blocked
    spreadsheet_id = (args.get("spreadsheet_id") or "").strip()
    range_name = (args.get("range") or "").strip()
    rows = args.get("rows")
    value_input_option = (args.get("value_input_option") or "USER_ENTERED").strip() or "USER_ENTERED"
    insert_data_option = (args.get("insert_data_option") or "INSERT_ROWS").strip() or "INSERT_ROWS"

    if not spreadsheet_id or not range_name or not isinstance(rows, list):
        return err(
            "google_sheets_append_rows",
            "missing_args",
            "spreadsheet_id, range, and rows are required",
            "google",
            started,
        )

    try:
        service = _build_service("sheets", "v4", SHEETS_WRITE_SCOPES)
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
        return err("google_sheets_append_rows", "sheets_append_failed", str(exc), "google", started)

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
    blocked = _capability_guard("google_sheets_create_sheet", "sheets_write", started)
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
        service = _build_service("sheets", "v4", SHEETS_WRITE_SCOPES)
        payload = (
            service.spreadsheets()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_title}}}]},
            )
            .execute()
        )
    except Exception as exc:
        return err("google_sheets_create_sheet", "sheets_create_failed", str(exc), "google", started)

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


def _docs_extract_text(elements: list[dict[str, Any]] | None, chunks: list[str]) -> None:
    for element in elements or []:
        paragraph = element.get("paragraph") or {}
        for part in paragraph.get("elements") or []:
            text_run = (part.get("textRun") or {}).get("content")
            if text_run:
                chunks.append(text_run)

        table = element.get("table") or {}
        for row in table.get("tableRows") or []:
            for cell in row.get("tableCells") or []:
                _docs_extract_text(cell.get("content") or [], chunks)

        table_of_contents = element.get("tableOfContents") or {}
        _docs_extract_text(table_of_contents.get("content") or [], chunks)


def _docs_get(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_docs_get", "docs_read", started)
    if blocked:
        return blocked

    document_id = (args.get("document_id") or "").strip()
    include_text = bool(args.get("include_text", True))
    max_chars = parse_int(args.get("max_chars"), 20000, minimum=100, maximum=200000)
    if not document_id:
        return err("google_docs_get", "missing_args", "document_id is required", "google", started)

    try:
        service = _build_service("docs", "v1", DOCS_SCOPES)
        payload = service.documents().get(documentId=document_id).execute()
    except Exception as exc:
        return err("google_docs_get", "docs_failed", str(exc), "google", started)

    text = ""
    if include_text:
        chunks: list[str] = []
        body = payload.get("body") or {}
        _docs_extract_text(body.get("content") or [], chunks)
        text = "".join(chunks).strip()
        if len(text) > max_chars:
            text = text[:max_chars]

    return ok(
        "google_docs_get",
        {
            "document_id": payload.get("documentId", document_id),
            "title": payload.get("title", ""),
            "revision_id": payload.get("revisionId", ""),
            "document_url": f"https://docs.google.com/document/d/{payload.get('documentId', document_id)}/edit",
            "text": text,
            "truncated": include_text and len(text) == max_chars,
        },
        "google",
        started,
    )


def _docs_create(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_docs_create", "docs_write", started)
    if blocked:
        return blocked

    title = (args.get("title") or "").strip()
    content = args.get("content")
    if not title:
        return err("google_docs_create", "missing_args", "title is required", "google", started)
    if content is None:
        content = ""
    if not isinstance(content, str):
        return err("google_docs_create", "invalid_content", "content must be a string", "google", started)

    try:
        service = _build_service("docs", "v1", DOCS_WRITE_SCOPES)
        payload = service.documents().create(body={"title": title}).execute()
        document_id = payload.get("documentId", "")
        if content and document_id:
            service.documents().batchUpdate(
                documentId=document_id,
                body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
            ).execute()
    except Exception as exc:
        return err("google_docs_create", "docs_create_failed", str(exc), "google", started)

    return ok(
        "google_docs_create",
        {
            "document_id": payload.get("documentId", ""),
            "title": payload.get("title", title),
            "revision_id": payload.get("revisionId", ""),
            "document_url": f"https://docs.google.com/document/d/{payload.get('documentId', '')}/edit",
            "content_chars": len(content),
        },
        "google",
        started,
    )


def _maps_build_route_link(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_maps_build_route_link", "maps", started)
    if blocked:
        return blocked

    origin = (args.get("origin") or "").strip()
    destination = (args.get("destination") or "").strip()
    if not origin or not destination:
        return err(
            "google_maps_build_route_link",
            "missing_args",
            "origin and destination are required",
            "google",
            started,
        )

    travel_mode = (args.get("travel_mode") or "driving").strip() or "driving"
    waypoints = _listify_strings(args.get("waypoints"))
    params = {
        "api": 1,
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }
    if waypoints:
        params["waypoints"] = "|".join(waypoints)
    if _bool_env("MYTHOSAUR_TOOLS_GOOGLE_MAPS_NAVIGATE_DEFAULT", False) or bool(args.get("navigate")):
        params["dir_action"] = "navigate"
    url = "https://www.google.com/maps/dir/?" + urlencode(params)

    return ok(
        "google_maps_build_route_link",
        {
            "origin": origin,
            "destination": destination,
            "travel_mode": travel_mode,
            "waypoints": waypoints,
            "url": url,
        },
        "google",
        started,
    )


def _maps_build_place_link(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_maps_build_place_link", "maps", started)
    if blocked:
        return blocked

    query = (args.get("query") or "").strip()
    place_id = (args.get("place_id") or "").strip()
    if not query and not place_id:
        return err(
            "google_maps_build_place_link",
            "missing_args",
            "query or place_id is required",
            "google",
            started,
        )

    params: dict[str, Any] = {"api": 1}
    if query:
        params["query"] = query
    if place_id:
        params["query_place_id"] = place_id
    url = "https://www.google.com/maps/search/?" + urlencode(params)

    return ok(
        "google_maps_build_place_link",
        {
            "query": query,
            "place_id": place_id,
            "url": url,
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
            name="google_calendar_create_event",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Create a Google Calendar event.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "calendar_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                    "timezone": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "attendees": {"type": "array", "items": {"type": "string"}},
                    "recurrence": {"type": "array", "items": {"type": "string"}},
                    "send_updates": {"type": "string"},
                },
                "required": ["summary"],
            },
            handler=_calendar_create_event,
            aliases=["osaurus.google_calendar_create_event"],
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
            name="gmail_send",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Send a Gmail message from the active account.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "to": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "cc": {"type": "array", "items": {"type": "string"}},
                    "bcc": {"type": "array", "items": {"type": "string"}},
                    "subject": {"type": "string"},
                    "body_text": {"type": "string"},
                    "body_html": {"type": "string"},
                },
                "required": ["to", "subject"],
            },
            handler=_gmail_send,
            aliases=["osaurus.gmail_send"],
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
            name="google_drive_create_folder",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Create a folder in Google Drive.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "folder_name": {"type": "string"},
                    "parent_folder_id": {"type": "string"},
                },
                "required": ["folder_name"],
            },
            handler=_drive_create_folder,
            aliases=["osaurus.google_drive_create_folder"],
        ),
        ToolDef(
            name="google_drive_upload_file",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Upload a workspace file to Google Drive.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "file_name": {"type": "string"},
                    "parent_folder_id": {"type": "string"},
                    "mime_type": {"type": "string"},
                },
                "required": ["path"],
            },
            handler=_drive_upload_file,
            aliases=["osaurus.google_drive_upload_file"],
        ),
        ToolDef(
            name="google_drive_create_text_file",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Create a text file directly in Google Drive.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file_name": {"type": "string"},
                    "content": {"type": "string"},
                    "parent_folder_id": {"type": "string"},
                    "mime_type": {"type": "string"},
                },
                "required": ["file_name"],
            },
            handler=_drive_create_text_file,
            aliases=["osaurus.google_drive_create_text_file"],
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
        ToolDef(
            name="google_sheets_write_range",
            plugin_id=GOOGLE_PLUGIN_ID,
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
            plugin_id=GOOGLE_PLUGIN_ID,
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
            plugin_id=GOOGLE_PLUGIN_ID,
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
        ToolDef(
            name="google_docs_get",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Read a Google Docs document and optionally return plain text content.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "document_id": {"type": "string"},
                    "include_text": {"type": "boolean"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["document_id"],
            },
            handler=_docs_get,
            aliases=["osaurus.google_docs_get"],
        ),
        ToolDef(
            name="google_docs_create",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Create a Google Docs document with optional initial text content.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["title"],
            },
            handler=_docs_create,
            aliases=["osaurus.google_docs_create"],
        ),
        ToolDef(
            name="google_maps_build_route_link",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Build a Google Maps route link from origin, destination, and optional waypoints.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "waypoints": {"type": "array", "items": {"type": "string"}},
                    "travel_mode": {"type": "string"},
                    "navigate": {"type": "boolean"},
                },
                "required": ["origin", "destination"],
            },
            handler=_maps_build_route_link,
            aliases=["osaurus.google_maps_build_route_link"],
        ),
        ToolDef(
            name="google_maps_build_place_link",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Build a Google Maps place/search link.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string"},
                    "place_id": {"type": "string"},
                },
                "required": [],
            },
            handler=_maps_build_place_link,
            aliases=["osaurus.google_maps_build_place_link"],
        ),
    ]
