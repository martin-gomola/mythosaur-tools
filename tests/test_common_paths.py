import pytest

from services.mcp_server.plugins.common import resolve_under_base, validate_fetch_url


def test_resolve_under_base_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        resolve_under_base("../outside", tmp_path)


def test_resolve_under_base_allows_relative_child(tmp_path):
    resolved = resolve_under_base("docs/file.txt", tmp_path)
    assert resolved == (tmp_path / "docs" / "file.txt").resolve(strict=False)


class TestValidateFetchUrl:
    def test_allows_https(self):
        validate_fetch_url("https://example.com/page")

    def test_allows_http(self):
        validate_fetch_url("http://example.com/page")

    def test_blocks_file_scheme(self):
        with pytest.raises(ValueError, match="scheme not allowed"):
            validate_fetch_url("file:///etc/passwd")

    def test_blocks_ftp_scheme(self):
        with pytest.raises(ValueError, match="scheme not allowed"):
            validate_fetch_url("ftp://host/data")

    def test_blocks_localhost(self):
        with pytest.raises(ValueError, match="localhost"):
            validate_fetch_url("http://localhost/admin")

    def test_blocks_loopback_ip(self):
        with pytest.raises(ValueError, match="blocked"):
            validate_fetch_url("http://127.0.0.1/secret")

    def test_blocks_private_10(self):
        with pytest.raises(ValueError, match="blocked"):
            validate_fetch_url("http://10.0.0.1/internal")

    def test_blocks_private_192(self):
        with pytest.raises(ValueError, match="blocked"):
            validate_fetch_url("http://192.168.1.1/admin")

    def test_blocks_link_local(self):
        with pytest.raises(ValueError, match="blocked"):
            validate_fetch_url("http://169.254.169.254/metadata")

    def test_blocks_ipv6_loopback(self):
        with pytest.raises(ValueError, match="blocked"):
            validate_fetch_url("http://[::1]/admin")

    def test_allows_public_ip(self):
        validate_fetch_url("https://8.8.8.8/dns")

    def test_blocks_no_hostname(self):
        with pytest.raises(ValueError, match="no hostname"):
            validate_fetch_url("http:///path")
