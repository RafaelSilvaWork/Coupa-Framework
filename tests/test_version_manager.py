from pathlib import Path

import pytest
import requests
from PyQt6.QtWidgets import QApplication

from modules.updater import _ListReleasesThread, build_installer_log_path


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_list_releases_skips_drafts_and_releases_without_exe_asset(qt_app, monkeypatch, tmp_path):
    # Isola o cache de respostas da API (ver modules/updater.py) numa pasta
    # temporária - sem isso, a resposta "de sucesso" fica gravada no
    # %APPDATA% real da máquina e o teste seguinte (que espera uma falha de
    # rede) lê esse cache em vez de bater no requests.get mockado.
    monkeypatch.setenv("APPDATA", str(tmp_path))

    payload = [
        {
            "tag_name": "v1.2.0",
            "draft": False,
            "published_at": "2026-08-07T14:12:12Z",
            "assets": [
                {"name": "CoupaFramework_Setup_v1.2.0.exe", "browser_download_url": "https://example/v1.2.0.exe"}
            ],
        },
        {
            "tag_name": "v1.1.9",
            "draft": True,  # release em rascunho - não deve aparecer para o usuário
            "assets": [{"name": "x.exe", "browser_download_url": "https://example/x.exe"}],
        },
        {
            "tag_name": "v1.1.8",
            "draft": False,
            "assets": [],  # sem instalador anexado - não dá pra instalar mesmo
        },
    ]
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(payload))

    thread = _ListReleasesThread()
    captured = []
    thread.releases_loaded.connect(captured.append)

    thread.run()

    assert len(captured) == 1
    releases = captured[0]
    assert len(releases) == 1
    assert releases[0]["tag"] == "v1.2.0"
    assert releases[0]["label"] == "v1.2.0"
    assert releases[0]["asset_url"] == "https://example/v1.2.0.exe"


def test_list_releases_emits_error_on_request_failure(qt_app, monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError("sem rede")

    monkeypatch.setattr(requests, "get", _raise)

    thread = _ListReleasesThread()
    errors = []
    thread.error.connect(errors.append)

    thread.run()

    assert len(errors) == 1


def test_build_installer_log_path_uses_appdata_logs_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    log_path = build_installer_log_path("installer_update")
    log_path_obj = Path(log_path)

    assert log_path_obj.parent == tmp_path / "CoupaFramework" / "logs"
    assert log_path_obj.parent.exists()
    assert log_path_obj.name.startswith("installer_update_")
    assert log_path_obj.suffix == ".log"
