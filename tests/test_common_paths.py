import pytest

from services.mcp_server.plugins.common import resolve_under_base


def test_resolve_under_base_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        resolve_under_base("../outside", tmp_path)


def test_resolve_under_base_allows_relative_child(tmp_path):
    resolved = resolve_under_base("docs/file.txt", tmp_path)
    assert resolved == (tmp_path / "docs" / "file.txt").resolve(strict=False)
