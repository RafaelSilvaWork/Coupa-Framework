import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from modules.updater import (
    GITHUB_REPO,
    _describe_github_api_error,
    _find_checksum_url,
    _read_cache,
    _verify_installer_checksum,
    _write_cache,
    build_installer_log_path,
)

LOCAL_INSTALLER_NAMES = ("CoupaFramework_Setup_v1.1.2.exe", "installer.exe")


class ModuleInstallWorker(QThread):
    """Baixa (se necessário) e instala silenciosamente um módulo do framework.

    Roda em background para não travar a UI durante a checagem/download do
    instalador. A instalação em si roda em modo silencioso (sem abrir a janela
    do assistente) via Inno Setup (/VERYSILENT) — o Windows não permite
    sobrescrever o próprio executável em uso, então o app chamador precisa se
    fechar logo depois de disparar a instalação.
    """

    progress_signal = pyqtSignal(int, str)  # percentual (-1 = indeterminado), mensagem
    finished_signal = pyqtSignal(bool, str)  # sucesso, mensagem de erro (se houver)

    def __init__(self, module_key: str):
        super().__init__()
        self.module_key = module_key

    def run(self):
        try:
            installer_path = self._find_installer()
        except requests.RequestException as exc:
            self.finished_signal.emit(False, f"Falha ao obter o instalador: {_describe_github_api_error(exc)}")
            return
        except (OSError, ValueError, KeyError) as exc:
            self.finished_signal.emit(False, f"Falha ao obter o instalador: {exc}")
            return

        if installer_path is None:
            self.finished_signal.emit(
                False,
                "Não foi possível localizar o instalador para este módulo. "
                "Verifique sua conexão com a internet e tente novamente.",
            )
            return

        self.progress_signal.emit(-1, "Iniciando instalação do módulo...")
        try:
            log_path = build_installer_log_path(f"installer_module_{self.module_key}")
            subprocess.Popen(
                [
                    installer_path,
                    "/VERYSILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                    f"/MODULE={self.module_key}",
                    f"/LOG={log_path}",
                ],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except OSError as exc:
            self.finished_signal.emit(False, f"Não foi possível iniciar o instalador: {exc}")
            return

        self.finished_signal.emit(True, "")

    def _find_installer(self) -> str | None:
        app_dir = Path(sys.executable).resolve().parent
        local_candidates = [app_dir / name for name in LOCAL_INSTALLER_NAMES]
        local_candidates.append(app_dir.parent / "installer_output" / LOCAL_INSTALLER_NAMES[0])
        for candidate in local_candidates:
            if candidate.exists():
                return str(candidate)

        self.progress_signal.emit(-1, "Verificando última versão disponível...")
        data = _read_cache("latest_release")
        if data is None:
            response = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                timeout=10,
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            data = response.json()
            _write_cache("latest_release", data)
        assets = data.get("assets", [])
        asset = next(
            (
                asset for asset in assets
                if isinstance(asset, dict) and asset.get("name", "").endswith(".exe")
            ),
            None,
        )
        if not asset:
            return None

        return self._download_asset(asset, assets)

    def _download_asset(self, asset: dict, assets: list) -> str:
        temp_path = Path(tempfile.gettempdir()) / asset["name"]
        url = asset.get("browser_download_url")
        if not isinstance(url, str):
            raise ValueError(f"Asset sem browser_download_url válido: {asset!r}")
        with requests.get(url, timeout=60, stream=True) as download_response:
            download_response.raise_for_status()
            total = int(download_response.headers.get("Content-Length", 0))
            baixado = 0
            with open(temp_path, "wb") as f:
                for chunk in download_response.iter_content(chunk_size=262144):
                    if not chunk:
                        continue
                    f.write(chunk)
                    baixado += len(chunk)
                    if total:
                        percentual = int(baixado * 100 / total)
                        self.progress_signal.emit(percentual, f"Baixando instalador... {percentual}%")
                    else:
                        self.progress_signal.emit(-1, "Baixando instalador...")

        self.progress_signal.emit(-1, "Verificando integridade do instalador...")
        checksum_url = _find_checksum_url(assets, asset.get("name", ""))
        verification_error = _verify_installer_checksum(str(temp_path), checksum_url or "")
        if verification_error:
            temp_path.unlink(missing_ok=True)
            raise ValueError(verification_error)
        return str(temp_path)
