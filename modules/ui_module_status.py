from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from modules.styles import scrollable, set_status

_ICON_POR_STATUS = {"ativo": "✅", "erro": "⚠️", "nao_instalado": "🔒"}
_TEXTO_POR_STATUS = {"ativo": "Ativo", "erro": "Erro ao carregar", "nao_instalado": "Não instalado"}
_ESTILO_POR_STATUS = {"ativo": "success", "erro": "warning", "nao_instalado": "muted"}


class ModuleStatusDialog(QDialog):
    """Painel com o status de cada módulo do framework neste PC.

    Recebe a lista já calculada pelo FrameworkApp (que já sabe, pra cada
    módulo, se o widget foi instanciado, falhou ao carregar ou nem está
    instalado) em vez de recalcular - evita duplicar a lógica que já existe
    em _safe_instantiate/_add_locked_tab.
    """

    def __init__(self, module_states: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Painel de módulos")
        self.resize(440, 460)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)

        title = QLabel("Status dos módulos")
        title.setObjectName("titleLabel")
        outer.addWidget(title)

        ativos = sum(1 for m in module_states if m["status"] == "ativo")
        subtitle = QLabel(f"{ativos} de {len(module_states)} módulos ativos neste PC.")
        subtitle.setObjectName("lockedModuleDesc")
        outer.addWidget(subtitle)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)

        for module in module_states:
            container_layout.addWidget(self._build_row(module))
        container_layout.addStretch()

        outer.addWidget(scrollable(container), 1)

    @staticmethod
    def _build_row(module: dict) -> QFrame:
        row = QFrame()
        row.setObjectName("lockedModuleCard")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)

        status = module.get("status", "nao_instalado")

        lbl_icon = QLabel(_ICON_POR_STATUS.get(status, "🔒"))
        lbl_icon.setStyleSheet("font-size: 20px;")
        layout.addWidget(lbl_icon)

        lbl_label = QLabel(module["label"])
        lbl_label.setObjectName("lockedModuleTitle")
        lbl_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(lbl_label, 1)

        lbl_status = QLabel()
        set_status(lbl_status, _ESTILO_POR_STATUS.get(status, "muted"), _TEXTO_POR_STATUS.get(status, ""))
        layout.addWidget(lbl_status)

        return row
