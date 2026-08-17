import json
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

logger = logging.getLogger(__name__)

GITHUB_REPO = "RafaelSilvaWork/Coupa-Framework"
CURRENT_VERSION = "1.2.2"

# Suaviza o limite de 60 requisições/hora sem autenticação da API do GitHub -
# fácil de estourar em redes com IP compartilhado, onde várias pessoas abrem
# o app (ou a tela de versões) ao mesmo tempo. Só encurta o tempo até uma
# atualização recém-publicada ser percebida; não afeta o fluxo de download/
# instalação em si.
CACHE_TTL_SECONDS = 900


def _app_data_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "CoupaFramework"


def build_installer_log_path(prefix: str) -> str:
    """Caminho de log para uma execução silenciosa do instalador (flag /LOG).

    Sem isso, uma instalação silenciosa que falha (como o bug do "{app}"
    expandido cedo demais) não deixa nenhum rastro em disco para diagnóstico -
    só o que aparecer na tela, se aparecer. Usa a mesma pasta de logs que
    modules/logger.py já usa para o app em si.
    """
    log_dir = _app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(log_dir / f"{prefix}_{timestamp}.log")


def _cache_dir() -> Path:
    return _app_data_dir() / "cache"


def _read_cache(key: str):
    """Lê uma resposta da API do GitHub cacheada há menos de CACHE_TTL_SECONDS.

    Retorna None tanto se não houver cache quanto se ele estiver expirado -
    nos dois casos o chamador deve buscar na rede normalmente.
    """
    try:
        entry = json.loads((_cache_dir() / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - entry.get("cached_at", 0) > CACHE_TTL_SECONDS:
        return None
    return entry.get("payload")


def _write_cache(key: str, payload) -> None:
    try:
        cache_dir = _cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{key}.json").write_text(
            json.dumps({"cached_at": time.time(), "payload": payload}),
            encoding="utf-8",
        )
    except OSError:
        logger.warning("Não foi possível gravar cache da API do GitHub (%s)", key)


def _describe_github_api_error(exc: Exception) -> str:
    """Traduz erros comuns da API do GitHub para uma mensagem acionável.

    Sem isso, um 403 de limite de requisições ou um 503 de instabilidade
    aparecem pro usuário como texto cru de exceção HTTP, sem deixar claro se
    o problema é a rede dele, algo no app, ou só o GitHub temporariamente
    limitado/instável.
    """
    response = getattr(exc, "response", None)
    if response is not None:
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            return (
                "Limite de requisições do GitHub atingido (comum em redes com "
                "IP compartilhado). Tente novamente em alguns minutos."
            )
        if response.status_code == 503:
            return "O GitHub está instável no momento. Tente novamente em alguns minutos."
    return str(exc)


def _normalize_version(value: str) -> Optional[tuple[int, int, int]]:
    text = (value or "").strip().lstrip("vV")
    if not text:
        return None
    parts = text.split(".")
    if len(parts) != 3:
        return None
    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        return None


def _format_version_label(version: str) -> str:
    normalized = (version or "").strip()
    if not normalized:
        return ""
    return normalized if normalized.startswith("v") else f"v{normalized}"


def _is_newer_version(latest_tag: str, current_version: str) -> bool:
    latest = _normalize_version(latest_tag)
    current = _normalize_version(current_version)
    if latest is None or current is None:
        return False
    return latest > current


def _start_installer(installer_path: str, parent_widget=None) -> Optional[subprocess.Popen]:
    """Dispara o instalador silenciosamente, sem fechar o app atual.

    Compartilhado pelo fluxo de atualização automática e pelo fluxo manual de
    instalar uma versão específica (rollback) - ambos terminam do mesmo jeito.
    Quem chama é responsável por aguardar o processo e fechar o app (ver
    _InstallWaitThread) - não fazemos isso aqui para o diálogo de progresso
    poder continuar visível durante a instalação.
    """
    try:
        log_path = build_installer_log_path("installer_update")
        return subprocess.Popen(
            [installer_path, "/SILENT", "/CLOSEAPPLICATIONS", "/CURRENTUSER", f"/LOG={log_path}"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    except OSError as exc:
        logger.exception("Falha ao iniciar o instalador: %s", exc)
        QMessageBox.critical(parent_widget, "Erro ao atualizar", f"Não foi possível iniciar o instalador: {exc}")
        return None


class _CheckThread(QThread):
    update_found = pyqtSignal(str, str)  # (latest_tag, asset_url)

    def run(self):
        try:
            data = _read_cache("latest_release")
            if data is None:
                response = requests.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                    timeout=5,
                    headers={"Accept": "application/vnd.github+json"},
                )
                response.raise_for_status()
                data = response.json()
                _write_cache("latest_release", data)
            tag = data.get("tag_name", "")
            if not tag or not _is_newer_version(tag, CURRENT_VERSION):
                return
            asset_url = next(
                (
                    asset.get("browser_download_url")
                    for asset in data.get("assets") or []
                    if isinstance(asset, dict) and asset.get("name", "").endswith(".exe")
                ),
                None,
            )
            if asset_url:
                self.update_found.emit(tag, asset_url)
        except requests.RequestException as exc:
            logger.exception("Falha ao verificar atualização no GitHub: %s", _describe_github_api_error(exc))
        except ValueError as exc:
            logger.exception("Resposta inválida da API do GitHub: %s", exc)


class _DownloadThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            response = requests.get(self._url, stream=True, timeout=60)
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0) or 0)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
            try:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self.progress.emit(int(downloaded * 100 / total))
                tmp.flush()
            finally:
                tmp.close()
            self.finished.emit(tmp.name)
        except requests.RequestException as exc:
            logger.exception("Falha ao baixar atualização: %s", exc)
            self.error.emit(_describe_github_api_error(exc))
        except OSError as exc:
            logger.exception("Falha ao gravar arquivo temporário da atualização: %s", exc)
            self.error.emit(str(exc))


class _InstallWaitThread(QThread):
    """Aguarda o processo do instalador terminar - rede de segurança.

    Na prática, installer.iss tem CloseApplications=yes e o instalador é
    chamado com /CLOSEAPPLICATIONS: assim que ele precisa sobrescrever
    CoupaFramework.exe, o Restart Manager do Windows encerra este processo
    sozinho, e essa thread nunca chega a emitir finished_wait. Ela só importa
    se isso não acontecer (ex: instalação falhou antes de chegar lá) - nesse
    caso fechamos o diálogo e o app manualmente quando o instalador retornar.
    """

    finished_wait = pyqtSignal()

    def __init__(self, process: subprocess.Popen):
        super().__init__()
        self._process = process

    def run(self):
        self._process.wait()
        self.finished_wait.emit()


class _DownloadProgressFlow(QObject):
    """Baixa um asset com diálogo de progresso e dispara o instalador ao final.

    Compartilhado por UpdateManager e VersionManager - ambos baixam um asset do
    GitHub, mostram uma barra de progresso modal e, ao terminar, rodam o mesmo
    instalador silencioso; só muda o texto do diálogo e o asset de origem. O
    mesmo diálogo permanece aberto (trocando para uma fase indeterminada
    "Instalando...") até o instalador assumir - em vez de fechar o app assim
    que o download termina, o que deixava um intervalo sem nenhuma janela
    visível enquanto o instalador rodava em segundo plano.
    """

    error = pyqtSignal(str)

    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self._parent_widget = parent_widget
        self._progress_dlg = None
        self._download_thread = None
        self._install_wait_thread = None

    def start(self, asset_url: str, dialog_title: str, dialog_label: str):
        self._progress_dlg = QProgressDialog(dialog_label, None, 0, 100, self._parent_widget)
        self._progress_dlg.setWindowTitle(dialog_title)
        self._progress_dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._progress_dlg.setCancelButton(None)
        self._progress_dlg.show()

        self._download_thread = _DownloadThread(asset_url)
        self._download_thread.progress.connect(self._progress_dlg.setValue)
        self._download_thread.finished.connect(self._on_downloaded)
        self._download_thread.error.connect(self._on_error)
        self._download_thread.start()

    def _on_downloaded(self, path: str):
        # O instalador silencioso não expõe percentual de progresso, então a
        # barra vira indeterminada (setRange(0, 0)) para a fase de instalação.
        self._progress_dlg.setLabelText("Instalando...")
        self._progress_dlg.setRange(0, 0)

        process = _start_installer(path, self._parent_widget)
        if process is None:
            self._progress_dlg.close()
            return

        self._install_wait_thread = _InstallWaitThread(process)
        self._install_wait_thread.finished_wait.connect(self._on_install_finished)
        self._install_wait_thread.start()

    def _on_install_finished(self):
        self._progress_dlg.close()
        QApplication.quit()

    def _on_error(self, err: str):
        self._progress_dlg.close()
        self.error.emit(err)


class UpdateManager(QObject):
    # Emitido quando existe atualização disponível mas o usuário optou por não
    # instalar agora (ou uma tentativa de download falhou) - carrega o rótulo
    # da versão (ex: "v1.1.5") para quem quiser oferecer um jeito de retomar
    # a atualização mais tarde sem esperar o app reabrir.
    update_declined = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_widget = parent
        self._check_thread = _CheckThread()
        self._check_thread.update_found.connect(self._on_update_found)
        self._flow = None
        self._latest_tag = ""
        self._asset_url = ""

    def start(self):
        self._check_thread.start()

    def _on_update_found(self, latest_tag: str, asset_url: str):
        self._latest_tag = latest_tag
        self._asset_url = asset_url
        self._prompt_update()

    def _prompt_update(self):
        msg = QMessageBox(self._parent_widget)
        msg.setWindowTitle("Atualização disponível")
        latest_label = _format_version_label(self._latest_tag)
        current_label = _format_version_label(CURRENT_VERSION)
        msg.setText(
            f"Nova versão disponível: <b>{latest_label}</b><br>"
            f"Versão atual: {current_label}<br><br>"
            "Deseja atualizar agora? O aplicativo será fechado automaticamente."
        )
        msg.setIcon(QMessageBox.Icon.Information)
        btn_sim = msg.addButton("Atualizar agora", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Agora não", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() != btn_sim:
            self.update_declined.emit(latest_label)
            return

        self._start_download()

    def start_download_now(self):
        """Retoma a atualização já detectada, sem perguntar de novo.

        Chamada pelo botão manual que fica visível depois que o usuário clica
        em "Agora não" no prompt inicial - o clique no botão já É a
        confirmação, não faz sentido perguntar de novo.
        """
        if not self._asset_url:
            return
        self._start_download()

    def _start_download(self):
        self._flow = _DownloadProgressFlow(self._parent_widget)
        self._flow.error.connect(self._on_error)
        self._flow.start(self._asset_url, "Atualizando", "Baixando atualização...")

    def _on_error(self, err: str):
        QMessageBox.critical(self._parent_widget, "Erro na atualização", f"Falha ao baixar: {err}")
        # Reoferece o botão manual para o usuário poder tentar de novo sem
        # precisar reabrir o aplicativo.
        self.update_declined.emit(_format_version_label(self._latest_tag))


class _ListReleasesThread(QThread):
    releases_loaded = pyqtSignal(list)  # lista de dicts: tag, label, asset_url, published_at
    error = pyqtSignal(str)

    def __init__(self, force: bool = False):
        super().__init__()
        self._force = force

    def run(self):
        try:
            data = None if self._force else _read_cache("releases_list")
            if data is None:
                response = requests.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}/releases",
                    timeout=10,
                    headers={"Accept": "application/vnd.github+json"},
                    params={"per_page": 15},
                )
                response.raise_for_status()
                data = response.json()
                _write_cache("releases_list", data)

            releases = []
            for item in data:
                if not isinstance(item, dict) or item.get("draft"):
                    continue
                tag = item.get("tag_name", "")
                asset_url = next(
                    (
                        asset.get("browser_download_url")
                        for asset in item.get("assets") or []
                        if isinstance(asset, dict) and asset.get("name", "").endswith(".exe")
                    ),
                    None,
                )
                if not tag or not asset_url:
                    continue
                releases.append({
                    "tag": tag,
                    "label": _format_version_label(tag),
                    "asset_url": asset_url,
                    "published_at": item.get("published_at", ""),
                })
            self.releases_loaded.emit(releases)
        except requests.RequestException as exc:
            logger.exception("Falha ao listar versões no GitHub: %s", exc)
            self.error.emit(_describe_github_api_error(exc))
        except ValueError as exc:
            logger.exception("Resposta inválida da API do GitHub ao listar versões: %s", exc)
            self.error.emit(str(exc))


class VersionManager(QObject):
    """Lista releases publicadas no GitHub e instala uma versão específica.

    Usada pela tela de histórico de versões para permitir rollback: baixa o
    instalador daquela release e roda o mesmo fluxo silencioso de instalação
    usado pelo auto-update, só que apontando para a versão escolhida pelo
    usuário em vez da mais recente.
    """

    releases_loaded = pyqtSignal(list)
    list_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_widget = parent
        self._list_thread = None
        self._flow = None

    def list_releases(self, force: bool = False):
        self._list_thread = _ListReleasesThread(force=force)
        self._list_thread.releases_loaded.connect(self.releases_loaded)
        self._list_thread.error.connect(self.list_error)
        self._list_thread.start()

    def install_version(self, asset_url: str, label: str):
        confirm = QMessageBox.question(
            self._parent_widget,
            "Confirmar instalação",
            f"Instalar a versão <b>{label}</b>?<br><br>"
            "O aplicativo será fechado automaticamente para concluir a instalação. "
            "Se for uma versão mais antiga que a atual, isso funciona como um rollback.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._flow = _DownloadProgressFlow(self._parent_widget)
        self._flow.error.connect(self._on_error)
        self._flow.start(asset_url, "Instalando versão", f"Baixando {label}...")

    def _on_error(self, err: str):
        QMessageBox.critical(self._parent_widget, "Erro ao instalar versão", f"Falha ao baixar: {err}")
