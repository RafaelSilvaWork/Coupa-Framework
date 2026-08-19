from datetime import datetime

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QFrame

from modules.styles import scrollable, set_status
from modules.updater import VersionManager, CURRENT_VERSION, _format_version_label


def _format_published_date(iso_text: str) -> str:
    if not iso_text:
        return ""
    try:
        return datetime.strptime(iso_text, "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y")
    except ValueError:
        return ""


class VersionHistoryDialog(QDialog):
    """Lista as versões publicadas no GitHub e permite instalar qualquer uma
    delas, inclusive uma mais antiga que a atual (rollback manual)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histórico de versões")
        self.resize(480, 480)

        self._version_manager = VersionManager(self)
        self._version_manager.releases_loaded.connect(self._on_releases_loaded)
        self._version_manager.list_error.connect(self._on_list_error)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Versões publicadas")
        title.setObjectName("titleLabel")
        title_row.addWidget(title, 1)

        self.btn_refresh = QPushButton("🔄 Atualizar")
        self.btn_refresh.setToolTip(
            "A lista fica em cache por até 15 minutos - use aqui para forçar "
            "uma checagem imediata (ex: acabou de publicar uma versão nova)."
        )
        self.btn_refresh.clicked.connect(self._refresh_releases)
        title_row.addWidget(self.btn_refresh)
        outer.addLayout(title_row)

        subtitle = QLabel(
            "Escolha uma versão para instalar. Instalar uma versão mais antiga "
            "que a atual funciona como um rollback."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("lockedModuleDesc")
        outer.addWidget(subtitle)

        self.lbl_status = QLabel("Carregando versões...")
        set_status(self.lbl_status, "muted")
        outer.addWidget(self.lbl_status)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()
        outer.addWidget(scrollable(self._list_container), 1)

        self._version_manager.list_releases()

    def _refresh_releases(self):
        self.btn_refresh.setEnabled(False)
        self._clear_list()
        self.lbl_status.setVisible(True)
        set_status(self.lbl_status, "muted", "Carregando versões...")
        self._version_manager.list_releases(force=True)

    def _clear_list(self):
        # Remove tudo menos o addStretch() do final (mantido para as linhas
        # ficarem no topo em vez de se espalharem pela área toda).
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _on_list_error(self, err: str):
        self.btn_refresh.setEnabled(True)
        set_status(self.lbl_status, "error", f"❌ Não foi possível carregar as versões: {err}")

    def _on_releases_loaded(self, releases: list):
        self.btn_refresh.setEnabled(True)
        self._clear_list()
        if not releases:
            set_status(self.lbl_status, "muted", "Nenhuma versão publicada encontrada.")
            return

        self.lbl_status.setVisible(False)
        for release in releases:
            row = self._build_row(release)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _build_row(self, release: dict) -> QFrame:
        row = QFrame()
        row.setObjectName("lockedModuleCard")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        is_current = release["label"] == _format_version_label(CURRENT_VERSION)

        lbl_tag = QLabel(release["label"] + ("  (versão atual)" if is_current else ""))
        lbl_tag.setObjectName("lockedModuleTitle")
        lbl_tag.setStyleSheet("font-size: 15px;")
        info_layout.addWidget(lbl_tag)

        date_text = _format_published_date(release.get("published_at", ""))
        if date_text:
            lbl_date = QLabel(f"Publicada em {date_text}")
            lbl_date.setObjectName("lockedModuleDesc")
            info_layout.addWidget(lbl_date)

        layout.addLayout(info_layout, 1)

        btn = QPushButton("Versão atual" if is_current else "Instalar")
        btn.setEnabled(not is_current)
        btn.setObjectName("btnClear" if is_current else "btnPrimary")
        if not is_current:
            checksum_url = release.get("checksum_url", "")
            btn.clicked.connect(
                lambda _checked=False, url=release["asset_url"], checksum_url=checksum_url, label=release["label"]:
                    self._version_manager.install_version(url, checksum_url, label)
            )
        layout.addWidget(btn)

        return row
