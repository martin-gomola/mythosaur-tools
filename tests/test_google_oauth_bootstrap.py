from __future__ import annotations

import importlib.util
from pathlib import Path

from google.auth.exceptions import RefreshError


def _load_bootstrap_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "google_oauth_bootstrap.py"
    spec = importlib.util.spec_from_file_location("google_oauth_bootstrap", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _InvalidScopeCreds:
    expired = True
    refresh_token = "refresh-token"
    valid = True

    def refresh(self, _request):
        raise RefreshError("invalid_scope: Bad Request")

    def to_json(self):
        return "{}"


class _ValidCreds:
    expired = False
    refresh_token = None
    valid = True


def test_load_existing_token_falls_back_to_fresh_flow_on_invalid_scope(tmp_path, monkeypatch, capsys):
    module = _load_bootstrap_module()
    token_path = tmp_path / "google-token.json"
    token_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        module.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: _InvalidScopeCreds(),
    )

    result = module._load_existing_token(
        token_path,
        ["https://www.googleapis.com/auth/photoslibrary.appendonly"],
    )

    assert result is None
    output = capsys.readouterr().out
    assert "invalid_scope" in output
    assert "fresh OAuth consent flow" in output


def test_load_existing_token_returns_valid_creds(tmp_path, monkeypatch):
    module = _load_bootstrap_module()
    token_path = tmp_path / "google-token.json"
    token_path.write_text('{"scopes":["scope-a"]}', encoding="utf-8")

    monkeypatch.setattr(
        module.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: _ValidCreds(),
    )

    result = module._load_existing_token(token_path, ["scope-a"])

    assert isinstance(result, _ValidCreds)
