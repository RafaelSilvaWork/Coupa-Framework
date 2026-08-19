import subprocess

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

import modules.updater as updater
from modules.updater import _DownloadProgressFlow, _InstallWaitThread, _start_installer


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


class _FakeProcess:
    def __init__(self, exit_code: int = 0):
        self._exit_code = exit_code
        self.wait_called = False

    def wait(self):
        self.wait_called = True
        return self._exit_code


def test_start_installer_launches_process_with_expected_flags(qt_app, monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    captured = {}

    def _fake_popen(args, **kwargs):
        captured["args"] = args
        return _FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    installer_path = str(tmp_path / "setup.exe")
    result = _start_installer(installer_path)

    assert isinstance(result, _FakeProcess)
    args = captured["args"]
    assert args[0] == installer_path
    assert "/SILENT" in args
    assert "/CLOSEAPPLICATIONS" in args
    assert "/CURRENTUSER" in args
    assert any(arg.startswith("/LOG=") for arg in args)


def test_start_installer_returns_none_and_warns_on_failure(qt_app, monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)

    def _raise(*a, **k):
        raise OSError("nao foi possivel iniciar o processo")

    monkeypatch.setattr(subprocess, "Popen", _raise)

    result = _start_installer(str(tmp_path / "setup.exe"))

    assert result is None


def test_install_wait_thread_emits_when_process_exits(qt_app):
    process = _FakeProcess(exit_code=0)
    thread = _InstallWaitThread(process)
    emitted = []
    thread.finished_wait.connect(lambda: emitted.append(True))

    thread.run()

    assert process.wait_called
    assert len(emitted) == 1


def test_download_progress_flow_starts_installer_and_quits_when_it_finishes(qt_app, monkeypatch):
    # _on_downloaded assume que start() já rodou e criou o diálogo - aqui
    # criamos um diálogo real "manualmente" pra poder chamar _on_downloaded
    # isolado, sem precisar de um download de verdade em segundo plano.
    flow = _DownloadProgressFlow(None)
    flow._progress_dlg = QProgressDialog("Baixando...", None, 0, 100, None)
    monkeypatch.setattr(updater, "_verify_installer_checksum", lambda path, checksum_url: None)

    started_with = {}

    def _fake_start_installer(path, parent_widget=None):
        started_with["path"] = path
        return _FakeProcess()

    monkeypatch.setattr(updater, "_start_installer", _fake_start_installer)

    quit_calls = []
    monkeypatch.setattr(updater.QApplication, "quit", staticmethod(lambda: quit_calls.append(True)))

    flow._on_downloaded("C:/fake/setup.exe")

    # _InstallWaitThread roda numa QThread real - aguarda ela terminar antes
    # de checar o resultado do sinal finished_wait -> _on_install_finished.
    assert flow._install_wait_thread.wait(2000)
    QApplication.processEvents()

    assert started_with["path"] == "C:/fake/setup.exe"
    assert quit_calls == [True]
    assert flow._progress_dlg.minimum() == 0
    assert flow._progress_dlg.maximum() == 0  # barra indeterminada


def test_download_progress_flow_closes_dialog_when_installer_fails_to_start(qt_app, monkeypatch):
    flow = _DownloadProgressFlow(None)
    flow._progress_dlg = QProgressDialog("Baixando...", None, 0, 100, None)
    monkeypatch.setattr(updater, "_verify_installer_checksum", lambda path, checksum_url: None)

    monkeypatch.setattr(updater, "_start_installer", lambda path, parent_widget=None: None)

    flow._on_downloaded("C:/fake/setup.exe")

    assert flow._install_wait_thread is None
    assert not flow._progress_dlg.isVisible()


def test_download_progress_flow_never_installs_when_checksum_verification_fails(qt_app, monkeypatch, tmp_path):
    flow = _DownloadProgressFlow(None)
    flow._progress_dlg = QProgressDialog("Baixando...", None, 0, 100, None)

    downloaded_file = tmp_path / "setup.exe"
    downloaded_file.write_bytes(b"conteudo adulterado")

    monkeypatch.setattr(
        updater, "_verify_installer_checksum",
        lambda path, checksum_url: "Verificação de integridade do instalador falhou (checksum não confere).",
    )

    install_calls = []
    monkeypatch.setattr(updater, "_start_installer", lambda path, parent_widget=None: install_calls.append(path))

    errors = []
    flow.error.connect(errors.append)

    flow._on_downloaded(str(downloaded_file))

    assert install_calls == []  # instalador nunca deve rodar sem checksum válido
    assert not downloaded_file.exists()  # arquivo suspeito é removido
    assert len(errors) == 1
    assert "checksum" in errors[0].lower()
    assert not flow._progress_dlg.isVisible()
