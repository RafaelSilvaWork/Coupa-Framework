from unittest.mock import patch

import pandas as pd
import pytest
from PyQt6.QtWidgets import QApplication, QFileDialog

from modules.ui_email_sender import EmailSenderWidget


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widget(qt_app, tmp_path, monkeypatch):
    # Isola de coupa_profiles.json real (dados sensíveis do usuário) e do
    # Windows Credential Manager de verdade.
    monkeypatch.setattr("modules.ui_email_sender.KEYRING_AVAILABLE", False)
    with patch("modules.config.CONFIG_FILE", tmp_path / "perfis_teste.json"):
        return EmailSenderWidget(parent_framework=None)


def test_normalize_column_name_remove_espacos_e_pontuacao(widget):
    assert widget._normalize_column_name(" Numero RC ") == "numerorc"
    assert widget._normalize_column_name("Fornecedor (Nome)") == "fornecedornome"


def test_find_column_localiza_pela_primeira_variante_correspondente(widget):
    columns = {"numerorc": "Numero RC Original", "fornecedor": "Fornecedor"}
    assert widget._find_column(columns, ["numero rc", "rc"]) == "Numero RC Original"
    assert widget._find_column(columns, ["inexistente"]) is None


def test_modo_envio_atual_reflete_radio_selecionado(widget):
    assert widget._modo_envio_atual() == "smtp"
    widget.radio_outlook.setChecked(True)
    assert widget._modo_envio_atual() == "outlook"
    widget.radio_power_automate.setChecked(True)
    assert widget._modo_envio_atual() == "power_automate"


def test_modo_envio_label_mapeia_nomes_amigaveis():
    assert EmailSenderWidget._modo_envio_label("smtp") == "SMTP"
    assert EmailSenderWidget._modo_envio_label("outlook") == "OUTLOOK"
    assert EmailSenderWidget._modo_envio_label("power_automate") == "POWER AUTOMATE"
    assert EmailSenderWidget._modo_envio_label("outro") == "OUTRO"


def test_update_send_mode_habilita_smtp_apenas_quando_selecionado(widget):
    widget.radio_outlook.setChecked(True)
    assert widget.smtp_group.isEnabled() is False
    assert widget.smtp_group.isHidden() is True

    widget.radio_smtp.setChecked(True)
    assert widget.smtp_group.isEnabled() is True
    assert widget.smtp_group.isHidden() is False


def test_check_prerequisites_falha_sem_resultados(widget):
    ok, msg = widget.check_prerequisites()
    assert ok is False
    assert "origem" in msg.lower()


def test_check_prerequisites_smtp_exige_usuario_e_senha(widget):
    widget.results = [{"status": "Com pedido"}]

    ok, msg = widget.check_prerequisites()
    assert ok is False
    assert "e-mail" in msg.lower()

    widget.txt_smtp_user.setText("user@empresa.com")
    ok, msg = widget.check_prerequisites()
    assert ok is False
    assert "senha" in msg.lower()

    widget.txt_smtp_pass.setText("segredo")
    ok, msg = widget.check_prerequisites()
    assert ok is True


def test_check_prerequisites_power_automate_exige_url(widget, monkeypatch):
    widget.results = [{"status": "Com pedido"}]
    widget.radio_power_automate.setChecked(True)
    monkeypatch.setattr("modules.ui_email_sender.get_power_automate_url", lambda: "")

    ok, msg = widget.check_prerequisites()

    assert ok is False
    assert "power automate" in msg.lower()


def test_receber_resultados_calcula_registros_validos(widget):
    widget.receber_resultados([
        {"status": "Com pedido"},
        {"erro": "falha"},
        {"status": "Sem pedido emitido"},
    ])

    assert len(widget.results) == 3
    assert widget.lbl_status_dados.text() == (
        "3 registro(s) recebido(s) da Aba 1 (1 pronto(s) para envio de e-mail)."
    )


def test_carregar_resultados_manualmente_mapeia_colunas_e_status(widget, tmp_path, monkeypatch):
    df = pd.DataFrame([
        {"Nº RC": "RC1", "N° PO": "PO1", "Fornecedor": "ACME", "Status": "Sucesso"},
        {"Nº RC": "RC2", "N° PO": "", "Fornecedor": "Beta", "Status": "Falhou"},
        {"Nº RC": "RC3", "N° PO": "", "Fornecedor": "", "Status": "Erro"},
    ])
    xlsx_path = tmp_path / "resultados.xlsx"
    df.to_excel(xlsx_path, index=False)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *args, **kwargs: (str(xlsx_path), ""))
    )

    widget.carregar_resultados_manualmente()

    assert len(widget.results) == 3
    assert widget.results[0]["requisicao"] == "RC1"
    assert widget.results[0]["pedido"] == "PO1"
    assert widget.results[0]["fornecedor"] == "ACME"
    assert widget.results[0]["status"] == "Com pedido"
    assert widget.results[1]["status"] == "Sem pedido emitido"
    assert widget.results[2] == {"requisicao": "RC3", "erro": "Carregado de planilha"}
