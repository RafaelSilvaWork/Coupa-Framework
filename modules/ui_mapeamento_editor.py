"""Editor genérico (em tabela) para as planilhas de mapeamento nome->e-mail
usadas no envio de e-mail: fornecedores, unidades/regionais e solicitantes.

Um único diálogo serve os três casos - só muda o título, o caminho do
arquivo e o rótulo da coluna de nome. Fornecedores usa com_codigo=True pra
ganhar uma coluna extra de Código, que modules/email_sender.py passa a
exigir junto do nome quando preenchida (evita casar fornecedores com nome
parecido).
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from modules.services.mapeamento_service import is_valid_email, load_mapping, save_mapping


class MapeamentoEditorDialog(QDialog):
    def __init__(self, parent, titulo: str, caminho, nome_label: str, com_codigo: bool = False):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(560, 480)
        self._caminho = Path(caminho)
        self._nome_label = nome_label
        self._com_codigo = com_codigo
        self._num_colunas = 3 if com_codigo else 2

        layout = QVBoxLayout(self)

        info = QLabel(f"Arquivo: {self._caminho}")
        info.setWordWrap(True)
        layout.addWidget(info)

        cabecalhos = [nome_label, "Código", "Email"] if com_codigo else [nome_label, "Email"]
        self.tabela = QTableWidget(0, self._num_colunas)
        self.tabela.setHorizontalHeaderLabels(cabecalhos)
        header = self.tabela.horizontalHeader()
        if header is not None:
            for coluna in range(self._num_colunas):
                header.setSectionResizeMode(coluna, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabela, 1)

        if com_codigo:
            dica = QLabel(
                "Código opcional: quando preenchido, o e-mail só é usado se o nome E o código "
                "baterem com o fornecedor da extração. Linhas sem código continuam batendo só pelo nome."
            )
            dica.setWordWrap(True)
            layout.addWidget(dica)

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
            linhas = load_mapping(caminho, com_codigo=self._com_codigo)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar", f"Não foi possível ler a planilha:\n{exc}")
            linhas = []
        self._preencher_tabela(linhas)

    def _preencher_tabela(self, linhas):
        self.tabela.setRowCount(0)
        for linha in linhas:
            self._adicionar_linha(*linha)

    def _adicionar_linha(self, nome: str = "", *resto: str):
        # resto = (email,) sem código, ou (codigo, email) com código -
        # aceita ambos os formatos pra _preencher_tabela funcionar com o
        # retorno de load_mapping tanto com quanto sem com_codigo.
        valores = (nome,) + resto
        valores = valores + ("",) * (self._num_colunas - len(valores))
        row = self.tabela.rowCount()
        self.tabela.insertRow(row)
        for coluna in range(self._num_colunas):
            self.tabela.setItem(row, coluna, QTableWidgetItem(valores[coluna]))

    def _remover_selecionadas(self):
        linhas = sorted({indice.row() for indice in self.tabela.selectedIndexes()}, reverse=True)
        for row in linhas:
            self.tabela.removeRow(row)

    def _linhas_atuais(self):
        linhas = []
        for row in range(self.tabela.rowCount()):
            valores = []
            for coluna in range(self._num_colunas):
                item = self.tabela.item(row, coluna)
                valores.append(item.text().strip() if item else "")
            if any(valores):
                linhas.append(tuple(valores))
        return linhas

    def _validar(self, linhas):
        """Retorna a mensagem de erro da primeira linha inválida, ou None se tudo ok."""
        vistos = set()
        for linha in linhas:
            nome, codigo, email = (linha[0], linha[1], linha[2]) if self._com_codigo else (linha[0], "", linha[1])
            if not nome:
                return "Existe uma linha sem nome preenchido."
            if not email:
                return f'"{nome}" está sem e-mail preenchido.'
            if not is_valid_email(email):
                return f'E-mail inválido para "{nome}": {email}'
            # Chave de duplicidade inclui o código: com com_codigo=True, o
            # mesmo nome pode aparecer mais de uma vez desde que o código
            # seja diferente (fornecedores homônimos com códigos distintos).
            chave = (nome.strip().lower(), codigo.strip().lower())
            if chave in vistos:
                descricao = f'"{nome}" (código "{codigo}")' if codigo else f'"{nome}"'
                return f"Linha duplicada: {descricao}."
            vistos.add(chave)
        return None

    def _salvar(self):
        linhas = self._linhas_atuais()
        erro = self._validar(linhas)
        if erro:
            QMessageBox.warning(self, "Não foi possível salvar", erro)
            return
        try:
            save_mapping(self._caminho, linhas, nome_label=self._nome_label, com_codigo=self._com_codigo)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar", f"Não foi possível salvar a planilha:\n{exc}")
            return
        self.accept()

    def _importar(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Importar planilha de mapeamento", "", "Excel (*.xlsx)")
        if not caminho:
            return
        try:
            linhas = load_mapping(caminho, com_codigo=self._com_codigo)
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
            save_mapping(caminho, self._linhas_atuais(), nome_label=self._nome_label, com_codigo=self._com_codigo)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", f"Não foi possível exportar a planilha:\n{exc}")
            return
        self.lbl_status.setText(f"Exportado para {caminho}.")
