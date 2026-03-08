#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


READONLY_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata",
]

WORKSPACE_SCOPES = [
    *READONLY_SCOPES,
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/photoslibrary.appendonly",
    "https://www.googleapis.com/auth/photoslibrary.edit.appcreateddata",
]

SCOPE_PRESETS = {
    "readonly": READONLY_SCOPES,
    "workspace": WORKSPACE_SCOPES,
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        scope = item.strip()
        if not scope or scope in seen:
            continue
        seen.add(scope)
        ordered.append(scope)
    return ordered


def _token_scopes(token_path: Path) -> set[str]:
    try:
        payload = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    raw_scopes = payload.get("scopes") or []
    if isinstance(raw_scopes, str):
        return {scope.strip() for scope in raw_scopes.split() if scope.strip()}
    if isinstance(raw_scopes, list):
        return {str(scope).strip() for scope in raw_scopes if str(scope).strip()}
    return set()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or refresh the Google OAuth token used by mythosaur-tools."
    )
    parser.add_argument(
        "--credentials",
        default="secrets/google-credentials.json",
        help="Path to the Google OAuth client credentials JSON.",
    )
    parser.add_argument(
        "--token",
        default="secrets/google-token.json",
        help="Path to write the authorized user token JSON.",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(SCOPE_PRESETS),
        default="workspace",
        help="Scope preset to request.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Additional OAuth scope to request. Repeat as needed.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore any existing token and run a fresh OAuth consent flow.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the local OAuth callback server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port for the local OAuth callback server. Use 0 for an ephemeral port.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open the browser; print the consent URL instead.",
    )
    return parser.parse_args()


def _load_existing_token(token_path: Path, scopes: list[str]) -> Credentials | None:
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except RefreshError as exc:
            message = str(exc)
            if "invalid_scope" in message:
                print("Existing token refresh failed due to invalid_scope.")
                print("Running a fresh OAuth consent flow to upgrade the token.")
                return None
            raise
    if not creds.valid:
        return None

    granted_scopes = _token_scopes(token_path)
    requested_scopes = set(scopes)
    if granted_scopes and not requested_scopes.issubset(granted_scopes):
        missing = sorted(requested_scopes - granted_scopes)
        print(f"Existing token is missing requested scopes: {', '.join(missing)}")
        print("Running a fresh OAuth consent flow to upgrade the token.")
        return None

    return creds


def main() -> int:
    args = _parse_args()
    credentials_path = Path(args.credentials).expanduser().resolve(strict=False)
    token_path = Path(args.token).expanduser().resolve(strict=False)
    scopes = _dedupe([*SCOPE_PRESETS[args.preset], *args.scope])

    if not credentials_path.exists():
        raise SystemExit(f"Missing credentials file: {credentials_path}")

    token_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.force:
        existing = _load_existing_token(token_path, scopes)
        if existing is not None:
            print(f"Token already valid: {token_path}")
            print(f"Scopes: {', '.join(scopes)}")
            return 0

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    creds = flow.run_local_server(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        authorization_prompt_message="Open this URL in your browser: {url}",
        success_message="Google authorization complete. You can close this window.",
        access_type="offline",
        prompt="consent",
    )
    token_path.write_text(creds.to_json(), encoding="utf-8")

    print(f"Wrote token: {token_path}")
    print(f"Credentials: {credentials_path}")
    print(f"Scopes: {', '.join(scopes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
