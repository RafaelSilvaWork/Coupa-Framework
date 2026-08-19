"""Editor genérico (em tabela) para as planilhas de mapeamento nome->e-mail
usadas no envio de e-mail: fornecedores, unidades/regionais e solicitantes.

Um único diálogo serve os três casos - só muda o título, o caminho do
arquivo e o rótulo da coluna de nome.
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QMessageBox, QFileDialog, QHeaderView
)

from modules.services.mapeamento_service import is_valid_email, load_mapping, save_mapping


class MapeamentoEditorDialog(QDialog):
    def __init__(self, parent, titulo: str, caminho, nome_label: str):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(560, 480)
        self._caminho = Path(caminho)
        self._nome_label = nome_label

        layout = QVBoxLayout(self)

        info = QLabel(f"Arquivo: {self._caminho}")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.tabela = QTableWidget(0, 2)
        self.tabela.setHorizontalHeaderLabels([nome_label, "Email"])
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabela, 1)

        botoes_linha = QHBoxLayout()
        btn_adicionar = QPushButton("+ Adicionar linha")
        btn_adicionar.clicked.connect(lambda _checked=False: self._adicionar_linha())
        btn_remover = QPushButton("Remover selecionada(s)")
        btn_remover.clicked.connect(self._remover_selecionadas)
        botoes_linha.addWidget(btn_adicionar)
        botoes_linha.addWidget(btn_remover)
        botoes_linha.addStretch(1)
        layout.addLayout(botoes_linha)

        botoes_arquivo = QHBoxLayout()
        btn_importar = QPushButton("Importar de Excel...")
        btn_importar.clicked.connect(self._importar)
        btn_exportar = QPushButton("Exportar para Excel...")
        btn_exportar.clicked.connect(self._exportar)
        botoes_arquivo.addWidget(btn_importar)
        botoes_arquivo.addWidget(btn_exportar)
        botoes_arquivo.addStretch(1)
        layout.addLayout(botoes_arquivo)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        botoes_finais = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_salvar = QPushButton("Salvar")
        btn_salvar.setObjectName("btnSuccess")
        btn_salvar.clicked.connect(self._salvar)
        botoes_finais.addStretch(1)
        botoes_finais.addWidget(btn_cancelar)
        botoes_finais.addWidget(btn_salvar)
        layout.addLayout(botoes_finais)

        self._carregar_arquivo(self._caminho)

    def _carregar_arquivo(self, caminho: Path):
        try:
            linhas = load_mapping(caminho)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar", f"Não foi possível ler a planilha:\n{exc}")
            linhas = []
        self._preencher_tabela(linhas)

    def _preencher_tabela(self, linhas):
        self.tabela.setRowCount(0)
        for nome, email in linhas:
            self._adicionar_linha(nome, email)

    def _adicionar_linha(self, nome: str = "", email: str = ""):
        row = self.tabela.rowCount()
        self.tabela.insertRow(row)
        self.tabela.setItem(row, 0, QTableWidgetItem(nome))
        self.tabela.setItem(row, 1, QTableWidgetItem(email))

    def _remover_selecionadas(self):
        linhas = sorted({indice.row() for indice in self.tabela.selectedIndexes()}, reverse=True)
        for row in linhas:
            self.tabela.removeRow(row)

    def _linhas_atuais(self):
        linhas = []
        for row in range(self.tabela.rowCount()):
            nome_item = self.tabela.item(row, 0)
            email_item = self.tabela.item(row, 1)
            nome = nome_item.text().strip() if nome_item else ""
            email = email_item.text().strip() if email_item else ""
            if nome or email:
                linhas.append((nome, email))
        return linhas

    def _validar(self, linhas):
        """Retorna a mensagem de erro da primeira linha inválida, ou None se tudo ok."""
        vistos = set()
        for nome, email in linhas:
            if not nome:
                return "Existe uma linha sem nome preenchido."
            if not email:
                return f'"{nome}" está sem e-mail preenchido.'
            if not is_valid_email(email):
                return f'E-mail inválido para "{nome}": {email}'
            chave = nome.strip().lower()
            if chave in vistos:
                return f'Nome duplicado: "{nome}".'
            vistos.add(chave)
        return None

    def _salvar(self):
        linhas = self._linhas_atuais()
        erro = self._validar(linhas)
        if erro:
            QMessageBox.warning(self, "Não foi possível salvar", erro)
            return
        try:
            save_mapping(self._caminho, linhas, nome_label=self._nome_label)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar", f"Não foi possível salvar a planilha:\n{exc}")
            return
        self.accept()

    def _importar(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Importar planilha de mapeamento", "", "Excel (*.xlsx)")
        if not caminho:
            return
        try:
            linhas = load_mapping(caminho)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao importar", f"Não foi possível ler a planilha:\n{exc}")
            return
        self._preencher_tabela(linhas)
        self.lbl_status.setText(f"{len(linhas)} linha(s) importada(s) - revise e clique em Salvar.")

    def _exportar(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar planilha de mapeamento", "", "Excel (*.xlsx)")
        if not caminho:
            return
        try:
            save_mapping(caminho, self._linhas_atuais(), nome_label=self._nome_label)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", f"Não foi possível exportar a planilha:\n{exc}")
            return
        self.lbl_status.setText(f"Exportado para {caminho}.")
