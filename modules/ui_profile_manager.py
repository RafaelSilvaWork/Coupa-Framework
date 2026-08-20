import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.config import (
    MAP_FORNECEDORES,
    MAP_SOLICITANTES,
    MAP_UNIDADES,
    ProfileManager,
    get_power_automate_url,
    get_saved_coupa_instance,
    set_coupa_base_url,
    set_power_automate_url,
)
from modules.styles import scrollable, set_status
from modules.ui_mapeamento_editor import MapeamentoEditorDialog

logger = logging.getLogger(__name__)


class ProfileManagerWidget(QWidget):
    profiles_changed = pyqtSignal()
    def __init__(self, parent_framework=None):
        super().__init__()
        self.parent_fw = parent_framework
        self.profiles = {}
        self.current_profile = None
        self.init_ui()
        self.load_profiles()

    def init_ui(self):
        layout = QHBoxLayout(self)

        left_container = QWidget()
        left_panel = QVBoxLayout(left_container)

        instance_group = QGroupBox("Instância do Coupa")
        instance_layout = QVBoxLayout()
        instance_layout.addWidget(QLabel(
            "Endereço do Coupa da sua empresa (o mesmo que aparece na barra do navegador "
            "quando você acessa o Coupa):"
        ))
        instance_row = QHBoxLayout()
        self.txt_coupa_instance = QLineEdit()
        self.txt_coupa_instance.setPlaceholderText("ex.: suaempresa.coupahost.com")
        self.txt_coupa_instance.setText(get_saved_coupa_instance())
        self.btn_save_instance = QPushButton("Salvar Instância")
        self.btn_save_instance.setObjectName("btnSuccess")
        self.btn_save_instance.clicked.connect(self.save_coupa_instance)
        instance_row.addWidget(self.txt_coupa_instance, 1)
        instance_row.addWidget(self.btn_save_instance)
        instance_layout.addLayout(instance_row)
        self.lbl_instance_status = QLabel("")
        set_status(self.lbl_instance_status, "muted")
        instance_layout.addWidget(self.lbl_instance_status)
        instance_group.setLayout(instance_layout)
        left_panel.addWidget(instance_group)

        power_automate_group = QGroupBox("Power Automate (envio de e-mail)")
        power_automate_layout = QVBoxLayout()
        power_automate_layout.addWidget(QLabel(
            "URL do flow do Power Automate usado para disparar e-mails de autorização. "
            "Compartilhada por todos os perfis - configure uma vez só."
        ))
        power_automate_row = QHBoxLayout()
        self.txt_power_automate_url = QLineEdit()
        self.txt_power_automate_url.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_power_automate_url.setPlaceholderText("https://.../triggers/manual/paths/invoke?...")
        self.txt_power_automate_url.setText(get_power_automate_url())
        self.btn_toggle_power_automate_url = QPushButton("\U0001f441")
        self.btn_toggle_power_automate_url.setFixedWidth(32)
        self.btn_toggle_power_automate_url.setCheckable(True)
        self.btn_toggle_power_automate_url.setToolTip("Mostrar/Ocultar URL")
        self.btn_toggle_power_automate_url.toggled.connect(
            lambda checked: self.txt_power_automate_url.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        self.btn_save_power_automate_url = QPushButton("Salvar URL")
        self.btn_save_power_automate_url.setObjectName("btnSuccess")
        self.btn_save_power_automate_url.clicked.connect(self.save_power_automate_url)
        power_automate_row.addWidget(self.txt_power_automate_url, 1)
        power_automate_row.addWidget(self.btn_toggle_power_automate_url)
        power_automate_row.addWidget(self.btn_save_power_automate_url)
        power_automate_layout.addLayout(power_automate_row)
        self.lbl_power_automate_status = QLabel("")
        set_status(self.lbl_power_automate_status, "muted")
        power_automate_layout.addWidget(self.lbl_power_automate_status)
        power_automate_group.setLayout(power_automate_layout)
        left_panel.addWidget(power_automate_group)

        profile_group = QGroupBox("Perfis de Automação")
        profile_layout = QVBoxLayout()

        combo_layout = QHBoxLayout()
        self.combo_profiles = QComboBox()
        self.combo_profiles.currentTextChanged.connect(self.load_selected_profile)
        self.btn_new_profile = QPushButton("Novo Perfil")
        self.btn_new_profile.clicked.connect(self.start_new_profile)
        combo_layout.addWidget(QLabel("Perfil:"))
        combo_layout.addWidget(self.combo_profiles, 1)
        combo_layout.addWidget(self.btn_new_profile)

        action_layout = QHBoxLayout()
        self.btn_save_profile = QPushButton("Salvar Perfil")
        self.btn_save_profile.setObjectName("btnSuccess")
        self.btn_save_profile.clicked.connect(self.save_profile)
        self.btn_delete_profile = QPushButton("Excluir Perfil")
        self.btn_delete_profile.setObjectName("btnDanger")
        self.btn_delete_profile.clicked.connect(self.delete_profile)
        self.btn_reload_profiles = QPushButton("Recarregar")
        self.btn_reload_profiles.setObjectName("btnWarning")
        self.btn_reload_profiles.clicked.connect(self.load_profiles)
        action_layout.addWidget(self.btn_save_profile)
        action_layout.addWidget(self.btn_delete_profile)
        action_layout.addWidget(self.btn_reload_profiles)

        profile_layout.addLayout(combo_layout)
        profile_layout.addLayout(action_layout)
        profile_group.setLayout(profile_layout)
        left_panel.addWidget(profile_group)

        config_group = QGroupBox("Configuração do Perfil")
        config_layout = QFormLayout()
        self.txt_profile_name = QLineEdit()
        self.txt_profile_name.setPlaceholderText("Digite o nome do perfil")
        config_layout.addRow(QLabel("Nome do perfil:"), self.txt_profile_name)

        self.chk_criado_por = QCheckBox("Criado Por")
        self.chk_solicitado_por = QCheckBox("Solicitado Por")
        self.chk_emails = QCheckBox("E-mails")
        self.chk_destino = QCheckBox("Destino")
        self.txt_comprador_email = QLineEdit()
        self.txt_comprador_email.setPlaceholderText("comprador1@empresa.com.br; comprador2@empresa.com.br")

        config_layout.addRow(self.chk_criado_por)
        config_layout.addRow(self.chk_solicitado_por)
        config_layout.addRow(self.chk_emails)
        config_layout.addRow(self.chk_destino)
        config_layout.addRow(QLabel("E-mails do Comprador (separados por ; ou ,):"), self.txt_comprador_email)
        config_group.setLayout(config_layout)
        left_panel.addWidget(config_group)

        mapeamentos_group = QGroupBox("Planilhas de Mapeamento (Nome → E-mail)")
        mapeamentos_layout = QVBoxLayout()
        mapeamentos_layout.addWidget(QLabel(
            "Usadas no envio de e-mail para achar automaticamente o e-mail de "
            "fornecedores, unidades e solicitantes a partir do nome."
        ))
        btn_map_fornecedores = QPushButton("Editar Fornecedores")
        btn_map_fornecedores.clicked.connect(self._editar_mapa_fornecedores)
        btn_map_unidades = QPushButton("Editar Unidades/Regionais")
        btn_map_unidades.clicked.connect(self._editar_mapa_unidades)
        btn_map_solicitantes = QPushButton("Editar Solicitantes")
        btn_map_solicitantes.clicked.connect(self._editar_mapa_solicitantes)
        mapeamentos_layout.addWidget(btn_map_fornecedores)
        mapeamentos_layout.addWidget(btn_map_unidades)
        mapeamentos_layout.addWidget(btn_map_solicitantes)
        mapeamentos_group.setLayout(mapeamentos_layout)
        left_panel.addWidget(mapeamentos_group)

        template_group = QGroupBox("Modelo de E-mail (HTML)")
        template_layout = QVBoxLayout()
        self.txt_template = QTextEdit()
        self.txt_template.setPlaceholderText("Cole seu HTML aqui. Use {pedido}, {req}, {fornecedor} como variáveis.")
        template_layout.addWidget(self.txt_template)
        template_group.setLayout(template_layout)
        left_panel.addWidget(template_group, 1)

        self.lbl_status = QLabel("Nenhum perfil carregado.")
        set_status(self.lbl_status, "muted")
        left_panel.addWidget(self.lbl_status)

        layout.addWidget(scrollable(left_container), 3)

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Instruções"))
        right_panel.addWidget(QLabel("1. Selecione um perfil existente ou crie um novo."))
        right_panel.addWidget(QLabel("2. Ajuste os campos desejados e pressione Salvar."))
        right_panel.addWidget(QLabel("3. Use o perfil na Aba de Extração ou de Envio de E-mail."))
        right_panel.addStretch(1)
        layout.addLayout(right_panel, 2)

    def save_coupa_instance(self):
        valor = self.txt_coupa_instance.text().strip()
        if not valor:
            QMessageBox.warning(self, "Aviso", "Informe o endereço da sua instância do Coupa.")
            return
        try:
            normalizado = set_coupa_base_url(valor)
        except Exception as exc:
            logger.exception("Falha ao salvar instância do Coupa")
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar a instância: {exc}")
            return
        self.txt_coupa_instance.setText(normalizado)
        set_status(self.lbl_instance_status, "success", f"Instância salva: {normalizado}")

    def save_power_automate_url(self):
        valor = self.txt_power_automate_url.text().strip()
        try:
            set_power_automate_url(valor)
        except Exception as exc:
            logger.exception("Falha ao salvar URL do Power Automate")
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar a URL: {exc}")
            return
        if valor:
            set_status(self.lbl_power_automate_status, "success", "URL do Power Automate salva.")
        else:
            set_status(self.lbl_power_automate_status, "muted", "URL do Power Automate removida.")

    def load_profiles(self):
        self.profiles = ProfileManager.load_profiles() or {}
        self.current_profile = None

        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()
        self.combo_profiles.addItems(self.profiles.keys())
        self.combo_profiles.blockSignals(False)

        if self.profiles:
            self.combo_profiles.setCurrentIndex(0)
            self.load_selected_profile(self.combo_profiles.currentText())
        else:
            self.clear_form()
            self.update_status("Nenhum perfil cadastrado. Cadastre um para começar.")

    def load_selected_profile(self, name: str):
        if not name or name not in self.profiles:
            self.clear_form()
            return

        self.current_profile = name
        profile = self.profiles[name].get("config", {})
        self.txt_profile_name.setText(name)
        self.txt_profile_name.setEnabled(False)
        self.chk_criado_por.setChecked(profile.get("criado_por", True))
        self.chk_solicitado_por.setChecked(profile.get("solicitado_por", True))
        self.chk_emails.setChecked(profile.get("emails", False))
        # amazonq-ignore-next-line
        self.chk_destino.setChecked(profile.get("destino", False))
        self.txt_comprador_email.setText(profile.get("comprador_email", ""))
        self.txt_template.setPlainText(profile.get("template", ""))
        self.update_status(f"Perfil '{name}' carregado. Revise os dados antes de salvar.")

    def clear_form(self):
        self.current_profile = None
        self.txt_profile_name.setText("")
        self.txt_profile_name.setEnabled(True)
        self.chk_criado_por.setChecked(True)
        self.chk_solicitado_por.setChecked(True)
        self.chk_emails.setChecked(False)
        self.chk_destino.setChecked(False)
        self.txt_comprador_email.setText("")
        self.txt_template.setPlainText("")

    def start_new_profile(self):
        self.combo_profiles.setCurrentText("")
        self.clear_form()
        self.txt_profile_name.setEnabled(True)
        self.update_status("Criando novo perfil.")

    def save_profile(self):
        name = self.txt_profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Aviso", "Digite um nome válido para o perfil.")
            return

        config = {
            "criado_por": self.chk_criado_por.isChecked(),
            "solicitado_por": self.chk_solicitado_por.isChecked(),
            "emails": self.chk_emails.isChecked(),
            "destino": self.chk_destino.isChecked(),
            "comprador_email": self.txt_comprador_email.text().strip(),
            "template": self.txt_template.toPlainText().strip(),
        }

        comprador_email = self.txt_comprador_email.text().strip()
        if comprador_email and ";" not in comprador_email and "," not in comprador_email:
            self.update_status("Use ; ou , para separar múltiplos e-mails do comprador.")
            return

        if self.current_profile and self.current_profile != name and name in self.profiles:
            QMessageBox.warning(self, "Aviso", "Já existe um perfil com esse nome.")
            return

        if self.current_profile and self.current_profile != name:
            del self.profiles[self.current_profile]

        self.profiles[name] = {"config": config}
        try:
            ProfileManager.save_profiles(self.profiles)
        except Exception as exc:
            logger.exception("Falha ao salvar perfil %s", name)
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar o perfil: {exc}")
            return
        self.load_profiles()
        self.combo_profiles.setCurrentText(name)
        self.update_status(f"Perfil '{name}' salvo com sucesso.")
        self.profiles_changed.emit()

    def _editar_mapa_fornecedores(self):
        self._abrir_editor_mapa("Mapa de Fornecedores", MAP_FORNECEDORES, "Fornecedor", com_codigo=True)

    def _editar_mapa_unidades(self):
        self._abrir_editor_mapa("Mapa de Unidades/Regionais", MAP_UNIDADES, "Unidade")

    def _editar_mapa_solicitantes(self):
        self._abrir_editor_mapa("Mapa de Solicitantes", MAP_SOLICITANTES, "Solicitante")

    def _abrir_editor_mapa(self, titulo: str, caminho, nome_label: str, com_codigo: bool = False):
        dialog = MapeamentoEditorDialog(self, titulo, caminho, nome_label, com_codigo=com_codigo)
        if dialog.exec():
            self.update_status(f"{titulo} atualizado com sucesso.")

    def delete_profile(self):
        name = self.combo_profiles.currentText()
        if not name:
            QMessageBox.warning(self, "Aviso", "Selecione um perfil para excluir.")
            return

        resposta = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Deseja realmente excluir o perfil '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return

        if name in self.profiles:
            del self.profiles[name]
            try:
                ProfileManager.save_profiles(self.profiles)
            except Exception as exc:
                logger.exception("Falha ao excluir perfil %s", name)
                QMessageBox.critical(self, "Erro", f"Não foi possível excluir o perfil: {exc}")
                return
            self.load_profiles()
            self.update_status(f"Perfil '{name}' excluído.")
            self.profiles_changed.emit()

    def update_status(self, message: str):
        set_status(self.lbl_status, "accent", message)
