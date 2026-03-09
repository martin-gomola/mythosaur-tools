from __future__ import annotations

import base64
import json
import mimetypes
import os
import threading
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

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
PHOTOS_READ_SCOPES = ["https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"]
PHOTOS_WRITE_SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary.appendonly",
    "https://www.googleapis.com/auth/photoslibrary.edit.appcreateddata",
]
_MAPS_DEFAULT_TIMEOUT_SEC = 20
_PHOTOS_DEFAULT_TIMEOUT_SEC = 20
_token_refresh_lock = threading.Lock()

_GOOGLE_SCOPE_REQUIREMENTS = {
    "gmail_read": GMAIL_SCOPES,
    "gmail_send": GMAIL_SEND_SCOPES,
    "calendar_read": CALENDAR_SCOPES,
    "calendar_write": CALENDAR_WRITE_SCOPES,
    "drive_read": DRIVE_SCOPES,
    "drive_write": DRIVE_WRITE_SCOPES,
    "sheets_read": SHEETS_SCOPES,
    "sheets_write": SHEETS_WRITE_SCOPES,
    "docs_read": DOCS_SCOPES,
    "docs_write": DOCS_WRITE_SCOPES,
    "photos_read": PHOTOS_READ_SCOPES,
    "photos_write": PHOTOS_WRITE_SCOPES,
}


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
    with _token_refresh_lock:
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


def _maps_api_key_value() -> str:
    direct = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
    if direct:
        return direct

    # Backward-compatibility: older local envs incorrectly stored the API key here.
    legacy = (os.getenv("GOOGLE_MAPS_PLATFORM") or "").strip()
    if legacy.startswith("AIza"):
        return legacy
    return ""


def _google_service_checks() -> dict[str, dict[str, Any]]:
    maps_api_key = _maps_api_key_value()
    return {
        "maps": {
            "auth_type": "api_key",
            "configured": bool(maps_api_key),
            "required_config": ["GOOGLE_MAPS_API_KEY"],
            "missing_config": [] if maps_api_key else ["GOOGLE_MAPS_API_KEY"],
        }
    }


def _maps_api_guard(tool_name: str, started: int) -> dict[str, Any] | None:
    if _maps_api_key_value():
        return None
    return err(
        tool_name,
        "maps_api_key_missing",
        "Google Maps API key is not configured. Set GOOGLE_MAPS_API_KEY.",
        "google",
        started,
    )


def _maps_post(tool_name: str, url: str, payload: dict[str, Any], field_mask: str, started: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    blocked = _maps_api_guard(tool_name, started)
    if blocked:
        return None, blocked

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _maps_api_key_value(),
        "X-Goog-FieldMask": field_mask,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=_MAPS_DEFAULT_TIMEOUT_SEC)
        response.raise_for_status()
    except requests.RequestException as exc:
        message = str(exc)
        if exc.response is not None:
            try:
                error_payload = exc.response.json()
                message = ((error_payload.get("error") or {}).get("message")) or exc.response.text or message
            except ValueError:
                message = exc.response.text or message
        return None, err(tool_name, "maps_api_failed", message, "google", started)

    try:
        return response.json(), None
    except ValueError as exc:
        return None, err(tool_name, "maps_api_invalid_response", str(exc), "google", started)


def _maps_normalize_travel_mode(raw: str) -> str:
    value = raw.strip().lower()
    mapping = {
        "drive": "DRIVE",
        "driving": "DRIVE",
        "walk": "WALK",
        "walking": "WALK",
        "bicycle": "BICYCLE",
        "bike": "BICYCLE",
        "transit": "TRANSIT",
        "two_wheeler": "TWO_WHEELER",
        "two-wheeler": "TWO_WHEELER",
        "motorcycle": "TWO_WHEELER",
    }
    return mapping.get(value, raw.strip().upper() or "DRIVE")


def _maps_link_travel_mode(raw: str) -> str:
    value = raw.strip().lower()
    mapping = {
        "drive": "driving",
        "driving": "driving",
        "walk": "walking",
        "walking": "walking",
        "bicycle": "bicycling",
        "bike": "bicycling",
        "transit": "transit",
        "two_wheeler": "driving",
        "two-wheeler": "driving",
        "motorcycle": "driving",
    }
    return mapping.get(value, value or "driving")


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
        "photos_read": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_PHOTOS_READ_ENABLED", False),
        "photos_write": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_PHOTOS_WRITE_ENABLED", False),
        "notebooklm": _bool_env("MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED", True),
        "maps": _bool_env("MYTHOSAUR_TOOLS_GOOGLE_MAPS_ENABLED", True),
    }


def google_auth_status() -> dict[str, Any]:
    token_file = _token_file()
    service_checks = _google_service_checks()
    if not token_file.exists():
        return {
            "token_file": str(token_file),
            "token_present": False,
            "granted_scopes": [],
            "scope_checks": {},
            "service_checks": service_checks,
        }

    try:
        payload = json.loads(token_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "token_file": str(token_file),
            "token_present": True,
            "granted_scopes": [],
            "scope_checks": {},
            "service_checks": service_checks,
            "error": f"invalid token file: {exc}",
        }

    raw_scopes = payload.get("scopes") or payload.get("scope") or []
    if isinstance(raw_scopes, str):
        granted_scopes = [item.strip() for item in raw_scopes.split() if item.strip()]
    elif isinstance(raw_scopes, list):
        granted_scopes = [str(item).strip() for item in raw_scopes if str(item).strip()]
    else:
        granted_scopes = []

    granted = set(granted_scopes)
    checks: dict[str, dict[str, Any]] = {}
    for capability, required in _GOOGLE_SCOPE_REQUIREMENTS.items():
        missing = [scope for scope in required if scope not in granted]
        checks[capability] = {
            "required_scopes": list(required),
            "granted": not missing,
            "missing_scopes": missing,
        }

    return {
        "token_file": str(token_file),
        "token_present": True,
        "granted_scopes": granted_scopes,
        "scope_checks": checks,
        "service_checks": service_checks,
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
    unread_only = bool(args.get("unread_only", False))
    label_ids = list(args.get("label_ids") or ["INBOX"])
    if unread_only and "UNREAD" not in label_ids:
        label_ids.append("UNREAD")

    try:
        service = _build_service("gmail", "v1", GMAIL_SCOPES)
        list_payload = service.users().messages().list(userId="me", labelIds=label_ids, maxResults=max_results).execute()
        unread_label_ids = label_ids if "UNREAD" in label_ids else [*label_ids, "UNREAD"]
        unread_payload = service.users().messages().list(userId="me", labelIds=unread_label_ids, maxResults=1).execute()
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
            "label_ids": detail.get("labelIds") or [],
            "is_unread": "UNREAD" in (detail.get("labelIds") or []),
        }
        if include_snippets:
            row["snippet"] = detail.get("snippet", "")
        messages.append(row)

    return ok(
        "gmail_unread",
        {
            "message_count": list_payload.get("resultSizeEstimate", len(messages)),
            "unread_count": unread_payload.get(
                "resultSizeEstimate",
                sum(1 for message in messages if message["is_unread"]),
            ),
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

    travel_mode = _maps_link_travel_mode(str(args.get("travel_mode") or "driving"))
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


def _maps_search_places(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_maps_search_places", "maps", started)
    if blocked:
        return blocked

    query = (args.get("query") or "").strip()
    if not query:
        return err("google_maps_search_places", "missing_args", "query is required", "google", started)

    payload: dict[str, Any] = {
        "textQuery": query,
        "maxResultCount": parse_int(args.get("max_results"), 5, minimum=1, maximum=10),
    }
    if language_code := (args.get("language_code") or "").strip():
        payload["languageCode"] = language_code
    if region_code := (args.get("region_code") or "").strip():
        payload["regionCode"] = region_code
    if included_type := (args.get("included_type") or "").strip():
        payload["includedType"] = included_type
    if "open_now" in args:
        payload["openNow"] = bool(args.get("open_now"))

    response_json, api_error = _maps_post(
        "google_maps_search_places",
        "https://places.googleapis.com/v1/places:searchText",
        payload,
        "places.id,places.displayName,places.formattedAddress,places.googleMapsUri,places.location,places.types,nextPageToken",
        started,
    )
    if api_error:
        return api_error

    places = []
    for place in response_json.get("places") or []:
        location = place.get("location") or {}
        places.append(
            {
                "id": place.get("id", ""),
                "display_name": ((place.get("displayName") or {}).get("text")) or "",
                "formatted_address": place.get("formattedAddress", ""),
                "google_maps_uri": place.get("googleMapsUri", ""),
                "location": {
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                },
                "types": place.get("types") or [],
            }
        )

    return ok(
        "google_maps_search_places",
        {
            "query": query,
            "places": places,
            "next_page_token": response_json.get("nextPageToken", ""),
        },
        "google",
        started,
    )


def _maps_compute_route(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_maps_compute_route", "maps", started)
    if blocked:
        return blocked

    origin = (args.get("origin") or "").strip()
    destination = (args.get("destination") or "").strip()
    if not origin or not destination:
        return err(
            "google_maps_compute_route",
            "missing_args",
            "origin and destination are required",
            "google",
            started,
        )

    travel_mode = _maps_normalize_travel_mode(str(args.get("travel_mode") or "DRIVE"))
    payload: dict[str, Any] = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": travel_mode,
        "computeAlternativeRoutes": bool(args.get("alternatives", False)),
    }
    if departure_time := (args.get("departure_time") or "").strip():
        payload["departureTime"] = departure_time
    if routing_preference := (args.get("routing_preference") or "").strip():
        payload["routingPreference"] = routing_preference.strip().upper()

    intermediates = []
    for waypoint in _listify_strings(args.get("waypoints")):
        intermediates.append({"address": waypoint})
    if intermediates:
        payload["intermediates"] = intermediates

    response_json, api_error = _maps_post(
        "google_maps_compute_route",
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        payload,
        "routes.duration,routes.distanceMeters,routes.description,routes.polyline.encodedPolyline,routes.legs.duration,routes.legs.distanceMeters,routes.legs.steps.navigationInstruction.instructions",
        started,
    )
    if api_error:
        return api_error

    routes = []
    for route in response_json.get("routes") or []:
        legs = []
        for leg in route.get("legs") or []:
            steps = []
            for step in leg.get("steps") or []:
                instructions = ((step.get("navigationInstruction") or {}).get("instructions")) or ""
                if instructions:
                    steps.append(instructions)
            legs.append(
                {
                    "distance_meters": leg.get("distanceMeters"),
                    "duration": leg.get("duration"),
                    "steps": steps,
                }
            )
        routes.append(
            {
                "description": route.get("description", ""),
                "distance_meters": route.get("distanceMeters"),
                "duration": route.get("duration"),
                "polyline": ((route.get("polyline") or {}).get("encodedPolyline")) or "",
                "legs": legs,
            }
        )

    return ok(
        "google_maps_compute_route",
        {
            "origin": origin,
            "destination": destination,
            "travel_mode": travel_mode,
            "waypoints": _listify_strings(args.get("waypoints")),
            "routes": routes,
            "route_link": _maps_build_route_link(
                {
                    "origin": origin,
                    "destination": destination,
                    "waypoints": _listify_strings(args.get("waypoints")),
                    "travel_mode": _maps_link_travel_mode(travel_mode),
                    "navigate": bool(args.get("navigate")),
                }
            )["data"]["url"],
        },
        "google",
        started,
    )


def _photos_headers(scopes: list[str], *, json_body: bool = True) -> dict[str, str]:
    creds = _get_credentials(scopes)
    headers = {"Authorization": f"Bearer {creds.token}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _photos_request(
    tool_name: str,
    method: str,
    url: str,
    scopes: list[str],
    started: int,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> tuple[dict[str, Any] | str | None, dict[str, Any] | None]:
    try:
        request_headers = _photos_headers(scopes, json_body=data is None)
        if headers:
            request_headers.update(headers)
        response = requests.request(
            method,
            url,
            headers=request_headers,
            json=payload if data is None else None,
            params=params,
            data=data,
            timeout=_PHOTOS_DEFAULT_TIMEOUT_SEC,
        )
        response.raise_for_status()
    except Exception as exc:
        message = str(exc)
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                error_payload = response.json()
                message = ((error_payload.get("error") or {}).get("message")) or response.text or message
            except ValueError:
                message = response.text or message
        return None, err(tool_name, "photos_failed", message, "google", started)

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        try:
            return response.json(), None
        except ValueError as exc:
            return None, err(tool_name, "photos_invalid_response", str(exc), "google", started)
    if not response.text:
        return {}, None
    return response.text, None


def _photos_normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("mediaMetadata") or {}
    return {
        "id": item.get("id", ""),
        "description": item.get("description", ""),
        "product_url": item.get("productUrl", ""),
        "base_url": item.get("baseUrl", ""),
        "mime_type": item.get("mimeType", ""),
        "filename": item.get("filename", ""),
        "creation_time": metadata.get("creationTime", ""),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
    }


def _photos_list_media_pages(
    *,
    tool_name: str,
    started: int,
    album_id: str = "",
    max_items: int = 200,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    items: list[dict[str, Any]] = []
    page_token = ""
    remaining = max_items

    while remaining > 0:
        page_size = min(100, remaining)
        if album_id:
            payload: dict[str, Any] = {"albumId": album_id, "pageSize": page_size}
            if page_token:
                payload["pageToken"] = page_token
            response_json, api_error = _photos_request(
                tool_name,
                "POST",
                "https://photoslibrary.googleapis.com/v1/mediaItems:search",
                PHOTOS_READ_SCOPES,
                started,
                payload=payload,
            )
        else:
            params: dict[str, Any] = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            response_json, api_error = _photos_request(
                tool_name,
                "GET",
                "https://photoslibrary.googleapis.com/v1/mediaItems",
                PHOTOS_READ_SCOPES,
                started,
                params=params,
            )
        if api_error:
            return None, api_error
        page_items = response_json.get("mediaItems") or []
        items.extend(page_items)
        remaining -= len(page_items)
        page_token = str(response_json.get("nextPageToken") or "").strip()
        if not page_token or not page_items:
            break

    return items, None


def _photos_create_album(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_photos_create_album", "photos_write", started)
    if blocked:
        return blocked

    title = (args.get("title") or "").strip()
    if not title:
        return err("google_photos_create_album", "missing_args", "title is required", "google", started)

    response_json, api_error = _photos_request(
        "google_photos_create_album",
        "POST",
        "https://photoslibrary.googleapis.com/v1/albums",
        PHOTOS_WRITE_SCOPES,
        started,
        payload={"album": {"title": title}},
    )
    if api_error:
        return api_error

    album = response_json.get("album") or response_json
    return ok(
        "google_photos_create_album",
        {
            "id": album.get("id", ""),
            "title": album.get("title", title),
            "product_url": album.get("productUrl", ""),
            "media_items_count": album.get("mediaItemsCount"),
            "cover_photo_base_url": album.get("coverPhotoBaseUrl", ""),
        },
        "google",
        started,
    )


def _photos_list_albums(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_photos_list_albums", "photos_read", started)
    if blocked:
        return blocked

    page_size = parse_int(args.get("page_size"), 20, minimum=1, maximum=50)
    params: dict[str, Any] = {"pageSize": page_size}
    if page_token := (args.get("page_token") or "").strip():
        params["pageToken"] = page_token

    response_json, api_error = _photos_request(
        "google_photos_list_albums",
        "GET",
        "https://photoslibrary.googleapis.com/v1/albums",
        PHOTOS_READ_SCOPES,
        started,
        params=params,
    )
    if api_error:
        return api_error

    albums = []
    for album in response_json.get("albums") or []:
        albums.append(
            {
                "id": album.get("id", ""),
                "title": album.get("title", ""),
                "product_url": album.get("productUrl", ""),
                "media_items_count": album.get("mediaItemsCount"),
                "cover_photo_base_url": album.get("coverPhotoBaseUrl", ""),
            }
        )

    return ok(
        "google_photos_list_albums",
        {"albums": albums, "next_page_token": response_json.get("nextPageToken", "")},
        "google",
        started,
    )


def _photos_list_media_items(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_photos_list_media_items", "photos_read", started)
    if blocked:
        return blocked

    album_id = (args.get("album_id") or "").strip()
    max_items = parse_int(args.get("max_items"), 50, minimum=1, maximum=500)
    items, api_error = _photos_list_media_pages(
        tool_name="google_photos_list_media_items",
        started=started,
        album_id=album_id,
        max_items=max_items,
    )
    if api_error:
        return api_error

    return ok(
        "google_photos_list_media_items",
        {
            "album_id": album_id,
            "items": [_photos_normalize_item(item) for item in items or []],
        },
        "google",
        started,
    )


def _photos_add_to_album(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_photos_add_to_album", "photos_write", started)
    if blocked:
        return blocked

    album_id = (args.get("album_id") or "").strip()
    media_item_ids = _listify_strings(args.get("media_item_ids"))
    if not album_id or not media_item_ids:
        return err(
            "google_photos_add_to_album",
            "missing_args",
            "album_id and media_item_ids are required",
            "google",
            started,
        )

    _response_json, api_error = _photos_request(
        "google_photos_add_to_album",
        "POST",
        f"https://photoslibrary.googleapis.com/v1/albums/{album_id}:batchAddMediaItems",
        PHOTOS_WRITE_SCOPES,
        started,
        payload={"mediaItemIds": media_item_ids},
    )
    if api_error:
        return api_error

    return ok(
        "google_photos_add_to_album",
        {"album_id": album_id, "media_item_ids": media_item_ids, "added_count": len(media_item_ids)},
        "google",
        started,
    )


def _photos_upload_file(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_photos_upload_file", "photos_write", started)
    if blocked:
        return blocked

    path = (args.get("path") or "").strip()
    album_id = (args.get("album_id") or "").strip()
    description = (args.get("description") or "").strip()
    if not path:
        return err("google_photos_upload_file", "missing_args", "path is required", "google", started)

    try:
        source_path = resolve_under_workspace(path)
    except Exception as exc:
        return err("google_photos_upload_file", "invalid_path", str(exc), "google", started)
    if not source_path.exists() or not source_path.is_file():
        return err("google_photos_upload_file", "missing_file", f"file not found: {source_path}", "google", started)

    upload_token, api_error = _photos_request(
        "google_photos_upload_file",
        "POST",
        "https://photoslibrary.googleapis.com/v1/uploads",
        PHOTOS_WRITE_SCOPES,
        started,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Goog-Upload-File-Name": source_path.name,
            "X-Goog-Upload-Protocol": "raw",
        },
        data=source_path.read_bytes(),
    )
    if api_error:
        return api_error

    batch_payload: dict[str, Any] = {
        "newMediaItems": [
            {
                "description": description,
                "simpleMediaItem": {"uploadToken": str(upload_token), "fileName": source_path.name},
            }
        ]
    }
    if album_id:
        batch_payload["albumId"] = album_id

    response_json, api_error = _photos_request(
        "google_photos_upload_file",
        "POST",
        "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate",
        PHOTOS_WRITE_SCOPES,
        started,
        payload=batch_payload,
    )
    if api_error:
        return api_error

    results = response_json.get("newMediaItemResults") or []
    created = []
    for item in results:
        status = item.get("status") or {}
        media_item = item.get("mediaItem") or {}
        created.append(
            {
                "status_code": status.get("code"),
                "status_message": status.get("message", ""),
                "media_item": _photos_normalize_item(media_item) if media_item else {},
            }
        )

    return ok(
        "google_photos_upload_file",
        {
            "source_path": str(source_path),
            "album_id": album_id,
            "results": created,
        },
        "google",
        started,
    )


def _photos_duplicate_key(item: dict[str, Any]) -> str:
    normalized = _photos_normalize_item(item)
    return "|".join(
        [
            normalized.get("filename", "").lower(),
            normalized.get("mime_type", "").lower(),
            str(normalized.get("width") or ""),
            str(normalized.get("height") or ""),
            normalized.get("creation_time", ""),
        ]
    )


def _photos_find_duplicate_candidates(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_photos_find_duplicate_candidates", "photos_read", started)
    if blocked:
        return blocked

    album_id = (args.get("album_id") or "").strip()
    max_items = parse_int(args.get("max_items"), 200, minimum=1, maximum=500)
    items, api_error = _photos_list_media_pages(
        tool_name="google_photos_find_duplicate_candidates",
        started=started,
        album_id=album_id,
        max_items=max_items,
    )
    if api_error:
        return api_error

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items or []:
        key = _photos_duplicate_key(item)
        groups.setdefault(key, []).append(_photos_normalize_item(item))

    duplicate_groups = [group for group in groups.values() if len(group) > 1]
    duplicate_groups.sort(key=len, reverse=True)

    return ok(
        "google_photos_find_duplicate_candidates",
        {
            "album_id": album_id,
            "duplicate_group_count": len(duplicate_groups),
            "groups": duplicate_groups,
            "notes": [
                "Duplicate detection only covers app-created Google Photos items that the current API can list.",
                "Grouping is heuristic: filename, mime type, dimensions, and creation time.",
            ],
        },
        "google",
        started,
    )


def _photos_create_curated_album(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _capability_guard("google_photos_create_curated_album", "photos_write", started)
    if blocked:
        return blocked

    title = (args.get("title") or "").strip()
    media_item_ids = _listify_strings(args.get("media_item_ids"))
    if not title or not media_item_ids:
        return err(
            "google_photos_create_curated_album",
            "missing_args",
            "title and media_item_ids are required",
            "google",
            started,
        )

    album_result = _photos_create_album({"title": title})
    if album_result.get("status") != "ok":
        return album_result
    album_id = str((album_result.get("data") or {}).get("id") or "")
    add_result = _photos_add_to_album({"album_id": album_id, "media_item_ids": media_item_ids})
    if add_result.get("status") != "ok":
        return add_result

    return ok(
        "google_photos_create_curated_album",
        {
            "album_id": album_id,
            "title": title,
            "media_item_ids": media_item_ids,
            "product_url": (album_result.get("data") or {}).get("product_url", ""),
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
            description="Return recent Gmail inbox messages for the active account, including unread status.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "max_results": {"type": "integer"},
                    "include_snippets": {"type": "boolean"},
                    "unread_only": {"type": "boolean"},
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
            name="google_photos_list_albums",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="List app-created Google Photos albums available to the authorized account.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "page_size": {"type": "integer"},
                    "page_token": {"type": "string"},
                },
                "required": [],
            },
            handler=_photos_list_albums,
            aliases=["osaurus.google_photos_list_albums"],
        ),
        ToolDef(
            name="google_photos_create_album",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Create an app-created Google Photos album.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
            handler=_photos_create_album,
            aliases=["osaurus.google_photos_create_album"],
        ),
        ToolDef(
            name="google_photos_list_media_items",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="List app-created Google Photos media items, optionally within an album.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "album_id": {"type": "string"},
                    "max_items": {"type": "integer"},
                },
                "required": [],
            },
            handler=_photos_list_media_items,
            aliases=["osaurus.google_photos_list_media_items"],
        ),
        ToolDef(
            name="google_photos_upload_file",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Upload a local workspace file into Google Photos app-created storage, optionally adding it to an album.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "album_id": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["path"],
            },
            handler=_photos_upload_file,
            aliases=["osaurus.google_photos_upload_file"],
        ),
        ToolDef(
            name="google_photos_add_to_album",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Add app-created Google Photos media items to an album.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "album_id": {"type": "string"},
                    "media_item_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["album_id", "media_item_ids"],
            },
            handler=_photos_add_to_album,
            aliases=["osaurus.google_photos_add_to_album"],
        ),
        ToolDef(
            name="google_photos_find_duplicate_candidates",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Find likely duplicate app-created Google Photos items using filename and metadata heuristics.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "album_id": {"type": "string"},
                    "max_items": {"type": "integer"},
                },
                "required": [],
            },
            handler=_photos_find_duplicate_candidates,
            aliases=["osaurus.google_photos_find_duplicate_candidates"],
        ),
        ToolDef(
            name="google_photos_create_curated_album",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Create a new curated Google Photos album from selected app-created media item ids.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "media_item_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "media_item_ids"],
            },
            handler=_photos_create_curated_album,
            aliases=["osaurus.google_photos_create_curated_album"],
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
        ToolDef(
            name="google_maps_search_places",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Search Google Maps Places by text query using the Google Maps Places API.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "language_code": {"type": "string"},
                    "region_code": {"type": "string"},
                    "included_type": {"type": "string"},
                    "open_now": {"type": "boolean"},
                },
                "required": ["query"],
            },
            handler=_maps_search_places,
            aliases=["osaurus.google_maps_search_places"],
        ),
        ToolDef(
            name="google_maps_compute_route",
            plugin_id=GOOGLE_PLUGIN_ID,
            description="Compute routes between origin and destination using the Google Routes API.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "waypoints": {"type": "array", "items": {"type": "string"}},
                    "travel_mode": {"type": "string"},
                    "routing_preference": {"type": "string"},
                    "departure_time": {"type": "string"},
                    "alternatives": {"type": "boolean"},
                    "navigate": {"type": "boolean"},
                },
                "required": ["origin", "destination"],
            },
            handler=_maps_compute_route,
            aliases=["osaurus.google_maps_compute_route"],
        ),
    ]
