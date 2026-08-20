import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from modules.ui_profile_manager import ProfileManagerWidget


def _registra_avisos(monkeypatch, lista: list) -> None:
    """Substitui QMessageBox.warning por um espião que só anota a chamada."""
    def _fake_warning(*args, **kwargs):
        lista.append(args)
        return QMessageBox.StandardButton.Ok
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(_fake_warning))


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widget(qt_app, tmp_path, monkeypatch):
    # Isola de coupa_profiles.json real (dados do usuário) pelo resto do teste,
    # já que save_profile()/delete_profile() gravam de verdade em CONFIG_FILE.
    monkeypatch.setattr("modules.config.CONFIG_FILE", tmp_path / "perfis_teste.json")
    return ProfileManagerWidget(parent_framework=None)


def test_save_profile_exige_nome(widget, monkeypatch):
    avisos = []
    _registra_avisos(monkeypatch, avisos)
    widget.txt_profile_name.setText("   ")

    widget.save_profile()

    assert len(avisos) == 1
    assert widget.profiles == {}


def test_save_profile_exige_separador_entre_multiplos_emails_do_comprador(widget):
    widget.txt_profile_name.setText("Perfil A")
    widget.txt_comprador_email.setText("comprador@empresa.com")

    widget.save_profile()

    assert "Use ; ou , " in widget.lbl_status.text()
    assert widget.profiles == {}


def test_save_profile_cria_perfil_novo_com_sucesso(widget):
    sinais = []
    widget.profiles_changed.connect(lambda: sinais.append(True))
    widget.txt_profile_name.setText("Perfil A")
    widget.chk_criado_por.setChecked(True)
    widget.chk_emails.setChecked(True)
    widget.txt_comprador_email.setText("a@empresa.com; b@empresa.com")
    widget.txt_template.setPlainText("<p>{pedido}</p>")

    widget.save_profile()

    assert "Perfil A" in widget.profiles
    config = widget.profiles["Perfil A"]["config"]
    assert config["criado_por"] is True
    assert config["emails"] is True
    assert config["comprador_email"] == "a@empresa.com; b@empresa.com"
    assert config["template"] == "<p>{pedido}</p>"
    assert "salvo com sucesso" in widget.lbl_status.text()
    assert sinais == [True]

    # Persistiu de verdade (isolado em tmp_path) e é recarregável.
    recarregados = widget.__class__(parent_framework=None).profiles
    assert "Perfil A" in recarregados


def test_save_profile_bloqueia_renomear_para_nome_ja_existente(widget, monkeypatch):
    widget.txt_profile_name.setText("Perfil A")
    widget.save_profile()
    widget.start_new_profile()
    widget.txt_profile_name.setText("Perfil B")
    widget.save_profile()

    widget.load_selected_profile("Perfil B")
    widget.txt_profile_name.setText("Perfil A")
    avisos = []
    _registra_avisos(monkeypatch, avisos)

    widget.save_profile()

    assert len(avisos) == 1
    assert set(widget.profiles.keys()) == {"Perfil A", "Perfil B"}


def test_save_profile_renomeia_perfil_existente(widget):
    widget.txt_profile_name.setText("Nome Antigo")
    widget.save_profile()
    widget.load_selected_profile("Nome Antigo")

    widget.txt_profile_name.setEnabled(True)
    widget.txt_profile_name.setText("Nome Novo")
    widget.save_profile()

    assert "Nome Novo" in widget.profiles
    assert "Nome Antigo" not in widget.profiles


def test_load_selected_profile_preenche_formulario(widget):
    widget.profiles = {
        "Perfil A": {"config": {
            "criado_por": False, "solicitado_por": True, "emails": True, "destino": True,
            "comprador_email": "x@y.com", "template": "<b>oi</b>",
        }}
    }

    widget.load_selected_profile("Perfil A")

    assert widget.current_profile == "Perfil A"
    assert widget.txt_profile_name.text() == "Perfil A"
    assert widget.txt_profile_name.isEnabled() is False
    assert widget.chk_criado_por.isChecked() is False
    assert widget.chk_emails.isChecked() is True
    assert widget.txt_comprador_email.text() == "x@y.com"
    assert widget.txt_template.toPlainText() == "<b>oi</b>"


def test_load_selected_profile_nome_desconhecido_limpa_formulario(widget):
    widget.txt_profile_name.setText("lixo")

    widget.load_selected_profile("nao existe")

    assert widget.current_profile is None
    assert widget.txt_profile_name.text() == ""
    assert widget.txt_profile_name.isEnabled() is True


def test_clear_form_restaura_padroes(widget):
    widget.chk_criado_por.setChecked(False)
    widget.chk_emails.setChecked(True)
    widget.txt_comprador_email.setText("algo")

    widget.clear_form()

    assert widget.current_profile is None
    assert widget.chk_criado_por.isChecked() is True
    assert widget.chk_solicitado_por.isChecked() is True
    assert widget.chk_emails.isChecked() is False
    assert widget.chk_destino.isChecked() is False
    assert widget.txt_comprador_email.text() == ""


def test_delete_profile_exige_selecao(widget, monkeypatch):
    avisos = []
    _registra_avisos(monkeypatch, avisos)
    widget.combo_profiles.clear()

    widget.delete_profile()

    assert len(avisos) == 1


def test_delete_profile_confirmado_remove_perfil(widget, monkeypatch):
    widget.txt_profile_name.setText("Perfil A")
    widget.save_profile()
    sinais = []
    widget.profiles_changed.connect(lambda: sinais.append(True))
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )

    widget.delete_profile()

    assert "Perfil A" not in widget.profiles
    assert sinais == [True]


def test_delete_profile_cancelado_mantem_perfil(widget, monkeypatch):
    widget.txt_profile_name.setText("Perfil A")
    widget.save_profile()
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )

    widget.delete_profile()

    assert "Perfil A" in widget.profiles
