import csv
import logging
import os
import re
from datetime import datetime

import fitz
from filelock import FileLock, Timeout
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.config import HISTORICO_RENOMEADOR
from modules.services.renomeador_service import RenomeadorService

logger = logging.getLogger(__name__)


class PDFCache:
    """Cache LRU para dados extraídos de PDFs."""
    def __init__(self, max_size: int = 50):
        self._cache: dict[str, dict] = {}
        self._max_size = max_size

    def get(self, caminho: str) -> dict | None:
        return self._cache.get(caminho)

    def set(self, caminho: str, dados: dict):
        if len(self._cache) >= self._max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[caminho] = dados

    def clear(self):
        self._cache.clear()


class AnalisadorWorker(QThread):
    """Worker para análise de PDFs em background, evitando congelamento da UI."""
    row_ready = pyqtSignal(int, dict)  # (row_index, resultado)
    finished = pyqtSignal()

    def __init__(self, pasta: str, arquivos: list, cache: PDFCache, extractor):
        super().__init__()
        self.pasta = pasta
        self.arquivos = arquivos
        self.cache = cache
        self.extractor = extractor

    def run(self):
        for idx, arquivo in enumerate(self.arquivos):
            caminho = os.path.join(self.pasta, arquivo)
            resultado = self.extractor(caminho)
            self.row_ready.emit(idx, resultado)
        self.finished.emit()


class RenomeadorWidget(QWidget):
    automatico_finished = pyqtSignal(bool, str)

    def __init__(self, parent_framework):
        super().__init__()
        self.parent_fw = parent_framework
        self.pasta = ""
        self.historico_path = HISTORICO_RENOMEADOR  # Item 16: path centralizado em config.py
        HISTORICO_RENOMEADOR.parent.mkdir(parents=True, exist_ok=True)
        self._pdf_cache = PDFCache()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        caminho_group = QHBoxLayout()
        self.txt_pasta = QLineEdit()
        btn_pasta = QPushButton("Selecionar Pasta")
        btn_pasta.clicked.connect(self.selecionar_pasta)
        btn_clear_pasta = QPushButton("Limpar")
        # amazonq-ignore-next-line
        btn_clear_pasta.setObjectName("btnClear")
        btn_clear_pasta.clicked.connect(self.txt_pasta.clear)
        caminho_group.addWidget(QLabel("Pasta de PDFs:"))
        caminho_group.addWidget(self.txt_pasta, 1)
        caminho_group.addWidget(btn_pasta)
        caminho_group.addWidget(btn_clear_pasta)
        layout.addLayout(caminho_group)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Arquivo", "ID Coupa", "Fornecedor", "Unid. Entrega", "Novo Nome", "Status"
        ])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        self.table.setColumnWidth(0, 230)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 250)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 350)
        self.table.setColumnWidth(5, 160)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        controls = QHBoxLayout()
        self.btn_analisar = QPushButton("Analisar")
        self.btn_analisar.setObjectName("btnPrimary")
        self.btn_analisar.clicked.connect(self.analisar)
        self.btn_renomear = QPushButton("Renomear")
        self.btn_renomear.setObjectName("btnSuccess")
        self.btn_renomear.clicked.connect(self.renomear)
        self.lbl_total = QLabel("PDFs encontrados: 0")
        self.combo_filtro = QComboBox()
        self.combo_filtro.addItems(["Todos", "✅ Pronto", "❌ Erro", "Aguardando"])
        self.combo_filtro.currentTextChanged.connect(self._aplicar_filtro)
        controls.addWidget(self.btn_analisar)
        controls.addWidget(self.btn_renomear)
        controls.addWidget(QLabel("Filtrar:"))
        controls.addWidget(self.combo_filtro)
        # amazonq-ignore-next-line
        controls.addStretch()
        controls.addWidget(self.lbl_total)
        layout.addLayout(controls)

    def selecionar_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta de PDFs")
        if not pasta:
            return
        self.pasta = pasta
        self.txt_pasta.setText(os.path.normpath(pasta))
        self.carregar_lista()

    def carregar_lista(self):
        self.table.setRowCount(0)
        if not self.pasta:
            self.lbl_total.setText("PDFs encontrados: 0")
            return

        arquivos = [f for f in os.listdir(self.pasta) if f.lower().endswith('.pdf')]
        for arquivo in arquivos:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(arquivo))
            self.table.setItem(row, 1, QTableWidgetItem(""))
            self.table.setItem(row, 2, QTableWidgetItem(""))
            self.table.setItem(row, 3, QTableWidgetItem(""))
            self.table.setItem(row, 4, QTableWidgetItem(""))
            self.table.setItem(row, 5, QTableWidgetItem("Aguardando analise"))

        self.lbl_total.setText(f"PDFs encontrados: {len(arquivos)}")

    def check_prerequisites(self) -> tuple:
        """Verifica se a aba esta pronta para execucao automatica."""
        if not self.pasta:
            return False, "Pasta de PDFs nao selecionada"
        arquivos = [f for f in os.listdir(self.pasta) if f.lower().endswith('.pdf')]
        if not arquivos:
            return False, "Nenhum PDF encontrado na pasta"
        return True, "Pronto"

    def executar_automatico(self):
        """Executa renomeacao automatica (modo cadeia)."""
        ok, msg = self.check_prerequisites()
        if not ok:
            self.automatico_finished.emit(False, f"Aba 4 pulada: {msg}")
            return
        self.carregar_lista()
        self.analisar()
        self.renomear(modo_automatico=True)

    def analisar(self):
        if not self.pasta:
            QMessageBox.warning(self, "Atencao", "Selecione uma pasta primeiro.")
            return

        self.btn_analisar.setEnabled(False)
        self.btn_renomear.setEnabled(False)
        self._analisador = AnalisadorWorker(self.pasta, self._arquivos_atuais(), self._pdf_cache, self.extrair_dados)
        self._analisador.row_ready.connect(self._on_row_ready)
        self._analisador.finished.connect(self._on_analise_finished)
        self._analisador.start()

    def _arquivos_atuais(self) -> list:
        return [self.table.item(r, 0).text() for r in range(self.table.rowCount()) if self.table.item(r, 0)]

    def _on_row_ready(self, row: int, resultado: dict):
        if resultado["status"] == "OK":
            novo_nome = self.gerar_nome_arquivo(
                resultado['id'], resultado['fornecedor'], resultado.get('unidade_entrega', '')
            )
            self.table.setItem(row, 1, QTableWidgetItem(resultado['id']))
            self.table.setItem(row, 2, QTableWidgetItem(resultado['fornecedor']))
            self.table.setItem(row, 3, QTableWidgetItem(resultado.get('unidade_entrega', '')))
            self.table.setItem(row, 4, QTableWidgetItem(novo_nome))
            self.table.setItem(row, 5, QTableWidgetItem("✅ Pronto"))
        else:
            self.table.setItem(row, 1, QTableWidgetItem("-"))
            self.table.setItem(row, 2, QTableWidgetItem("-"))
            self.table.setItem(row, 3, QTableWidgetItem("-"))
            self.table.setItem(row, 4, QTableWidgetItem("-"))
            self.table.setItem(row, 5, QTableWidgetItem(f"❌ {resultado.get('erro', 'Erro')}"))

    def _on_analise_finished(self):
        self.btn_analisar.setEnabled(True)
        self.btn_renomear.setEnabled(True)

    def _aplicar_filtro(self, filtro: str):
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 5)
            status = status_item.text() if status_item else ""
            if filtro == "Todos":
                self.table.setRowHidden(row, False)
            elif filtro == "✅ Pronto":
                self.table.setRowHidden(row, status != "✅ Pronto")
            elif filtro == "❌ Erro":
                self.table.setRowHidden(row, not status.startswith("❌"))
            elif filtro == "Aguardando":
                self.table.setRowHidden(row, status != "Aguardando analise")

    def renomear(self, modo_automatico=False):
        if not self.pasta:
            if not modo_automatico:
                QMessageBox.warning(self, "Atencao", "Selecione uma pasta primeiro.")
            return

        backup_folder = os.path.join(self.pasta, "Backup_Renomeamento")
        os.makedirs(backup_folder, exist_ok=True)
        renomeados = 0

        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 5)
            status = status_item.text() if status_item is not None else ""
            if status != "\u2705 Pronto":
                continue

            arquivo_item = self.table.item(row, 0)
            novo_nome_item = self.table.item(row, 4)
            if arquivo_item is None or novo_nome_item is None:
                continue

            arquivo = arquivo_item.text()
            novo_nome = novo_nome_item.text()
            origem = os.path.join(self.pasta, arquivo)
            destino = os.path.join(self.pasta, novo_nome)

            if os.path.exists(destino):
                self.table.setItem(row, 5, QTableWidgetItem("\u26a0 Arquivo ja existe"))
                self.salvar_historico(arquivo, novo_nome, "Arquivo existe")
                continue

            try:
                ok, status = RenomeadorService.renomear_arquivo(origem, destino, backup_folder)
                if ok:
                    self.table.setItem(row, 5, QTableWidgetItem("✅ Renomeado"))
                    self.salvar_historico(arquivo, novo_nome, "OK")
                    renomeados += 1
                else:
                    self.table.setItem(row, 5, QTableWidgetItem(f"⚠️ {status}"))
                    self.salvar_historico(arquivo, novo_nome, f"Erro: {status}")
            except Exception as e:
                self.table.setItem(row, 5, QTableWidgetItem(f"\u274c {str(e)}"))
                self.salvar_historico(arquivo, novo_nome, f"Erro: {str(e)}")

        if modo_automatico:
            self.automatico_finished.emit(True, f"Aba 4 concluida: {renomeados} arquivos renomeados.")
        else:
            QMessageBox.information(self, "Finalizado", f"{renomeados} arquivos renomeados.")

    def salvar_historico(self, antigo, novo, status):
        """Item 24: Salva historico com FileLock para evitar corrupcao em acesso concorrente."""
        lock_path = self.historico_path.with_suffix(self.historico_path.suffix + ".lock")
        lock = FileLock(lock_path, timeout=5)
        try:
            with lock:
                existe = self.historico_path.exists()
                with open(self.historico_path, 'a', newline='', encoding='utf-8') as f:
                    escritor = csv.writer(f)
                    if not existe:
                        escritor.writerow(["Data", "Arquivo antigo", "Arquivo novo", "Status"])
                    escritor.writerow([
                        datetime.now().strftime("%d/%m/%Y %H:%M"),
                        antigo,
                        novo,
                        status
                    ])
        except Timeout:
            logger.warning("Nao foi possivel travar o arquivo de historico: %s", lock_path)
            # Fallback: escreve sem lock para evitar perda de dados
            existe = self.historico_path.exists()
            with open(self.historico_path, 'a', newline='', encoding='utf-8') as f:
                escritor = csv.writer(f)
                if not existe:
                    escritor.writerow(["Data", "Arquivo antigo", "Arquivo novo", "Status"])
                escritor.writerow([
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    antigo,
                    novo,
                    status
                ])

    def limpar_texto(self, texto: str) -> str:
        return RenomeadorService.limpar_texto(texto)

    def gerar_nome_arquivo(self, id_coupa: str, fornecedor: str, unidade_entrega: str = "") -> str:
        return RenomeadorService.gerar_nome_arquivo(id_coupa, fornecedor, unidade_entrega)

    def normalizar_fornecedor(self, texto: str) -> str:
        texto = self.limpar_texto(texto)
        texto = re.sub(r'^(Raz[ãa]o(?: Social)?\s*[:\-]?\s*)', '', texto, flags=re.IGNORECASE)
        texto = re.split(
            r'\s*-\s*(?:Raz[ãa]o(?: Social)?|Endere[cç]o|Entrega|CNPJ|CPF|Item\s+Data|Observa[cç][õe]s|Observacoes)',
            texto,
            maxsplit=1,
            flags=re.IGNORECASE
        )[0].strip()
        return texto

    def extrair_dados(self, caminho: str) -> dict[str, str]:
        """Item 13: Extrai dados do PDF com cache LRU."""
        # Verifica cache antes de ler o PDF
        cached = self._pdf_cache.get(caminho)
        if cached is not None:
            return cached

        texto = ""
        try:
            with fitz.open(caminho) as pdf:
                for pagina in pdf:
                    texto += pagina.get_text()
        except Exception as e:
            return {"status": "ERRO", "erro": str(e)}

        id_coupa = re.search(
            r"ID\s*Coupa\s*[:\-]?\s*([0-9A-Za-z\-]+)",
            texto,
            re.IGNORECASE
        )
        fornecedor = re.search(
            r"(?:Fornecedor|Raz[ãa]o(?: Social)?)\s*[:\-]?\s*(.+?)"
            r"(?=\s{2,}|Endere[cç]o|Entrega|CNPJ|CPF|Item\s+Data|$)",
            texto,
            re.IGNORECASE | re.S
        )

        fornecedores_preciso = self.normalizar_fornecedor(
            fornecedor.group(1) if fornecedor else ""
        )

        # Extrair Razão da seção "Endereço de entrega"
        unidade_entrega = ""
        linhas = texto.split('\n')
        dentro_entrega = False

        for linha in linhas:
            linha_strip = linha.strip()
            if not linha_strip:
                continue

            if re.search(r'Endere[cç]o\s*(?:de\s+)?[Ee]ntrega', linha_strip, re.IGNORECASE):
                dentro_entrega = True
                continue

            if dentro_entrega and re.search(
                r'^(?:Item\s+Data|Observa[cç][õe]s|Observacoes|Total|Subtotal|Imposto|Frete)',
                linha_strip,
                re.IGNORECASE
            ):
                break

            if dentro_entrega:
                razao_match = re.search(
                    r'Raz[ãa]o\s*[:\-]?\s*(.+)',
                    linha_strip,
                    re.IGNORECASE
                )
                if razao_match:
                    unidade_entrega = self.limpar_texto(razao_match.group(1))
                    break

        erros = []
        if not id_coupa:
            erros.append("ID Coupa")
        if not fornecedores_preciso:
            erros.append("Fornecedor")

        if erros:
            return {
                "status": "ERRO",
                "erro": ", ".join(erros)
            }

        resultado = {
            "status": "OK",
            "id": self.limpar_texto(id_coupa.group(1) if id_coupa else ""),
            "fornecedor": fornecedores_preciso,
            "unidade_entrega": unidade_entrega,
        }

        # Salva no cache para reuso
        self._pdf_cache.set(caminho, resultado)
        return resultado
