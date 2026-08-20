import logging
import sys

import pytest

import modules.telemetry as telemetry_module
from modules.telemetry import _RateLimitFilter, init_telemetry


def test_rate_limit_filter_permite_ate_o_maximo_e_bloqueia_depois():
    filtro = _RateLimitFilter(max_records=2)
    record = logging.LogRecord("x", logging.ERROR, __file__, 1, "msg", None, None)

    assert filtro.filter(record) is True
    assert filtro.filter(record) is True
    assert filtro.filter(record) is False
    assert filtro.filter(record) is False


@pytest.fixture(autouse=True)
def _preserva_estado_global_de_telemetria():
    initialized_original = telemetry_module._initialized
    excepthook_original = sys.excepthook
    yield
    telemetry_module._initialized = initialized_original
    sys.excepthook = excepthook_original


def test_init_telemetry_nao_faz_nada_sem_connection_string(monkeypatch):
    monkeypatch.setattr(telemetry_module, "APPINSIGHTS_CONNECTION_STRING", "")
    telemetry_module._initialized = False

    init_telemetry()

    assert telemetry_module._initialized is False


def test_init_telemetry_e_idempotente_quando_ja_inicializada(monkeypatch):
    telemetry_module._initialized = True
    monkeypatch.setattr(telemetry_module, "APPINSIGHTS_CONNECTION_STRING", "InstrumentationKey=fake")

    root_logger = logging.getLogger()
    handlers_antes = list(root_logger.handlers)

    init_telemetry()

    assert root_logger.handlers == handlers_antes, "não deve registrar handler de novo"


def test_init_telemetry_tolera_pacote_opencensus_ausente(monkeypatch):
    telemetry_module._initialized = False
    monkeypatch.setattr(telemetry_module, "APPINSIGHTS_CONNECTION_STRING", "InstrumentationKey=fake")
    monkeypatch.setitem(sys.modules, "opencensus.ext.azure.log_exporter", None)

    init_telemetry()

    assert telemetry_module._initialized is False


def test_init_telemetry_registra_handler_e_excepthook_quando_configurada(monkeypatch):
    telemetry_module._initialized = False
    monkeypatch.setattr(telemetry_module, "APPINSIGHTS_CONNECTION_STRING", "InstrumentationKey=fake")

    class _FakeAzureLogHandler(logging.Handler):
        def __init__(self, connection_string=None):
            super().__init__()
            self.connection_string = connection_string

    import opencensus.ext.azure.log_exporter as log_exporter_module
    monkeypatch.setattr(log_exporter_module, "AzureLogHandler", _FakeAzureLogHandler)

    root_logger = logging.getLogger()
    handlers_antes = list(root_logger.handlers)
    try:
        init_telemetry()

        assert telemetry_module._initialized is True
        novos_handlers = [h for h in root_logger.handlers if h not in handlers_antes]
        assert len(novos_handlers) == 1
        assert isinstance(novos_handlers[0], _FakeAzureLogHandler)
        assert novos_handlers[0].level == logging.ERROR
        assert sys.excepthook is telemetry_module._report_unhandled_exception
    finally:
        for h in root_logger.handlers[:]:
            if h not in handlers_antes:
                root_logger.removeHandler(h)


def test_report_unhandled_exception_loga_e_encaminha_para_excepthook_original(monkeypatch):
    chamadas = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *args: chamadas.append(args))

    try:
        raise ValueError("falha de teste")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    telemetry_module._report_unhandled_exception(exc_type, exc_value, exc_tb)

    assert len(chamadas) == 1
    assert chamadas[0][0] is exc_type
    assert chamadas[0][1] is exc_value
