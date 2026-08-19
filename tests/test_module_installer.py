import hashlib
import sys

import pytest
import requests

from modules.module_installer import ModuleInstallWorker


def test_find_installer_prefers_local_file_in_app_dir(tmp_path, monkeypatch):
    fake_app_dir = tmp_path / "app"
    fake_app_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(fake_app_dir / "CoupaFramework.exe"))

    local_installer = fake_app_dir / "CoupaFramework_Setup_v1.1.2.exe"
    local_installer.write_bytes(b"fake installer")

    worker = ModuleInstallWorker("extrator")

    assert worker._find_installer() == str(local_installer)


def test_find_installer_checks_installer_output_folder(tmp_path, monkeypatch):
    fake_app_dir = tmp_path / "app"
    fake_app_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(fake_app_dir / "CoupaFramework.exe"))

    installer_output = tmp_path / "installer_output"
    installer_output.mkdir()
    local_installer = installer_output / "CoupaFramework_Setup_v1.1.2.exe"
    local_installer.write_bytes(b"fake installer")

    worker = ModuleInstallWorker("email")

    assert worker._find_installer() == str(local_installer)


class _FakeStreamResponse:
    def __init__(self, content: bytes):
        self._content = content
        self.headers = {"Content-Length": str(len(content))}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self._content


class _FakeChecksumResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        pass


def _fake_requests_get(content: bytes, checksum_text: str):
    def _fake_get(url, timeout=None, stream=False):
        if stream:
            return _FakeStreamResponse(content)
        return _FakeChecksumResponse(checksum_text)
    return _fake_get


def test_download_asset_installs_when_checksum_matches(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.module_installer.tempfile.gettempdir", lambda: str(tmp_path))
    content = b"conteudo real do instalador"
    expected_hash = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(requests, "get", _fake_requests_get(content, expected_hash))

    asset = {"name": "CoupaFramework_Setup_v1.2.4.exe", "browser_download_url": "https://example/setup.exe"}
    assets = [asset, {"name": "CoupaFramework_Setup_v1.2.4.exe.sha256", "browser_download_url": "https://example/setup.exe.sha256"}]

    worker = ModuleInstallWorker("extrator")
    result_path = worker._download_asset(asset, assets)

    assert result_path == str(tmp_path / asset["name"])
    assert (tmp_path / asset["name"]).read_bytes() == content


def test_download_asset_raises_and_removes_file_when_checksum_mismatches(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.module_installer.tempfile.gettempdir", lambda: str(tmp_path))
    content = b"conteudo adulterado"
    monkeypatch.setattr(requests, "get", _fake_requests_get(content, "0" * 64))

    asset = {"name": "CoupaFramework_Setup_v1.2.4.exe", "browser_download_url": "https://example/setup.exe"}
    assets = [asset, {"name": "CoupaFramework_Setup_v1.2.4.exe.sha256", "browser_download_url": "https://example/setup.exe.sha256"}]

    worker = ModuleInstallWorker("extrator")
    with pytest.raises(ValueError):
        worker._download_asset(asset, assets)

    assert not (tmp_path / asset["name"]).exists()


def test_download_asset_raises_when_no_checksum_asset_published(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.module_installer.tempfile.gettempdir", lambda: str(tmp_path))
    content = b"instalador de release antiga, sem checksum"
    monkeypatch.setattr(requests, "get", _fake_requests_get(content, ""))

    asset = {"name": "CoupaFramework_Setup_v1.1.2.exe", "browser_download_url": "https://example/setup.exe"}
    assets = [asset]  # sem asset .sha256 correspondente

    worker = ModuleInstallWorker("extrator")
    with pytest.raises(ValueError):
        worker._download_asset(asset, assets)

    assert not (tmp_path / asset["name"]).exists()
