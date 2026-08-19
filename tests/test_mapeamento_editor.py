import pytest
from PyQt6.QtWidgets import QApplication

from modules.services.mapeamento_service import load_mapping
from modules.ui_mapeamento_editor import MapeamentoEditorDialog


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_carrega_linhas_existentes_do_arquivo(qt_app, tmp_path):
    caminho = tmp_path / "fornecedores.xlsx"
    from modules.services.mapeamento_service import save_mapping
    save_mapping(caminho, [("ABC Ltda", "abc@empresa.com")], nome_label="Fornecedor")

    dialog = MapeamentoEditorDialog(None, "Mapa de Fornecedores", caminho, "Fornecedor")

    assert dialog.tabela.rowCount() == 1
    assert dialog.tabela.item(0, 0).text() == "ABC Ltda"
    assert dialog.tabela.item(0, 1).text() == "abc@empresa.com"


def test_adicionar_e_remover_linha(qt_app, tmp_path):
    dialog = MapeamentoEditorDialog(None, "Mapa de Fornecedores", tmp_path / "novo.xlsx", "Fornecedor")
    linhas_iniciais = dialog.tabela.rowCount()

    dialog._adicionar_linha("Novo Fornecedor", "novo@empresa.com")
    assert dialog.tabela.rowCount() == linhas_iniciais + 1

    dialog.tabela.selectRow(dialog.tabela.rowCount() - 1)
    dialog._remover_selecionadas()
    assert dialog.tabela.rowCount() == linhas_iniciais


def test_validar_rejeita_email_invalido(qt_app, tmp_path):
    dialog = MapeamentoEditorDialog(None, "Mapa de Fornecedores", tmp_path / "novo.xlsx", "Fornecedor")

    erro = dialog._validar([("ABC Ltda", "nao-e-email")])

    assert erro is not None
    assert "ABC Ltda" in erro


def test_validar_rejeita_nome_duplicado(qt_app, tmp_path):
    dialog = MapeamentoEditorDialog(None, "Mapa de Fornecedores", tmp_path / "novo.xlsx", "Fornecedor")

    erro = dialog._validar([("ABC Ltda", "abc@empresa.com"), ("abc ltda", "outro@empresa.com")])

    assert erro is not None
    assert "duplicad" in erro.lower()


def test_validar_aceita_linhas_validas(qt_app, tmp_path):
    dialog = MapeamentoEditorDialog(None, "Mapa de Fornecedores", tmp_path / "novo.xlsx", "Fornecedor")

    erro = dialog._validar([("ABC Ltda", "abc@empresa.com"), ("XYZ Distribuidora", "xyz@empresa.com")])

    assert erro is None


def test_salvar_grava_arquivo_e_fecha_dialogo_quando_valido(qt_app, tmp_path):
    caminho = tmp_path / "fornecedores.xlsx"
    dialog = MapeamentoEditorDialog(None, "Mapa de Fornecedores", caminho, "Fornecedor")

    dialog._adicionar_linha("ABC Ltda", "abc@empresa.com")
    dialog._salvar()

    assert load_mapping(caminho) == [("ABC Ltda", "abc@empresa.com")]


def test_salvar_nao_fecha_dialogo_quando_invalido(qt_app, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    caminho = tmp_path / "fornecedores.xlsx"
    dialog = MapeamentoEditorDialog(None, "Mapa de Fornecedores", caminho, "Fornecedor")

    dialog._adicionar_linha("ABC Ltda", "email-invalido")
    dialog._salvar()

    assert not caminho.exists()


# ---- Modo com_codigo (editor de Fornecedores) ----

def test_com_codigo_mostra_terceira_coluna(qt_app, tmp_path):
    dialog = MapeamentoEditorDialog(
        None, "Mapa de Fornecedores", tmp_path / "novo.xlsx", "Fornecedor", com_codigo=True,
    )

    assert dialog.tabela.columnCount() == 3
    assert dialog.tabela.horizontalHeaderItem(1).text() == "Código"


def test_com_codigo_permite_nomes_iguais_com_codigos_diferentes(qt_app, tmp_path):
    dialog = MapeamentoEditorDialog(
        None, "Mapa de Fornecedores", tmp_path / "novo.xlsx", "Fornecedor", com_codigo=True,
    )

    erro = dialog._validar([
        ("ABC Ltda", "111", "abc111@empresa.com"),
        ("ABC Ltda", "222", "abc222@empresa.com"),
    ])

    assert erro is None


def test_com_codigo_rejeita_mesmo_nome_e_codigo_repetidos(qt_app, tmp_path):
    dialog = MapeamentoEditorDialog(
        None, "Mapa de Fornecedores", tmp_path / "novo.xlsx", "Fornecedor", com_codigo=True,
    )

    erro = dialog._validar([
        ("ABC Ltda", "111", "abc@empresa.com"),
        ("ABC Ltda", "111", "outro@empresa.com"),
    ])

    assert erro is not None
    assert "duplicad" in erro.lower()


def test_com_codigo_salva_e_carrega_de_volta(qt_app, tmp_path):
    caminho = tmp_path / "fornecedores.xlsx"
    dialog = MapeamentoEditorDialog(None, "Mapa de Fornecedores", caminho, "Fornecedor", com_codigo=True)

    dialog._adicionar_linha("ABC Ltda", "111", "abc@empresa.com")
    dialog._salvar()

    assert load_mapping(caminho, com_codigo=True) == [("ABC Ltda", "111", "abc@empresa.com")]
