import contextlib
import os

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.download_scraper import DownloadWorker
from modules.fluxo_orquestrador import get_modo_automatico
from modules.logger import UILogger
from modules.services.data_bus import DataBus
from modules.styles import scrollable, set_status


class OrcamentoDownloaderWidget(QWidget):
    automatico_finished = pyqtSignal(bool, str)

    def __init__(self, parent_framework):
        super().__init__()
        self.parent_fw = parent_framework
        self.pasta_download = ""
        self.worker = None
        # Melhoria 5: ModoAutomatico é um singleton centralizado em
        # fluxo_orquestrador.get_modo_automatico() — as abas compartilham a MESMA instância.
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        left_container = QWidget()
        left_panel = QVBoxLayout(left_container)

        pasta_group = QGroupBox("Pasta de Destino")
        pasta_layout = QHBoxLayout()
        self.lbl_pasta = QLabel("Nenhuma pasta selecionada")
        set_status(self.lbl_pasta, "muted")
        self.btn_pasta = QPushButton("Selecionar Pasta")
        self.btn_pasta.clicked.connect(self.selecionar_pasta)
        self.btn_clear_pasta = QPushButton("Limpar")
        self.btn_clear_pasta.clicked.connect(self.limpar_pasta)
        self.btn_clear_pasta.setObjectName("btnClearField")
        pasta_layout.addWidget(self.lbl_pasta, 1)
        pasta_layout.addWidget(self.btn_pasta)
        pasta_layout.addWidget(self.btn_clear_pasta)
        pasta_group.setLayout(pasta_layout)
        left_panel.addWidget(pasta_group)

        req_group = QGroupBox("Lista de Requisi\u00e7\u00f5es para Download (importada da Aba 1)")
        req_layout = QVBoxLayout()
        self.lbl_import_status = QLabel("Aguardando dados da Aba 1 (\U0001f4e6 Extrator Inteligente)...")
        set_status(self.lbl_import_status, "muted")
        self.lbl_import_status.setWordWrap(True)
        self.txt_req_list = QTextEdit()
        self.txt_req_list.setPlaceholderText(
            "Digite as requisi\u00e7\u00f5es manualmente ou aguarde a importa\u00e7\u00e3o autom\u00e1tica da Aba 1."
        )
        self._user_editou_manualmente = False
        self.txt_req_list.textChanged.connect(self._marcar_edicao_manual)
        req_layout.addWidget(self.lbl_import_status)
        req_layout.addWidget(self.txt_req_list)
        req_group.setLayout(req_layout)
        left_panel.addWidget(req_group)

        btn_layout = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar Downloads")
        self.btn_iniciar.setObjectName("btnPrimary")
        self.btn_iniciar.clicked.connect(self.executar_downloads)

        self.btn_cancelar = QPushButton("Cancelar Processo")
        self.btn_cancelar.setObjectName("btnDanger")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self.cancelar_downloads)

        btn_layout.addWidget(self.btn_iniciar)
        btn_layout.addWidget(self.btn_cancelar)
        left_panel.addLayout(btn_layout)

        progresso_group = QGroupBox("Progresso de Downloads")
        progresso_layout = QVBoxLayout()
        progresso_layout.addWidget(QLabel("Progresso Geral de Requisi\u00e7\u00f5es:"))
        self.bar_geral = QProgressBar()
        self.bar_geral.setValue(0)
        progresso_layout.addWidget(self.bar_geral)
        progresso_layout.addWidget(QLabel("Progresso de Anexos (Download):"))
        self.bar_downloads = QProgressBar()
        self.bar_downloads.setValue(0)
        progresso_layout.addWidget(self.bar_downloads)
        progresso_group.setLayout(progresso_layout)
        left_panel.addWidget(progresso_group)

        right_panel = QVBoxLayout()
        log_group = QGroupBox("Logs de Execu\u00e7\u00e3o - Downloader")
        log_layout = QVBoxLayout()
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        log_layout.addWidget(self.txt_logs)
        log_group.setLayout(log_layout)
        right_panel.addWidget(log_group)

        layout.addWidget(scrollable(left_container), 2)
        layout.addLayout(right_panel, 3)

    def showEvent(self, event):
        super().showEvent(event)
        texto_atual = self.txt_req_list.toPlainText().strip()
        if not texto_atual:
            self.importar_da_aba1()

    def importar_da_aba1(self, forcar=False):
        """Importa requisicoes via DataBus centralizado (Itens 5 e 7)."""
        if self._user_editou_manualmente and not forcar:
            return

        requisicoes_com_pedido = DataBus.get_requisicoes_com_pedido()

        if not requisicoes_com_pedido:
            set_status(
                self.lbl_import_status, "muted",
                "Aguardando dados da Aba 1 (\U0001f4e6 Extrator Inteligente)...",
            )
            return

        self.txt_req_list.blockSignals(True)
        self.txt_req_list.setPlainText("\n".join(requisicoes_com_pedido))
        self.txt_req_list.blockSignals(False)
        set_status(
            self.lbl_import_status, "success",
            f"\u2705 {len(requisicoes_com_pedido)} requisicao(oes) importada(s) da Aba 1",
        )
        self._user_editou_manualmente = False
        # Feedback visual: borda verde por 1.5s
        from PyQt6.QtCore import QTimer
        self.txt_req_list.setStyleSheet("border: 2px solid #4ade80;")
        QTimer.singleShot(1500, lambda: self.txt_req_list.setStyleSheet(""))

    def selecionar_pasta(self) -> None:
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta onde os arquivos serao salvos")
        if pasta:
            self.pasta_download = os.path.normpath(pasta)
            set_status(self.lbl_pasta, "normal", self.pasta_download)

    def limpar_pasta(self) -> None:
        self.pasta_download = ""
        set_status(self.lbl_pasta, "muted", "Nenhuma pasta selecionada")

    def _marcar_edicao_manual(self) -> None:
        if self.txt_req_list.hasFocus():
            self._user_editou_manualmente = True

    def log(self, msg: str):
        UILogger.plain(self.txt_logs, msg)

    def check_prerequisites(self) -> tuple:
        if not self.pasta_download:
            return False, "Pasta de destino nao selecionada"
        return True, "Pronto"

    def executar_automatico(self):
        self.importar_da_aba1()
        if not self.pasta_download:
            self.automatico_finished.emit(False, "Aba 2 pulada: pasta de destino nao selecionada")
            # amazonq-ignore-next-line
            return
        self.executar_downloads(modo_automatico=True)

    def executar_downloads(self, modo_automatico: bool = False) -> None:
        if not self.pasta_download:
            if not modo_automatico:
                QMessageBox.warning(self, "Erro", "Selecione uma pasta de destino antes de comecar!")
            return

        req_text = self.txt_req_list.toPlainText()
        requisicoes = [line.strip() for line in req_text.split("\n") if line.strip()]

        if not requisicoes:
            self.importar_da_aba1()
            req_text = self.txt_req_list.toPlainText()
            requisicoes = [line.strip() for line in req_text.split("\n") if line.strip()]

        if not requisicoes:
            if not modo_automatico:
                QMessageBox.warning(
                    self, "Erro",
                    "Nenhuma requisicao disponivel. Execute a Aba 1 (Extrator Inteligente) primeiro!",
                )
            return

        self.btn_iniciar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.bar_geral.setValue(0)
        self.bar_downloads.setValue(0)

        if modo_automatico:
            get_modo_automatico().ativar("Aba 2")
        else:
            get_modo_automatico().desativar()

        self.log("\U0001f680 Iniciando processador de downloads em lote...")
        self.worker = DownloadWorker(requisicoes, self.pasta_download)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_req_signal.connect(self.bar_geral.setValue)
        self.worker.progress_down_signal.connect(self.bar_downloads.setValue)
        self.worker.finished_signal.connect(self.processo_finalizado)
        self.worker.start()

    def cancelar_downloads(self) -> None:
        if self.worker:
            self.worker.cancelar()
            self.log("\U0001f6d1 Solicitacao de cancelamento enviada...")

    @pyqtSlot(bool, list, list)
    def processo_finalizado(self, sucesso: bool, salvos: list, sem_arquivos: list):
        self.btn_iniciar.setEnabled(True)
        self.btn_cancelar.setEnabled(False)

        if os.path.exists(self.pasta_download):
            for f in os.listdir(self.pasta_download):
                if f.startswith("temp_"):
                    with contextlib.suppress(Exception):
                        # best-effort: limpeza de temporários, arquivo pode já ter sumido
                        os.remove(os.path.join(self.pasta_download, f))

        if not sucesso:
            self.log("\U0001f6d1 Operacao cancelada pelo usuario.")
            if not get_modo_automatico().ativo:
                QMessageBox.information(self, "Cancelado", "O processo de download foi cancelado.")
            return

        if get_modo_automatico().ativo:
            get_modo_automatico().desativar()
            resumo = f"\U0001f3c1 Aba 2 concluida: {len(salvos)} orcamento(s) salvo(s)."
            if sem_arquivos:
                resumo += f" | \u26a0\ufe0f {len(sem_arquivos)} requisicoes sem arquivos."
            self.log(resumo)
            self.automatico_finished.emit(True, resumo)
        else:
            linhas_resumo = [f"\U0001f3c1 Processo concluido: {len(salvos)} orcamento(s) salvo(s)."]
            if sem_arquivos:
                linhas_resumo.append(f"\u26a0\ufe0f Requisicoes sem arquivos validos: {len(sem_arquivos)}")
                linhas_resumo.append("Requisicoes: " + ", ".join(sem_arquivos))
            self.log(" | ".join(linhas_resumo))
            QMessageBox.information(self, "Concluido", "\n".join(linhas_resumo))
            self.parent_fw.tab_widget.setCurrentIndex(2)

