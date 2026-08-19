import requests

from modules.updater import (
    _fetch_expected_checksum,
    _find_checksum_url,
    _format_version_label,
    _is_newer_version,
    _sha256_file,
    _verify_installer_checksum,
)


def test_older_release_is_not_considered_update():
    assert not _is_newer_version("1.1.0", "1.1.1")


def test_newer_release_is_considered_update():
    assert _is_newer_version("1.2.0", "1.1.1")


def test_v_prefix_is_supported():
    assert _is_newer_version("v1.1.2", "1.1.1")


def test_display_version_adds_v_prefix_when_missing():
    assert _format_version_label("1.2.0") == "v1.2.0"


def test_display_version_preserves_existing_v_prefix():
    assert _format_version_label("v1.2.0") == "v1.2.0"


def test_find_checksum_url_matches_installer_name():
    assets = [
        {"name": "CoupaFramework_Setup_v1.2.4.exe", "browser_download_url": "https://example/setup.exe"},
        {"name": "CoupaFramework_Setup_v1.2.4.exe.sha256", "browser_download_url": "https://example/setup.exe.sha256"},
    ]
    assert _find_checksum_url(assets, "CoupaFramework_Setup_v1.2.4.exe") == "https://example/setup.exe.sha256"


def test_find_checksum_url_returns_none_when_missing():
    assets = [{"name": "CoupaFramework_Setup_v1.2.4.exe", "browser_download_url": "https://example/setup.exe"}]
    assert _find_checksum_url(assets, "CoupaFramework_Setup_v1.2.4.exe") is None


def test_sha256_file_matches_known_digest(tmp_path):
    file_path = tmp_path / "content.bin"
    file_path.write_bytes(b"conteudo de teste")
    import hashlib
    expected = hashlib.sha256(b"conteudo de teste").hexdigest()
    assert _sha256_file(str(file_path)) == expected


def test_fetch_expected_checksum_accepts_plain_hash(monkeypatch):
    class _FakeResponse:
        text = "abc123"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse())
    assert _fetch_expected_checksum("https://example/setup.exe.sha256") == "abc123"


def test_fetch_expected_checksum_accepts_sha256sum_format(monkeypatch):
    class _FakeResponse:
        text = "ABC123  CoupaFramework_Setup_v1.2.4.exe\n"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse())
    assert _fetch_expected_checksum("https://example/setup.exe.sha256") == "abc123"


def test_fetch_expected_checksum_returns_none_on_request_error(monkeypatch):
    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError("sem rede")

    monkeypatch.setattr(requests, "get", _raise)
    assert _fetch_expected_checksum("https://example/setup.exe.sha256") is None


def test_verify_installer_checksum_fails_closed_without_checksum_url(tmp_path):
    file_path = tmp_path / "setup.exe"
    file_path.write_bytes(b"qualquer coisa")
    assert _verify_installer_checksum(str(file_path), "") is not None


def test_verify_installer_checksum_passes_when_hash_matches(tmp_path, monkeypatch):
    file_path = tmp_path / "setup.exe"
    file_path.write_bytes(b"conteudo real")
    import hashlib
    monkeypatch.setattr(
        "modules.updater._fetch_expected_checksum",
        lambda url: hashlib.sha256(b"conteudo real").hexdigest(),
    )
    assert _verify_installer_checksum(str(file_path), "https://example/setup.exe.sha256") is None


def test_verify_installer_checksum_fails_when_hash_differs(tmp_path, monkeypatch):
    file_path = tmp_path / "setup.exe"
    file_path.write_bytes(b"conteudo adulterado")
    monkeypatch.setattr("modules.updater._fetch_expected_checksum", lambda url: "0" * 64)
    assert _verify_installer_checksum(str(file_path), "https://example/setup.exe.sha256") is not None
