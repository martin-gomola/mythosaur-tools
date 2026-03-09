from __future__ import annotations

import mimetypes
from typing import Any

from . import _auth
from ..common import ToolDef, err, now_ms, ok, parse_int, resolve_under_workspace


def _drive_recent_files(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _auth._capability_guard("google_drive_recent_files", "drive_read", started)
    if blocked:
        return blocked
    max_results = parse_int(args.get("max_results"), 10, minimum=1, maximum=50)
    query = (args.get("query") or "").strip()
    if len(query) > _auth._MAX_DRIVE_QUERY_LEN:
        return err(
            "google_drive_recent_files", "query_too_long",
            f"query exceeds {_auth._MAX_DRIVE_QUERY_LEN} characters",
            "google", started,
        )

    try:
        service = _auth._build_service("drive", "v3", _auth.DRIVE_SCOPES)
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
        return err("google_drive_recent_files", "drive_failed", _auth._safe_error_msg(exc), "google", started)

    return ok(
        "google_drive_recent_files",
        {"files": payload.get("files") or []},
        "google",
        started,
    )


def _drive_create_folder(args: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    blocked = _auth._capability_guard("google_drive_create_folder", "drive_write", started)
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
        service = _auth._build_service("drive", "v3", _auth.DRIVE_WRITE_SCOPES)
        payload = (
            service.files()
            .create(body=metadata, fields="id,name,mimeType,parents,webViewLink")
            .execute()
        )
    except Exception as exc:
        return err("google_drive_create_folder", "drive_create_failed", _auth._safe_error_msg(exc), "google", started)

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
    blocked = _auth._capability_guard("google_drive_create_text_file", "drive_write", started)
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
    size_err = _auth._validate_content_size("google_drive_create_text_file", content, _auth._MAX_CONTENT_BYTES, started)
    if size_err:
        return size_err
    if mime_type != "text/plain" and not _auth._MIME_TYPE_RE.match(mime_type):
        return err("google_drive_create_text_file", "invalid_mime_type", f"invalid mime_type: {mime_type}", "google", started)

    metadata: dict[str, Any] = {"name": file_name}
    if parent_folder_id:
        metadata["parents"] = [parent_folder_id]

    try:
        from googleapiclient.http import MediaInMemoryUpload

        service = _auth._build_service("drive", "v3", _auth.DRIVE_WRITE_SCOPES)
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
        return err("google_drive_create_text_file", "drive_create_failed", _auth._safe_error_msg(exc), "google", started)

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
    blocked = _auth._capability_guard("google_drive_upload_file", "drive_write", started)
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
        return err("google_drive_upload_file", "invalid_path", _auth._safe_error_msg(exc), "google", started)

    if not path.exists() or not path.is_file():
        return err(
            "google_drive_upload_file",
            "file_not_found",
            f"file not found: {path}",
            "google",
            started,
        )

    upload_name = file_name or path.name
    if mime_type and not _auth._MIME_TYPE_RE.match(mime_type):
        return err("google_drive_upload_file", "invalid_mime_type", f"invalid mime_type: {mime_type}", "google", started)
    upload_mime = mime_type or mimetypes.guess_type(upload_name)[0] or "application/octet-stream"
    metadata: dict[str, Any] = {"name": upload_name}
    if parent_folder_id:
        metadata["parents"] = [parent_folder_id]

    try:
        from googleapiclient.http import MediaFileUpload

        service = _auth._build_service("drive", "v3", _auth.DRIVE_WRITE_SCOPES)
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
        return err("google_drive_upload_file", "drive_upload_failed", _auth._safe_error_msg(exc), "google", started)

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


def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="google_drive_recent_files",
            plugin_id=_auth.GOOGLE_PLUGIN_ID,
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
            plugin_id=_auth.GOOGLE_PLUGIN_ID,
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
            name="google_drive_create_text_file",
            plugin_id=_auth.GOOGLE_PLUGIN_ID,
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
            name="google_drive_upload_file",
            plugin_id=_auth.GOOGLE_PLUGIN_ID,
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
    ]
