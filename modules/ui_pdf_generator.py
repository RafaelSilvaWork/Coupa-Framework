import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QProgressBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSlot, pyqtSignal

from modules.fluxo_orquestrador import get_modo_automatico
from modules.pdf_generator import PdfGeneratorWorker
from modules.services.data_bus import DataBus
from modules.logger import UILogger
from modules.styles import set_status, scrollable


class PedidoPdfGeneratorWidget(QWidget):
    """Widget para geracao de PDFs de pedidos (Aba 3).

    Improvements:
        - Item 6: UILogger centralizado
        - Item 7: DataBus.get_pedidos_extraidos() em vez de acessar parent_fw.tab_coupa
        - Item 9: ModoAutomatico singleton compartilhado
        - Item 12: Nomenclatura padronizada em portugues (verificar_requisitos, selecionar_pasta)
        - Item 19: Type hints em metodos publicos
    """
    automatico_finished = pyqtSignal(bool, str)

    def __init__(self, parent_framework) -> None:
        super().__init__()
        self.parent_fw = parent_framework
        self.pasta_saida: str = ""
        self.worker: PdfGeneratorWorker | None = None
        self._user_editou_manualmente: bool = False
        # Melhoria 5: ModoAutomatico é um singleton centralizado em
        # fluxo_orquestrador.get_modo_automatico() — as abas compartilham a MESMA instância.
        self.init_ui()

    def init_ui(self) -> None:
        layout = QHBoxLayout(self)
        left_container = QWidget()
        left_panel = QVBoxLayout(left_container)

        pasta_group = QGroupBox("Caminho de Destino dos PDFs")
        pasta_layout = QHBoxLayout()
        self.lbl_pasta = QLabel("Nenhuma pasta selecionada")
        set_status(self.lbl_pasta, "muted")
        self.lbl_pasta.setWordWrap(True)
        self.btn_pasta = QPushButton("Escolher...")
        self.btn_pasta.clicked.connect(self.selecionar_pasta)
        self.btn_limpar_pasta = QPushButton("Limpar")
        self.btn_limpar_pasta.clicked.connect(self.limpar_pasta)
        self.btn_limpar_pasta.setObjectName("btnClearField")
        pasta_layout.addWidget(self.lbl_pasta, 1)
        pasta_layout.addWidget(self.btn_pasta)
        pasta_layout.addWidget(self.btn_limpar_pasta)
        pasta_group.setLayout(pasta_layout)
        left_panel.addWidget(pasta_group)

        pedidos_group = QGroupBox("Numeros de Pedidos (importados da Aba 1)")
        pedidos_layout = QVBoxLayout()
        self.lbl_import_status = QLabel("Aguardando dados da Aba 1 (📦 Extrator Inteligente)...")
        set_status(self.lbl_import_status, "muted")
        self.lbl_import_status.setWordWrap(True)
        self.txt_pedidos = QTextEdit()
        self.txt_pedidos.setPlaceholderText(
            "Digite os pedidos manualmente ou aguarde a importacao automatica da Aba 1."
        )
        self._user_editou_manualmente = False
        self.txt_pedidos.textChanged.connect(self._marcar_edicao_manual)
        pedidos_layout.addWidget(self.lbl_import_status)
        pedidos_layout.addWidget(self.txt_pedidos)
        pedidos_group.setLayout(pedidos_layout)
        left_panel.addWidget(pedidos_group)

        btn_layout = QHBoxLayout()
        self.btn_gerar = QPushButton("Iniciar Geracao de PDFs")
        self.btn_gerar.setObjectName("btnPrimary")
        self.btn_gerar.clicked.connect(self.iniciar_geracao)

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnDanger")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self.cancelar_geracao)

        btn_layout.addWidget(self.btn_gerar)
        btn_layout.addWidget(self.btn_cancelar)
        left_panel.addLayout(btn_layout)

        progresso_group = QGroupBox("Status de Compilacao")
        progresso_layout = QVBoxLayout()
        self.bar_geral = QProgressBar()
        self.bar_geral.setValue(0)
        progresso_layout.addWidget(self.bar_geral)
        progresso_group.setLayout(progresso_layout)
        left_panel.addWidget(progresso_group)

        right_panel = QVBoxLayout()
        log_group = QGroupBox("Logs de Execucao - Gerador PDF")
        log_layout = QVBoxLayout()
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        log_layout.addWidget(self.txt_logs)
        log_group.setLayout(log_layout)
        right_panel.addWidget(log_group)

        layout.addWidget(scrollable(left_container), 2)
        layout.addLayout(right_panel, 3)

    def showEvent(self, event):
        """Ao exibir a aba, importa dados da Aba 1 automaticamente (so se o campo estiver vazio)."""
        super().showEvent(event)
        texto_atual = self.txt_pedidos.toPlainText().strip()
        if not texto_atual:
            self.importar_da_aba1()

    def importar_da_aba1(self, forcar: bool = False) -> None:
        """Importa a lista de pedidos extraidos da Aba 1 via DataBus (Item 7).

        Args:
            forcar: Se True, sobrescreve mesmo se o usuario digitou manualmente.
        """
        if self._user_editou_manualmente and not forcar:
            return

        pedidos_extraidos = DataBus.get_pedidos_extraidos()

        if pedidos_extraidos:
            self.txt_pedidos.blockSignals(True)
            self.txt_pedidos.setPlainText("\n".join(pedidos_extraidos))
            self.txt_pedidos.blockSignals(False)
            set_status(
                self.lbl_import_status, "success",
                f"✅ {len(pedidos_extraidos)} pedido(s) importado(s) da Aba 1 via DataBus",
            )
            self._user_editou_manualmente = False
        else:
            set_status(self.lbl_import_status, "muted", "Aguardando dados da Aba 1 (📦 Extrator Inteligente)...")

    def selecionar_pasta(self) -> None:
        """Item 12: Nome padronizado em portugues."""
        caminho = QFileDialog.getExistingDirectory(self, "Selecione a pasta de saida")
        if caminho:
            self.pasta_saida = os.path.normpath(caminho)
            set_status(self.lbl_pasta, "normal", self.pasta_saida)

    def limpar_pasta(self) -> None:
        self.pasta_saida = ""
        set_status(self.lbl_pasta, "muted", "Nenhuma pasta selecionada")

    def _marcar_edicao_manual(self) -> None:
        """Marca que o usuario editou o campo manualmente."""
        if self.txt_pedidos.hasFocus():
            self._user_editou_manualmente = True

    def log(self, msg: str) -> None:
        UILogger.auto(self.txt_logs, msg)

    def verificar_requisitos(self) -> tuple:
        """Item 12: Nome padronizado em portugues.
        Verifica se a aba esta pronta para execucao automatica."""
        if not self.pasta_saida:
            return False, "Pasta de destino dos PDFs nao selecionada"
        return True, "Pronto"

    def check_prerequisites(self) -> tuple:
        """Alias para compatibilidade com fluxo_orquestrador."""
        return self.verificar_requisitos()

    def executar_automatico(self) -> None:
        """Executa a geracao de PDF automaticamente (modo cadeia)."""
        self.importar_da_aba1()
        if not self.pasta_saida:
            self.automatico_finished.emit(False, "Aba 3 pulada: pasta de destino nao selecionada")
            return
        self.iniciar_geracao(modo_automatico=True)

    def iniciar_geracao(self, modo_automatico: bool = False) -> None:
        texto = self.txt_pedidos.toPlainText()

        if not texto.strip():
            self.importar_da_aba1()
            texto = self.txt_pedidos.toPlainText()

        linhas = texto.splitlines()
        pedidos = []
        requisicoes_por_pedido: dict[str, list[str]] = {}
        vistos = set()
        for linha in linhas:
            colunas = [valor.strip() for valor in linha.split("\t")]
            pedido = colunas[0] if colunas else ""
            requisicao = colunas[1] if len(colunas) > 1 and colunas[1] else "Nao informada"
            if pedido:
                if pedido not in vistos:
                    vistos.add(pedido)
                    pedidos.append(pedido)
                    requisicoes_por_pedido[pedido] = []
                if requisicao not in requisicoes_por_pedido[pedido]:
                    requisicoes_por_pedido[pedido].append(requisicao)

        if not pedidos:
            if not modo_automatico:
                QMessageBox.warning(
                    self, "Aviso",
                    "Nenhum pedido disponivel. Execute a Aba 1 (Extrator Inteligente) primeiro!",
                )
            return

        self.btn_gerar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.bar_geral.setValue(0)

        if modo_automatico:
            get_modo_automatico().ativar("Aba 3")
        else:
            get_modo_automatico().desativar()

        self.log("🚀 Iniciando geracao de PDFs em lote...")
        self.worker = PdfGeneratorWorker(pedidos, self.pasta_saida, requisicoes_por_pedido)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.bar_geral.setValue)
        self.worker.finished_signal.connect(self.processo_finalizado)
        self.worker.start()

    def cancelar_geracao(self) -> None:
        if self.worker:
            self.worker.cancelar()
            self.log("🛑 Solicitando cancelamento do lote...")

    @pyqtSlot(str)
    def processo_finalizado(self, resumo: str) -> None:
        self.btn_gerar.setEnabled(True)
        self.btn_cancelar.setEnabled(False)

        if get_modo_automatico().ativo:
            get_modo_automatico().desativar()
            self.log(f"🎉 Aba 3 concluida: {resumo}")
            self.automatico_finished.emit(True, f"Aba 3 concluida: {resumo}")
        else:
            self.log(f"🎉 {resumo}")
            QMessageBox.information(self, "Concluido", resumo)
