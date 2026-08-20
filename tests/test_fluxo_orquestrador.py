from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from modules.fluxo_orquestrador import AutomaticFlowRunner, ModoAutomatico, get_modo_automatico


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture(autouse=True)
def reset_singleton():
    ModoAutomatico._instancia_unica = None
    yield
    ModoAutomatico._instancia_unica = None


def make_runner(qt_app, abas_attrs=None):
    # AutomaticFlowRunner herda QObject — precisa de QApplication ativa
    fw = QObject()
    if abas_attrs:
        for attr, widget in abas_attrs.items():
            setattr(fw, attr, widget)
    return AutomaticFlowRunner(fw)


def test_get_modo_automatico_singleton(qt_app):
    a = get_modo_automatico()
    b = get_modo_automatico()
    assert a is b


def test_modo_automatico_ativar_desativar(qt_app):
    modo = get_modo_automatico()
    assert not modo.ativo
    modo.ativar("Aba 1")
    assert modo.ativo
    assert modo.aba_origem == "Aba 1"
    modo.desativar()
    assert not modo.ativo


def test_validar_pre_requisitos_sem_widgets(qt_app):
    runner = make_runner(qt_app)
    falhas = runner.validar_pre_requisitos_abas([2, 3], tem_requisicoes=True, tem_pedidos=True)
    assert falhas == []


def test_validar_pre_requisitos_sem_dados(qt_app):
    runner = make_runner(qt_app)
    falhas = runner.validar_pre_requisitos_abas([2], tem_requisicoes=False)
    assert len(falhas) == 1
    assert "Aba 2" in falhas[0]


def test_validar_pre_requisitos_widget_falha(qt_app):
    widget = MagicMock()
    widget.check_prerequisites.return_value = (False, "pasta nao selecionada")
    runner = make_runner(qt_app, {"tab_downloader": widget})
    falhas = runner.validar_pre_requisitos_abas([2], tem_requisicoes=True)
    assert len(falhas) == 1
    assert "pasta nao selecionada" in falhas[0]


def test_start_emite_flow_finished_sem_dados(qt_app):
    runner = make_runner(qt_app)
    resultados = []
    runner.flow_finished.connect(lambda ok, msg: resultados.append((ok, msg)))
    runner.start([], [2, 3])
    assert len(resultados) > 0
