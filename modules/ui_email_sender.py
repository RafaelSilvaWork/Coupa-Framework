import os
import re
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QFormLayout, QFileDialog, QMessageBox, QComboBox,
    QRadioButton
)
from PyQt6.QtCore import pyqtSignal
from modules.config import ProfileManager, MAP_FORNECEDORES, MAP_SOLICITANTES, MAP_UNIDADES
from modules.email_sender import EmailWorker
from modules.fluxo_orquestrador import get_modo_automatico
from modules.logger import UILogger
from modules.styles import set_status, scrollable
import pandas as pd

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

KEYRING_SERVICE = "CoupaFrameworkEmail"
KEYRING_USERNAME_KEY = "smtp_email"
KEYRING_PASSWORD_KEY = "smtp_password"


class EmailSenderWidget(QWidget):
    automatico_finished = pyqtSignal(bool, str)

    def __init__(self, parent_framework):
        super().__init__()
        self.parent_fw = parent_framework
        self.profiles = ProfileManager.load_profiles()
        self.results: List[Dict[str, Any]] = []
        self.email_worker = None
        self.attachment_path = ""
        # Melhoria 5: ModoAutomatico é um singleton centralizado em
        # fluxo_orquestrador.get_modo_automatico() — as abas compartilham a MESMA instância.
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        left_container = QWidget()
        left_panel = QVBoxLayout(left_container)

        profile_group = QGroupBox("Perfil de Disparo")
        profile_layout = QHBoxLayout()
        self.combo_perfis = QComboBox()
        self.combo_perfis.addItem("Padr\u00e3o")
        self.combo_perfis.addItems(self.profiles.keys())

        profile_layout.addWidget(QLabel("Selecionar Perfil:"))
        profile_layout.addWidget(self.combo_perfis)
        profile_group.setLayout(profile_layout)
        left_panel.addWidget(profile_group)

        self.radio_smtp = QRadioButton("Enviar via SMTP")
        self.radio_outlook = QRadioButton("Enviar via Outlook Desktop")
        self.radio_smtp.setChecked(True)
        self.radio_smtp.toggled.connect(self.update_send_mode)

        method_group = QGroupBox("Modo de Envio")
        method_layout = QVBoxLayout()
        method_layout.addWidget(self.radio_smtp)
        method_layout.addWidget(self.radio_outlook)
        method_group.setLayout(method_layout)
        left_panel.addWidget(method_group)

        smtp_group = QGroupBox("Configura\u00e7\u00f5es SMTP de Envio")
        smtp_layout = QFormLayout()
        self.txt_smtp_host = QLineEdit("smtp.office365.com")
        self.txt_smtp_port = QLineEdit("587")
        self.txt_smtp_user = QLineEdit()
        self.txt_smtp_user.setPlaceholderText("seu-email@empresa.com.br")
        self.txt_smtp_pass = QLineEdit()
        self.txt_smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)

        # Botão de toggle para mostrar/ocultar senha
        self.btn_toggle_pass = QPushButton("\U0001f441")
        self.btn_toggle_pass.setFixedWidth(32)
        self.btn_toggle_pass.setCheckable(True)
        self.btn_toggle_pass.setToolTip("Mostrar/Ocultar senha")
        self.btn_toggle_pass.toggled.connect(
            lambda checked: self.txt_smtp_pass.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )

        # Botão para salvar credenciais no Windows Credential Manager (keyring)
        self.btn_save_creds = QPushButton("Salvar Credenciais")
        self.btn_save_creds.setObjectName("btnSuccess")
        self.btn_save_creds.setToolTip("Salva e-mail e senha no Gerenciador de Credenciais do Windows")
        self.btn_save_creds.clicked.connect(self._save_credentials_to_keyring)

        # Botão para carregar credenciais do keyring
        self.btn_load_creds = QPushButton("Carregar Credenciais")
        self.btn_load_creds.setObjectName("btnPrimary")
        self.btn_load_creds.setToolTip("Carrega e-mail e senha salvos no Gerenciador de Credenciais")
        self.btn_load_creds.clicked.connect(self._load_credentials_from_keyring)

        pass_layout = QHBoxLayout()
        pass_layout.addWidget(self.txt_smtp_pass, 1)
        pass_layout.addWidget(self.btn_toggle_pass)
        pass_widget = QWidget()
        pass_widget.setLayout(pass_layout)

        creds_layout = QHBoxLayout()
        creds_layout.addWidget(self.btn_save_creds)
        creds_layout.addWidget(self.btn_load_creds)
        creds_widget = QWidget()
        creds_widget.setLayout(creds_layout)

        smtp_layout.addRow(QLabel("Servidor SMTP:"), self.txt_smtp_host)
        smtp_layout.addRow(QLabel("Porta:"), self.txt_smtp_port)
        smtp_layout.addRow(QLabel("E-mail Remetente:"), self.txt_smtp_user)
        smtp_layout.addRow(QLabel("Senha:"), pass_widget)
        smtp_layout.addRow(QLabel(""), creds_widget)

        if not KEYRING_AVAILABLE:
            status_label = QLabel(
                "\u26a0\ufe0f keyring n\u00e3o instalado. `pip install keyring` "
                "para salvar credenciais com seguran\u00e7a."
            )
            set_status(status_label, "warning")
            smtp_layout.addRow(QLabel(""), status_label)

        smtp_group.setLayout(smtp_layout)
        left_panel.addWidget(smtp_group)
        self.smtp_group = smtp_group

        mapas_group = QGroupBox("Planilhas de Mapeamento")
        mapas_layout = QVBoxLayout()

        linha_fornecedores = QHBoxLayout()
        self.txt_map_fornecedores = QLineEdit()
        btn_map_fornecedores = QPushButton("Escolher...")
        btn_map_fornecedores.clicked.connect(self.escolher_map_fornecedores)
        btn_clear_fornecedores = QPushButton("Limpar")
        btn_clear_fornecedores.clicked.connect(self.txt_map_fornecedores.clear)
        btn_clear_fornecedores.setObjectName("btnClearField")
        linha_fornecedores.addWidget(QLabel("Mapa de Fornecedores:"))
        linha_fornecedores.addWidget(self.txt_map_fornecedores, 1)
        linha_fornecedores.addWidget(btn_map_fornecedores)
        linha_fornecedores.addWidget(btn_clear_fornecedores)
        mapas_layout.addLayout(linha_fornecedores)

        linha_unidades = QHBoxLayout()
        self.txt_map_unidades = QLineEdit()
        btn_map_unidades = QPushButton("Escolher...")
        btn_map_unidades.clicked.connect(self.escolher_map_unidades)
        btn_clear_unidades = QPushButton("Limpar")
        btn_clear_unidades.clicked.connect(self.txt_map_unidades.clear)
        btn_clear_unidades.setObjectName("btnClearField")
        linha_unidades.addWidget(QLabel("Mapa de Regionais/Unidades:"))
        linha_unidades.addWidget(self.txt_map_unidades, 1)
        linha_unidades.addWidget(btn_map_unidades)
        linha_unidades.addWidget(btn_clear_unidades)
        mapas_layout.addLayout(linha_unidades)

        linha_solicitantes = QHBoxLayout()
        self.txt_map_solicitantes = QLineEdit()
        btn_map_solicitantes = QPushButton("Escolher...")
        btn_map_solicitantes.clicked.connect(self.escolher_map_solicitantes)
        btn_clear_solicitantes = QPushButton("Limpar")
        btn_clear_solicitantes.clicked.connect(self.txt_map_solicitantes.clear)
        btn_clear_solicitantes.setObjectName("btnClearField")
        linha_solicitantes.addWidget(QLabel("Mapa de Solicitantes:"))
        linha_solicitantes.addWidget(self.txt_map_solicitantes, 1)
        linha_solicitantes.addWidget(btn_map_solicitantes)
        linha_solicitantes.addWidget(btn_clear_solicitantes)
        mapas_layout.addLayout(linha_solicitantes)

        linha_pasta_arquivos = QHBoxLayout()
        self.txt_pasta_arquivos = QLineEdit()
        btn_pasta_arquivos = QPushButton("Escolher...")
        btn_pasta_arquivos.clicked.connect(self.escolher_pasta_arquivos)
        btn_clear_pasta_arquivos = QPushButton("Limpar")
        btn_clear_pasta_arquivos.clicked.connect(self.txt_pasta_arquivos.clear)
        btn_clear_pasta_arquivos.setObjectName("btnClearField")
        linha_pasta_arquivos.addWidget(QLabel("Pasta de Arquivos dos Fornecedores:"))
        linha_pasta_arquivos.addWidget(self.txt_pasta_arquivos, 1)
        linha_pasta_arquivos.addWidget(btn_pasta_arquivos)
        linha_pasta_arquivos.addWidget(btn_clear_pasta_arquivos)
        mapas_layout.addLayout(linha_pasta_arquivos)

        mapas_group.setLayout(mapas_layout)
        left_panel.addWidget(mapas_group)

        origem_group = QGroupBox("Dados de Origem (Aba 1 \u2192 Aba 2 \u2192 aqui)")
        origem_layout = QVBoxLayout()
        self.lbl_status_dados = QLabel("Nenhum dado recebido ainda. Rode a Aba 1 e a Aba 2 primeiro.")
        self.lbl_status_dados.setWordWrap(True)
        set_status(self.lbl_status_dados, "muted")
        origem_layout.addWidget(self.lbl_status_dados)

        self.btn_carregar_manual = QPushButton("Carregar Planilha de Resultados Manualmente")
        self.btn_carregar_manual.clicked.connect(self.carregar_resultados_manualmente)
        origem_layout.addWidget(self.btn_carregar_manual)
        origem_group.setLayout(origem_layout)
        left_panel.addWidget(origem_group)

        anexo_group = QGroupBox("Anexo (opcional)")
        anexo_layout = QHBoxLayout()
        self.lbl_anexo = QLabel("Nenhum anexo selecionado")
        set_status(self.lbl_anexo, "muted")
        btn_anexo = QPushButton("Selecionar Arquivo...")
        btn_anexo.clicked.connect(self.escolher_anexo)
        btn_clear_anexo = QPushButton("Limpar")
        btn_clear_anexo.clicked.connect(self.limpar_anexo)
        btn_clear_anexo.setObjectName("btnClearField")
        anexo_layout.addWidget(self.lbl_anexo, 1)
        anexo_layout.addWidget(btn_anexo)
        anexo_layout.addWidget(btn_clear_anexo)
        anexo_group.setLayout(anexo_layout)
        left_panel.addWidget(anexo_group)

        self.btn_enviar = QPushButton("\U0001f680 Enviar E-mails Agora")
        self.btn_enviar.setObjectName("btnSend")
        self.btn_enviar.clicked.connect(self.iniciar_envio)
        left_panel.addWidget(self.btn_enviar)

        right_panel = QVBoxLayout()
        log_group = QGroupBox("Logs de Envio")
        log_layout = QVBoxLayout()
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)

        log_layout.addWidget(self.txt_logs)
        log_group.setLayout(log_layout)
        right_panel.addWidget(log_group)

        layout.addWidget(scrollable(left_container), 2)
        layout.addLayout(right_panel, 3)

        # Tenta carregar credenciais salvas ao iniciar
        self._load_credentials_from_keyring()

    def _save_credentials_to_keyring(self):
        """Salva e-mail e senha SMTP no Windows Credential Manager via keyring."""
        if not KEYRING_AVAILABLE:
            QMessageBox.warning(
                self, "keyring n\u00e3o dispon\u00edvel",
                "Instale o keyring com: pip install keyring\n"
                "Depois reinicie o aplicativo."
            )
            return

        email = self.txt_smtp_user.text().strip()
        password = self.txt_smtp_pass.text().strip()

        if not email:
            QMessageBox.warning(self, "Credenciais", "Preencha o e-mail remetente antes de salvar.")
            return
        if not password:
            QMessageBox.warning(self, "Credenciais", "Preencha a senha antes de salvar.")
            return

        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY, email)
            keyring.set_password(KEYRING_SERVICE, KEYRING_PASSWORD_KEY, password)
            self.log("\U0001f512 Credenciais SMTP salvas com seguran\u00e7a no Gerenciador de Credenciais do Windows.")
            QMessageBox.information(
                self, "Credenciais Salvas",
                "E-mail e senha SMTP foram salvos com seguran\u00e7a no "
                "Gerenciador de Credenciais do Windows (Credential Manager)."
            )
        except Exception as e:
            self.log(f"\u274c Erro ao salvar credenciais no keyring: {str(e)}")
            QMessageBox.critical(self, "Erro", f"N\u00e3o foi poss\u00edvel salvar as credenciais:\n{str(e)}")

    def _load_credentials_from_keyring(self):
        """Carrega e-mail e senha SMTP do Windows Credential Manager via keyring."""
        # amazonq-ignore-next-line
        if not KEYRING_AVAILABLE:
            return

        try:
            email = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
            password = keyring.get_password(KEYRING_SERVICE, KEYRING_PASSWORD_KEY)

            if email:
                self.txt_smtp_user.setText(email)
            if password:
                self.txt_smtp_pass.setText(password)

            if email or password:
                self.log("\U0001f513 Credenciais SMTP carregadas do Gerenciador de Credenciais do Windows.")
        except Exception as e:
            self.log(f"\u2139\ufe0f Nenhuma credencial salva encontrada no keyring: {str(e)}")

    def refresh_profiles(self):
        """Sincroniza os perfis com a aba Gerenciar Perfis."""
        self.profiles = ProfileManager.load_profiles()
        current = self.combo_perfis.currentText()
        self.combo_perfis.blockSignals(True)
        self.combo_perfis.clear()
        self.combo_perfis.addItem("Padr\u00e3o")
        self.combo_perfis.addItems(self.profiles.keys())
        if current in self.profiles:
            self.combo_perfis.setCurrentText(current)
        self.combo_perfis.blockSignals(False)

    def showEvent(self, event):
        self.refresh_profiles()
        super().showEvent(event)

    def log(self, msg: str):
        UILogger.auto(self.txt_logs, msg)

    def receber_resultados(self, results: List[Dict[str, Any]]):
        self.results = results
        validos = [r for r in results if "erro" not in r and r.get("status") != "Sem pedido emitido"]
        set_status(
            self.lbl_status_dados, "success",
            f"{len(results)} registro(s) recebido(s) da Aba 1 "
            f"({len(validos)} pronto(s) para envio de e-mail)."
        )

    def escolher_pasta_arquivos(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta raiz dos arquivos dos fornecedores")
        if pasta:
            self.txt_pasta_arquivos.setText(os.path.normpath(pasta))

    def carregar_resultados_manualmente(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar planilha de resultados", "", "Excel (*.xlsx)")
        if not file_path:
            return
        try:
            df = pd.read_excel(file_path)
            columns = {self._normalize_column_name(c): c for c in df.columns}

            lookup = {
                "requisicao": ["n\u00ba rc", "n\u00b0 rc", "nrcr", "rc", "requisicao", "requerimento"],
                "pedido": ["n\u00b0 po", "n\u00b0 do po", "numero po", "n\u00famero do po", "po", "pedido"],
                "fornecedor": ["fornecedor", "nome do fornecedor", "fornecedor (nome)", "supplier"],
                "fornecedor_num": [
                    "n\u00b0 do fornecedor", "numero do fornecedor", "fornecedor (numero)",
                    "fornecedor num", "supplier id",
                ],
                "localidade": ["unidade de entrega", "unidade", "localidade", "destino", "delivery unit"],
                "criado_por": ["criado por", "created by", "criado_por"],
                "solicitado_por": ["solicitado por", "requested by", "solicitado_por"],
                "emails": ["e-mails", "emails", "e-mail", "email", "e-mails na justificativa"],
                "comprador": ["comprador", "buyer"],
            }

            resultados = []
            for _, row in df.iterrows():
                status = str(row.get("Status", "")).strip()
                mapped = {}
                for key, variants in lookup.items():
                    column_name = self._find_column(columns, variants)
                    mapped[key] = str(row.get(column_name, "")).strip() if column_name else ""

                item = {
                    "requisicao": mapped["requisicao"],
                    "status": "Com pedido" if status == "Sucesso" else "Sem pedido emitido",
                    "pedido": mapped["pedido"],
                    "fornecedor": mapped["fornecedor"],
                    "fornecedor_num": mapped["fornecedor_num"],
                    "criado_por": mapped["criado_por"],
                    "criado_por_email": "",
                    "solicitado_por": mapped["solicitado_por"],
                    "solicitado_por_email": "",
                    "emails": mapped["emails"],
                    "localidade": mapped["localidade"],
                    "comprador": mapped["comprador"],
                }
                if status == "Erro":
                    item = {"requisicao": item["requisicao"], "erro": "Carregado de planilha"}
                resultados.append(item)
            self.receber_resultados(resultados)
            self.log(f"\U0001f4c2 Planilha carregada manualmente: {len(resultados)} registro(s).")
        except Exception as e:
            self.log(f"\u274c Erro ao carregar planilha: {str(e)}")

    def escolher_map_fornecedores(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar mapa de fornecedores", "", "Excel (*.xlsx)")
        if caminho:
            self.txt_map_fornecedores.setText(caminho)

    def escolher_map_unidades(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar mapa de regionais/unidades", "", "Excel (*.xlsx)")
        if caminho:
            self.txt_map_unidades.setText(caminho)

    def escolher_map_solicitantes(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar mapa de solicitantes", "", "Excel (*.xlsx)")
        if caminho:
            self.txt_map_solicitantes.setText(caminho)

    def escolher_anexo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar anexo")
        if caminho:
            self.attachment_path = caminho
            set_status(self.lbl_anexo, "normal", os.path.basename(caminho))

    def limpar_anexo(self):
        self.attachment_path = ""
        set_status(self.lbl_anexo, "muted", "Nenhum anexo selecionado")

    def _normalize_column_name(self, name: str) -> str:
        return re.sub(r"[^\w]", "", str(name).strip().lower())

    def _find_column(self, columns: dict[str, str], variants: list[str]) -> str | None:
        for candidate in variants:
            key = self._normalize_column_name(candidate)
            if key in columns:
                return columns[key]
        return None

    def update_send_mode(self):
        use_smtp = self.radio_smtp.isChecked()
        self.smtp_group.setVisible(use_smtp)
        self.smtp_group.setEnabled(use_smtp)

    def check_prerequisites(self) -> tuple:
        """Verifica se a aba est\u00e1 pronta para execu\u00e7\u00e3o autom\u00e1tica."""
        if not self.results:
            return False, "Nenhum dado de origem carregado"
        send_mode = "smtp" if self.radio_smtp.isChecked() else "outlook"
        if send_mode == "smtp":
            if not self.txt_smtp_user.text().strip():
                return False, "E-mail remetente SMTP n\u00e3o configurado"
            if not self.txt_smtp_pass.text().strip():
                return False, "Senha SMTP n\u00e3o configurada"
        return True, "Pronto"

    def executar_automatico(self):
        """Executa envio de e-mails automaticamente (modo cadeia)."""
        ok, msg = self.check_prerequisites()
        if not ok:
            self.automatico_finished.emit(False, f"Aba 6 pulada: {msg}")
            return
        self.iniciar_envio(modo_automatico=True)

    def iniciar_envio(self, modo_automatico=False):
        if not self.results:
            if not modo_automatico:
                QMessageBox.warning(self, "Aviso", "Nenhum dado de origem carregado.")
            return

        send_mode = "smtp" if self.radio_smtp.isChecked() else "outlook"
        sender = self.txt_smtp_user.text().strip()
        password = self.txt_smtp_pass.text().strip()
        smtp_server = self.txt_smtp_host.text().strip()

        if send_mode == "smtp" and (not sender or not password or not smtp_server):
            if not modo_automatico:
                QMessageBox.warning(self, "Aviso", "Preencha as configura\u00e7\u00f5es SMTP antes de enviar.")
            return

        perfil_nome = self.combo_perfis.currentText()
        template_html = ""
        if perfil_nome != "Padr\u00e3o" and perfil_nome in self.profiles:
            template_html = self.profiles[perfil_nome]["config"].get("template", "")

        if not modo_automatico:
            validos = [r for r in self.results if "erro" not in r and r.get("status") != "Sem pedido emitido"]
            preview = ""
            fornecedores = [r.get("fornecedor", "") for r in validos if r.get("fornecedor")]
            if fornecedores:
                lista = "\n".join(f"  • {f}" for f in fornecedores[:5])
                if len(fornecedores) > 5:
                    lista += f"\n  ... e mais {len(fornecedores) - 5} fornecedor(es)"
                preview = f"\n\nFornecedores:\n{lista}"
            mensagem_confirmacao = (
                f"Isso vai disparar e-mails para até {len(validos)} destinatário(s) usando "
                f"o perfil '{perfil_nome}' via {send_mode.upper()}.{preview}\n\nConfirma?"
            )
            confirmacao = QMessageBox.question(
                self, "Confirmar Envio",
                mensagem_confirmacao,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirmacao != QMessageBox.StandardButton.Yes:
                return

        smtp_config = {
            "sender": sender,
            "password": password,
            "smtp_server": smtp_server,
            "port": self.txt_smtp_port.text().strip(),
            "map_fornecedores": self.txt_map_fornecedores.text().strip() or str(MAP_FORNECEDORES),
            "map_unidades": self.txt_map_unidades.text().strip() or str(MAP_UNIDADES),
            "map_solicitantes": self.txt_map_solicitantes.text().strip() or str(MAP_SOLICITANTES),
            "template": template_html,
            "comprador_email": self.profiles.get(perfil_nome, {}).get("config", {}).get("comprador_email", ""),
            "pasta_arquivos": self.txt_pasta_arquivos.text().strip(),
            "mode": send_mode,
        }

        self.btn_enviar.setEnabled(False)
        self.log(f"\U0001f680 Iniciando disparo de e-mails com perfil: {perfil_nome} via {send_mode.upper()}...")

        if modo_automatico:
            get_modo_automatico().ativar("Aba 6")
        else:
            get_modo_automatico().desativar()
        self.email_worker = EmailWorker(smtp_config, self.results, self.attachment_path)
        self.email_worker.log_signal.connect(self.log)
        self.email_worker.finished_signal.connect(self.envio_finalizado)
        self.email_worker.start()

    def envio_finalizado(self, sucesso: bool, mensagem: str):
        self.btn_enviar.setEnabled(True)

        if get_modo_automatico().ativo:
            get_modo_automatico().desativar()
            self.log(f"\U0001f3c1 Aba 6 conclu\u00edda: {mensagem}")
            self.automatico_finished.emit(True, f"Aba 6 conclu\u00edda: {mensagem}")
        else:
            self.log(f"\U0001f3c1 {mensagem}")
            QMessageBox.information(self, "Disparo de E-mails", mensagem)
