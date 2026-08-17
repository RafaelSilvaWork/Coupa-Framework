import sys
import traceback
from typing import NamedTuple, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QStatusBar,
    QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout,
    QTextEdit, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from modules import (
    CoupaExtractorWidget, OrcamentoDownloaderWidget,
    PedidoPdfGeneratorWidget, RenomeadorWidget, OrganizadorWidget,
    EmailSenderWidget, ProfileManagerWidget, IMPORT_ERRORS
)
from modules.styles import APP_STYLESHEET, set_status
from modules.playwright_pool import cleanup_playwright_pool
from modules.updater import UpdateManager
from modules.ui_versions import VersionHistoryDialog
from modules.ui_module_status import ModuleStatusDialog
from modules.feature_selection import is_module_enabled
from modules.module_installer import ModuleInstallWorker
from modules.telemetry import init_telemetry


class ModuleSpec(NamedTuple):
    """Descreve uma aba/módulo do framework - fonte única de verdade.

    widget_class pode ser None se o import falhou (ver modules/__init__.py);
    class_name fica separado porque nesse caso não dá pra pegar o nome a
    partir da classe. class_name também é a chave usada em IMPORT_ERRORS.
    attr é o nome do atributo em FrameworkApp (ex: self.tab_coupa) - outros
    módulos (ui_coupa.py, DataBus) acessam a instância por esse nome.
    """

    key: str
    attr: str
    widget_class: Optional[type]
    class_name: str
    label: str


# Única lista com todos os módulos/abas do framework. Adicionar ou remover um
# módulo só exige editar esta lista - instanciação, título da aba, mapeamento
# de erro de import e o painel de status (🧩) são todos derivados dela.
MODULES: list[ModuleSpec] = [
    ModuleSpec("extrator", "tab_coupa", CoupaExtractorWidget, "CoupaExtractorWidget", "📦 Extrator Inteligente"),
    ModuleSpec(
        "downloader", "tab_downloader", OrcamentoDownloaderWidget,
        "OrcamentoDownloaderWidget", "📥 Baixador de Orçamentos",
    ),
    ModuleSpec(
        "pdf", "tab_pdf_generator", PedidoPdfGeneratorWidget,
        "PedidoPdfGeneratorWidget", "📄 Gerador de PDF de Pedidos",
    ),
    ModuleSpec("renomeador", "tab_renomeador", RenomeadorWidget, "RenomeadorWidget", "📝 Renomeador"),
    ModuleSpec("organizador", "tab_organizador", OrganizadorWidget, "OrganizadorWidget", "🗂️ Organizador"),
    ModuleSpec("email", "tab_email_sender", EmailSenderWidget, "EmailSenderWidget", "📧 Disparo de E-mails"),
    ModuleSpec(
        "perfis", "tab_manage_profiles", ProfileManagerWidget,
        "ProfileManagerWidget", "👥 Gerenciar Perfis",
    ),
]

_MODULES_BY_KEY = {module.key: module for module in MODULES}


def _resolve_module_error(module_key: str) -> Optional[str]:
    """Erro de import salvo para este módulo, se houver.

    IMPORT_ERRORS pode estar preenchido pela chave da classe widget (falha
    durante `from modules import ...`) ou pela module_key (falha ao
    instanciar em _safe_instantiate), então checamos as duas.
    """
    class_name = _MODULES_BY_KEY[module_key].class_name
    return IMPORT_ERRORS.get(class_name) or IMPORT_ERRORS.get(module_key)


def build_tab_title(module_key: str, enabled: bool) -> str:
    base_title = _MODULES_BY_KEY[module_key].label
    return f"🔒 {base_title}" if not enabled else base_title


class LockedModuleWidget(QWidget):
    """Tela exibida no lugar de uma aba quando o módulo correspondente não
    está disponível. Cobre dois cenários distintos:

    - Módulo nunca instalado neste PC (instalação seletiva não marcou este
      módulo, ou ele foi removido depois) -> oferece "Baixar este módulo".
    - Módulo deveria estar instalado mas falhou ao carregar (dependência
      ausente, arquivo corrompido, etc) -> mostra o erro real e oferece
      "Reinstalar módulo" para tentar corrigir baixando os arquivos de novo.
    """

    FECHAMENTO_AUTOMATICO_SEGUNDOS = 5

    def __init__(self, parent, module_key: str, module_label: str, error_detail: str | None = None):
        super().__init__(parent)
        self.module_key = module_key
        self.module_label = module_label
        self.error_detail = error_detail
        self._segundos_restantes = self.FECHAMENTO_AUTOMATICO_SEGUNDOS

        outer_layout = QVBoxLayout(self)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("lockedModuleCard")
        card.setFixedWidth(440)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(16)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("⚠️" if error_detail else "🔒")
        icon_label.setObjectName("lockedModuleIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_status(icon_label, "warning" if error_detail else "normal")
        card_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Módulo indisponível" if error_detail else "Módulo não instalado")
        title.setObjectName("lockedModuleTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        if error_detail:
            # Módulo deveria estar disponível, mas falhou ao carregar (dependência
            # ausente, erro de import, etc). Mostra o motivo real em vez de
            # apenas dizer "não instalado" — isso ajuda a diagnosticar no cliente.
            description = QLabel(
                f"O módulo <b>{module_label}</b> não pôde ser carregado neste PC "
                f"devido a um erro interno (veja detalhes abaixo)."
            )
        else:
            description = QLabel(
                f"O módulo <b>{module_label}</b> não está instalado neste cliente. "
                f"Baixe e instale para liberar esta aba."
            )
        description.setObjectName("lockedModuleDesc")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(description)

        if error_detail:
            error_box = QTextEdit()
            error_box.setReadOnly(True)
            error_box.setPlainText(error_detail)
            error_box.setFixedHeight(140)
            error_box.setStyleSheet(
                "font-family: Consolas, monospace; font-size: 11px; color: #ff7b72;"
            )
            card_layout.addWidget(error_box)

        button_row = QWidget()
        button_row_layout = QHBoxLayout(button_row)
        button_row_layout.setContentsMargins(0, 0, 0, 0)
        button_row_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.download_button = QPushButton("Reinstalar módulo" if error_detail else "Baixar este módulo")
        self.download_button.setObjectName("btnPrimary")
        self.download_button.clicked.connect(self._on_download_requested)
        button_row_layout.addWidget(self.download_button)
        card_layout.addWidget(button_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        card_layout.addWidget(self.progress_bar)

        self.lbl_install_status = QLabel("")
        self.lbl_install_status.setWordWrap(True)
        self.lbl_install_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_install_status.setVisible(False)
        card_layout.addWidget(self.lbl_install_status)

        self._install_worker: ModuleInstallWorker | None = None
        self._fechamento_timer: QTimer | None = None

        outer_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_download_requested(self):
        self.download_button.setEnabled(False)
        self.download_button.setText("Instalando...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        set_status(self.lbl_install_status, "muted", "Preparando instalação...")
        self.lbl_install_status.setVisible(True)

        self._install_worker = ModuleInstallWorker(self.module_key)
        self._install_worker.progress_signal.connect(self._on_install_progress)
        self._install_worker.finished_signal.connect(self._on_install_finished)
        self._install_worker.start()

    def _on_install_progress(self, percentual: int, mensagem: str):
        if percentual >= 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percentual)
        else:
            self.progress_bar.setRange(0, 0)
        set_status(self.lbl_install_status, "muted", mensagem)

    def _on_install_finished(self, sucesso: bool, mensagem: str):
        if not sucesso:
            self.progress_bar.setVisible(False)
            set_status(self.lbl_install_status, "error", f"❌ {mensagem}")
            self.download_button.setEnabled(True)
            self.download_button.setText("Reinstalar módulo" if self.error_detail else "Baixar este módulo")
            return

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.download_button.setVisible(False)
        self._segundos_restantes = self.FECHAMENTO_AUTOMATICO_SEGUNDOS
        self._atualizar_mensagem_sucesso()

        self._fechamento_timer = QTimer(self)
        self._fechamento_timer.timeout.connect(self._tick_fechamento)
        self._fechamento_timer.start(1000)

    def _atualizar_mensagem_sucesso(self):
        set_status(
            self.lbl_install_status,
            "success",
            "✅ Instalação concluída! O aplicativo será reiniciado automaticamente em "
            f"{self._segundos_restantes}s para ativar o módulo.",
        )

    def _tick_fechamento(self):
        self._segundos_restantes -= 1
        if self._segundos_restantes <= 0:
            self._fechamento_timer.stop()
            set_status(self.lbl_install_status, "success", "✅ Reiniciando agora...")
            QTimer.singleShot(300, self._fechar_aplicativo)
            return
        self._atualizar_mensagem_sucesso()

    def _fechar_aplicativo(self):
        # Fecha a janela principal (não só QApplication.quit()) para que o
        # closeEvent rode e libere os contextos do PlaywrightPool normalmente.
        self.window().close()


class FrameworkApp(QMainWindow):
    def __init__(self):
        super(FrameworkApp, self).__init__()
        self.setWindowTitle("Coupa Framework - Automação de Suprimentos")
        self.setGeometry(100, 100, 1400, 920)
        self.setMinimumSize(1024, 720)

        # --- Header / Top Bar ---
        # Sem stylesheet inline aqui - estilizado pela folha global
        # (QWidget#appHeader / QLabel#appHeaderTitle em styles.py), mesmo
        # motivo do ajuste na status bar: cor/estilo hardcoded direto no
        # widget fica fora da paleta central e mais difícil de manter.
        header = QWidget()
        header.setObjectName("appHeader")
        header.setFixedHeight(56)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        self.lbl_header_title = QLabel("\U0001f310 Coupa Framework - Automação de Suprimentos")
        self.lbl_header_title.setObjectName("appHeaderTitle")
        # Stretch=1: o título é o texto mais longo do header - sem prioridade
        # de espaço, ele é o primeiro a ser espremido/cortado quando a janela
        # fica estreita (perto do mínimo de 1024px) com os botões ao lado.
        header_layout.addWidget(self.lbl_header_title, 1)

        # Ordem no header, da esquerda pra direita: Nome - Atualização (só
        # quando pendente) - Painel - Versões. O botão de atualização fica
        # oculto por padrão e só aparece quando existe uma versão nova e o
        # usuário clicou em "Agora não" no aviso automático (ou uma tentativa
        # de download falhou) - assim ele não perde a chance de atualizar sem
        # precisar esperar o app reabrir.
        self.btn_update_available = QPushButton("")
        self.btn_update_available.setObjectName("btnWarning")
        self.btn_update_available.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update_available.setToolTip("Clique para baixar e instalar a atualização")
        self.btn_update_available.setVisible(False)
        self.btn_update_available.clicked.connect(self._on_update_button_clicked)
        header_layout.addWidget(self.btn_update_available)

        # Botão sempre visível com o resumo de quais módulos estão ativos
        # neste PC (ver ModuleStatusDialog) - self._module_states é montado
        # mais abaixo, depois que as abas são instanciadas.
        self.btn_module_panel = QPushButton("🧩 Painel")
        self.btn_module_panel.setObjectName("btnHeaderAction")
        self.btn_module_panel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_module_panel.setToolTip("Ver quais módulos estão ativos neste PC")
        self.btn_module_panel.clicked.connect(self._open_module_panel)
        header_layout.addWidget(self.btn_module_panel)

        # Botão sempre visível para abrir o histórico de versões publicadas e
        # instalar qualquer uma delas (inclusive uma mais antiga - rollback
        # manual caso a versão atual tenha algum problema).
        self.btn_version_history = QPushButton("🕘 Versões")
        self.btn_version_history.setObjectName("btnHeaderAction")
        self.btn_version_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_version_history.setToolTip("Ver e instalar versões anteriores (rollback)")
        self.btn_version_history.clicked.connect(self._open_version_history)
        header_layout.addWidget(self.btn_version_history)

        # --- Tab Widget ---
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        # Central widget wrapping header + tabs
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(header)
        central_layout.addWidget(self.tab_widget, 1)
        self.setCentralWidget(central)

        # --- Status Bar ---
        # Sem stylesheet inline aqui - o QStatusBar já é estilizado pela folha
        # global (APP_STYLESHEET, aplicada em app.setStyleSheet mais abaixo).
        # Uma sobrescrita local duplicava quase a mesma regra com valores
        # levemente diferentes (font-size, padding) e ainda não resolvia a cor
        # do texto, porque QLabel não herda "color" do QStatusBar pai - por
        # isso o rótulo usava a cor genérica de QLabel em vez da paleta.
        self.status_bar = QStatusBar()
        self.lbl_status = QLabel("Pronto")
        self.lbl_status.setObjectName("appStatusBarLabel")
        # Stretch=1 para o rótulo ocupar o espaço disponível e não ficar preso
        # ao tamanho calculado para o texto inicial "Pronto", cortando
        # mensagens de status mais longas.
        self.status_bar.addWidget(self.lbl_status, 1)
        self.setStatusBar(self.status_bar)

        # Instanciação das abas + painel de status (botão "🧩 Painel" no header).
        # Importante: só instanciamos se a classe realmente importou (não é None).
        # Se um widget falhou ao importar (dependência ausente no PC, por ex.),
        # ele cai automaticamente na aba bloqueada em vez de derrubar o app inteiro.
        self._module_states = []
        for module in MODULES:
            instance = self._safe_instantiate(module.widget_class, module.key)
            setattr(self, module.attr, instance)
            if instance is not None:
                self.tab_widget.addTab(instance, module.label)
            else:
                self._add_locked_tab(module.key)
            self._module_states.append(self._build_module_state(module.key, module.label, instance))

        # Conectar troca de aba para atualizar status
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Sincronizar perfis entre abas quando os módulos estiverem disponíveis
        if self.tab_manage_profiles is not None and self.tab_coupa is not None:
            self.tab_manage_profiles.profiles_changed.connect(self.tab_coupa.refresh_profiles)
        if self.tab_manage_profiles is not None and self.tab_email_sender is not None:
            self.tab_manage_profiles.profiles_changed.connect(self.tab_email_sender.refresh_profiles)

        # Verifica atualizações em background via QThread (UI sempre na thread principal)
        self._update_manager = UpdateManager(self)
        self._update_manager.update_declined.connect(self._show_update_available_button)
        self._update_manager.start()

    @staticmethod
    def _build_module_state(module_key: str, label: str, tab_widget) -> dict:
        if tab_widget is not None:
            return {"key": module_key, "label": label, "status": "ativo"}
        if _resolve_module_error(module_key):
            return {"key": module_key, "label": label, "status": "erro"}
        return {"key": module_key, "label": label, "status": "nao_instalado"}

    def _open_module_panel(self):
        dialog = ModuleStatusDialog(self._module_states, self)
        dialog.exec()

    def _open_version_history(self):
        dialog = VersionHistoryDialog(self)
        dialog.exec()

    def _show_update_available_button(self, latest_label: str):
        self.btn_update_available.setText(f"⬆ Atualizar para {latest_label}")
        self.btn_update_available.setEnabled(True)
        self.btn_update_available.setVisible(True)

    def _on_update_button_clicked(self):
        self.btn_update_available.setEnabled(False)
        self.btn_update_available.setText("Baixando atualização...")
        self._update_manager.start_download_now()

    def _safe_instantiate(self, widget_class, module_key: str):
        """Instancia o widget somente se a classe carregou de verdade (não é None)
        e o módulo está habilitado. Nunca chama None(...), que é o que causava o
        'NoneType' object is not callable ao rodar em outra máquina."""
        if widget_class is None:
            return None
        if not is_module_enabled(module_key):
            return None
        try:
            return widget_class(self)
        except Exception:
            error_text = traceback.format_exc()
            IMPORT_ERRORS[module_key] = error_text
            print(f"[ERRO] Falha ao inicializar o módulo '{module_key}':\n{error_text}")
            return None

    def _add_locked_tab(self, module_key: str):
        label = _MODULES_BY_KEY[module_key].label
        error_detail = _resolve_module_error(module_key)
        widget = LockedModuleWidget(self, module_key, label, error_detail=error_detail)
        self.tab_widget.addTab(widget, build_tab_title(module_key, False))

    def _on_tab_changed(self, index: int):
        tab_text = self.tab_widget.tabText(index).strip()
        self.lbl_status.setText(f"Aba ativa: {tab_text}")

    def set_status(self, message: str):
        self.lbl_status.setText(message)

    def closeEvent(self, event):
        """Item 3: Libera todos os contextos do PlaywrightPool ao fechar o app."""
        cleanup_playwright_pool()
        super().closeEvent(event)


if __name__ == "__main__":
    init_telemetry()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    window = FrameworkApp()
    window.show()
    sys.exit(app.exec())
