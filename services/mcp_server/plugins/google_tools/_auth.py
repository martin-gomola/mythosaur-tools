"""Shared foundation module for all Google Workspace tools.

Contains auth, validation, scopes, capability checks, and service helpers
used across calendar, gmail, drive, sheets, docs, photos, and maps domains.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Final

import requests

from ..common import JsonDict, bool_env, env_get, err

# --- Validation constants ---
_MAX_CONTENT_BYTES = 10 * 1024 * 1024
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_MAX_LABEL_IDS = 20
_MAX_DRIVE_QUERY_LEN = 1000
GOOGLE_SOURCE: Final = "google"
DEFAULT_TOKEN_FILE: Final = "/secrets/google-token.json"
DEFAULT_CREDENTIALS_FILE: Final = "/secrets/google-credentials.json"

# --- Regex patterns ---
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RFC3339_LIKE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$"
)
_MIME_TYPE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9!#$&\-^_.+]*/[a-zA-Z0-9][a-zA-Z0-9!#$&\-^_.+]*$")
_HTML_DANGEROUS_RE = re.compile(
    r"<\s*script|javascript\s*:|on\w+\s*=|<\s*iframe|<\s*object|<\s*embed|<\s*applet|<\s*form\b",
    re.IGNORECASE,
)

# --- Enum frozensets ---
_VALID_SEND_UPDATES = frozenset({"all", "externalOnly", "none"})
_VALID_VALUE_INPUT_OPTIONS = frozenset({"USER_ENTERED", "RAW"})
_VALID_INSERT_DATA_OPTIONS = frozenset({"INSERT_ROWS", "OVERWRITE"})
_VALID_ROUTING_PREFERENCES = frozenset({"TRAFFIC_UNAWARE", "TRAFFIC_AWARE", "TRAFFIC_AWARE_OPTIMAL"})


# --- Validation helpers ---
def _safe_error_msg(exc: Exception) -> str:
    if isinstance(exc, requests.RequestException):
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                body = resp.json()
                msg = ((body.get("error") or {}).get("message")) or ""
                if msg:
                    return msg[:500]
            except (ValueError, AttributeError):
                pass
            if hasattr(resp, "text") and resp.text:
                return resp.text[:500]
        return "Google API request failed"
    if isinstance(exc, (FileNotFoundError, ValueError)):
        return str(exc)[:500]
    return "an unexpected error occurred"


def _validate_emails(tool_name: str, field: str, emails: list[str], started: int) -> dict[str, Any] | None:
    for addr in emails:
        if not _EMAIL_RE.match(addr):
            return err(tool_name, "invalid_email", f"invalid email in {field}: {addr}", GOOGLE_SOURCE, started)
    return None


def _validate_rfc3339(tool_name: str, field: str, value: str, started: int) -> dict[str, Any] | None:
    if value and not _RFC3339_LIKE_RE.match(value):
        return err(tool_name, "invalid_timestamp", f"{field} must be RFC 3339 format", GOOGLE_SOURCE, started)
    return None


def _validate_content_size(
    tool_name: str, content: str, max_bytes: int, started: int,
) -> dict[str, Any] | None:
    size = len(content.encode("utf-8"))
    if size > max_bytes:
        return err(
            tool_name, "content_too_large",
            f"content is {size} bytes, max allowed is {max_bytes}",
            GOOGLE_SOURCE, started,
        )
    return None


def _validate_enum(value: str, valid: frozenset[str], default: str) -> str:
    return value if value in valid else default


# --- Plugin ID ---
GOOGLE_PLUGIN_ID = "mythosaur.google_workspace"

# --- Scope constants ---
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

# --- Timeout constants ---
_MAPS_DEFAULT_TIMEOUT_SEC = 20
_PHOTOS_DEFAULT_TIMEOUT_SEC = 20

# --- Thread lock ---
_token_refresh_lock = threading.Lock()

# --- Scope requirements ---
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


# --- Auth ---
def _google_modules():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    return Request, Credentials, build


def _token_file() -> Path:
    raw = (env_get("MT_GOOGLE_TOKEN_FILE", DEFAULT_TOKEN_FILE) or DEFAULT_TOKEN_FILE).strip()
    return Path(raw)


def _credentials_file() -> Path:
    raw = (env_get("MT_GOOGLE_CREDENTIALS_FILE", DEFAULT_CREDENTIALS_FILE) or DEFAULT_CREDENTIALS_FILE).strip()
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


# --- Maps API key ---
def _maps_api_key_value() -> str:
    direct = (env_get("MT_GOOGLE_MAPS_API_KEY", "") or "").strip()
    if direct:
        return direct

    # Backward-compatibility: older local envs incorrectly stored the API key here.
    legacy = (env_get("MT_GOOGLE_MAPS_PLATFORM", "") or "").strip()
    if legacy.startswith("AIza"):
        return legacy
    return ""


def _google_service_checks() -> dict[str, dict[str, Any]]:
    maps_api_key = _maps_api_key_value()
    return {
        "maps": {
            "auth_type": "api_key",
            "configured": bool(maps_api_key),
            "required_config": ["MT_GOOGLE_MAPS_API_KEY"],
            "missing_config": [] if maps_api_key else ["MT_GOOGLE_MAPS_API_KEY"],
        }
    }


def _maps_api_guard(tool_name: str, started: int) -> dict[str, Any] | None:
    if _maps_api_key_value():
        return None
    return err(
        tool_name,
        "maps_api_key_missing",
        "Google Maps API key is not configured. Set MT_GOOGLE_MAPS_API_KEY.",
        GOOGLE_SOURCE,
        started,
    )


# --- Capabilities ---
def google_capabilities() -> dict[str, bool]:
    return {
        "calendar_read": bool_env("MT_GOOGLE_CALENDAR_READ_ENABLED", True),
        "calendar_write": bool_env("MT_GOOGLE_CALENDAR_WRITE_ENABLED", False),
        "gmail_read": bool_env("MT_GOOGLE_GMAIL_READ_ENABLED", True),
        "gmail_send": bool_env("MT_GOOGLE_GMAIL_SEND_ENABLED", False),
        "drive_read": bool_env("MT_GOOGLE_DRIVE_READ_ENABLED", True),
        "drive_write": bool_env("MT_GOOGLE_DRIVE_WRITE_ENABLED", False),
        "sheets_read": bool_env("MT_GOOGLE_SHEETS_READ_ENABLED", True),
        "sheets_write": bool_env("MT_GOOGLE_SHEETS_WRITE_ENABLED", False),
        "docs_read": bool_env("MT_GOOGLE_DOCS_READ_ENABLED", True),
        "docs_write": bool_env("MT_GOOGLE_DOCS_WRITE_ENABLED", False),
        "photos_read": bool_env("MT_GOOGLE_PHOTOS_READ_ENABLED", False),
        "photos_write": bool_env("MT_GOOGLE_PHOTOS_WRITE_ENABLED", False),
        "notebooklm": bool_env("MT_NOTEBOOKLM_ENABLED", True),
        "maps": bool_env("MT_GOOGLE_MAPS_ENABLED", True),
    }


def _granted_scopes(payload: JsonDict) -> list[str]:
    raw_scopes = payload.get("scopes") or payload.get("scope") or []
    if isinstance(raw_scopes, str):
        return [item.strip() for item in raw_scopes.split() if item.strip()]
    if isinstance(raw_scopes, list):
        return [str(item).strip() for item in raw_scopes if str(item).strip()]
    return []


def _scope_checks(granted_scopes: list[str]) -> dict[str, JsonDict]:
    granted = set(granted_scopes)
    checks: dict[str, JsonDict] = {}
    for capability, required in _GOOGLE_SCOPE_REQUIREMENTS.items():
        missing = [scope for scope in required if scope not in granted]
        checks[capability] = {
            "required_scopes": list(required),
            "granted": not missing,
            "missing_scopes": missing,
        }
    return checks


def google_auth_status() -> JsonDict:
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
            "error": "invalid token file: unable to parse token JSON",
        }

    granted_scopes = _granted_scopes(payload)

    return {
        "token_file": str(token_file),
        "token_present": True,
        "granted_scopes": granted_scopes,
        "scope_checks": _scope_checks(granted_scopes),
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
        GOOGLE_SOURCE,
        started,
    )
