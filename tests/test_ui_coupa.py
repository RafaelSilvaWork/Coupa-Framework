from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication

from modules.ui_coupa import CoupaExtractorWidget


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widget(qt_app, tmp_path):
    # Isola de coupa_profiles.json real (dados sensíveis do usuário).
    with patch("modules.config.CONFIG_FILE", tmp_path / "perfis_teste.json"):
        return CoupaExtractorWidget(parent_framework=None)


def test_load_selected_profile_lista_campos_ativos(widget):
    widget.profiles = {
        "Perfil A": {"config": {"criado_por": True, "solicitado_por": False, "emails": True, "destino": False}}
    }

    widget.load_selected_profile("Perfil A")

    assert widget.lbl_config_status.text() == "Campos ativos: Criado Por, E-mails"


def test_load_selected_profile_nenhum_campo_ativo(widget):
    widget.profiles = {"Vazio": {"config": {}}}

    widget.load_selected_profile("Vazio")

    assert widget.lbl_config_status.text() == "Campos ativos: Nenhum"


def test_load_selected_profile_ignora_nome_desconhecido(widget):
    widget.profiles = {}
    widget.lbl_config_status.setText("original")

    widget.load_selected_profile("nao existe")

    assert widget.lbl_config_status.text() == "original"


def test_open_edge_for_login_exige_perfil_selecionado(widget):
    widget.combo_profiles.clear()
    widget.txt_req_list.setPlainText("123")

    widget.open_edge_for_login()

    assert "Selecione um perfil" in widget.txt_logs.toPlainText()


def test_open_edge_for_login_exige_requisicoes(widget):
    widget.profiles = {"Perfil A": {"config": {}}}
    widget.combo_profiles.clear()
    widget.combo_profiles.addItem("Perfil A")
    widget.txt_req_list.clear()

    widget.open_edge_for_login()

    assert "Insira requisi" in widget.txt_logs.toPlainText()


def test_automation_finished_sem_resultados_limpa_tabela(widget):
    widget.tbl_results.setRowCount(3)

    widget.automation_finished([])

    assert widget.tbl_results.rowCount() == 0
    assert widget.last_results == []


def test_automation_finished_popula_tabela_e_habilita_botoes(widget, monkeypatch):
    armazenados = {}
    monkeypatch.setattr(
        "modules.ui_coupa.DataBus.store_extraction_results",
        lambda results: armazenados.setdefault("results", results),
    )
    widget.chk_aba2.setChecked(False)
    widget.chk_aba3.setChecked(False)
    widget.chk_aba4.setChecked(False)
    widget.chk_aba5.setChecked(False)
    widget.chk_aba6.setChecked(False)

    resultados = [
        {
            "requisicao": "1", "pedido": "P1", "fornecedor": "ACME",
            "criado_por": "Fulano", "localidade": "SP", "status": "Com pedido",
        },
        {"requisicao": "2", "erro": "falhou"},
    ]

    widget.automation_finished(resultados)

    assert widget.last_results == resultados
    assert armazenados["results"] == resultados
    assert widget.btn_excel.isEnabled() is True
    assert widget.btn_open_edge.isEnabled() is True
    assert widget.tbl_results.rowCount() == 2
    # A tabela ordena ao reativar setSortingEnabled(True), então a posição
    # das linhas não é garantida - busca pelo nº da requisição (coluna 0).
    status_por_requisicao = {
        widget.tbl_results.item(row, 0).text(): widget.tbl_results.item(row, 5).text()
        for row in range(widget.tbl_results.rowCount())
    }
    assert status_por_requisicao == {"1": "Com pedido", "2": "Erro"}
    assert "desabilitado" in widget.lbl_fluxo_status.text()


def test_on_progress_mostra_barra_sem_agendar_timer_abaixo_de_100(widget):
    widget._on_progress(50)

    assert widget.progress_bar.isHidden() is False
    assert getattr(widget, "_progress_hide_timer", None) is None


def test_on_progress_agenda_timer_ao_completar(widget):
    widget._on_progress(100)

    assert widget._progress_hide_timer is not None
    assert widget._progress_hide_timer.isSingleShot() is True
