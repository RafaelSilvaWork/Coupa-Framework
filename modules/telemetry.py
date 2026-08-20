"""Telemetria opcional de erros via Azure Application Insights.

Desativada por padrão (quando APPINSIGHTS_CONNECTION_STRING está vazia em
modules/config.py, que é o valor sempre commitado no repositório). Quando
ativa, qualquer logger.exception()/logger.error() já existente no projeto
passa a ser reportado automaticamente, sem precisar tocar em cada ponto de
captura de erro — o handler é anexado ao logger raiz.
"""

import logging
import sys
import threading

from modules.config import APPINSIGHTS_CONNECTION_STRING

_initialized = False

# Teto de eventos enviados por execução do app, independente do que estiver
# configurado do lado da Azure (Daily Cap). Protege contra um bug tipo loop de
# erro em série gerar volume alto de telemetria - garante o custo baixo por
# controle nosso, não só por configuração externa.
_MAX_TELEMETRY_EVENTS_PER_SESSION = 50


class _RateLimitFilter(logging.Filter):
    def __init__(self, max_records: int):
        super().__init__()
        self._max_records = max_records
        self._count = 0
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        with self._lock:
            self._count += 1
            return self._count <= self._max_records


def init_telemetry() -> None:
    """Liga o envio de erros para o Application Insights, se configurado.

    Chamar uma única vez, no início do main.py. Não faz nada (silenciosamente)
    se APPINSIGHTS_CONNECTION_STRING estiver vazia ou se o pacote opencensus
    não estiver instalado — telemetria nunca pode impedir o app de abrir.
    """
    global _initialized
    if _initialized or not APPINSIGHTS_CONNECTION_STRING:
        return

    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler
    except ImportError:
        return

    try:
        # AzureLogHandler.createLock() força self.lock = None de propósito (o envio
        # é assíncrono via worker thread própria). Isso quebrou no Python 3.14: o
        # logging padrão passou a usar "with self.lock:" em Handler.handle(), que
        # não aceita None. Restauramos um lock de verdade só para compatibilidade.
        class _FixedAzureLogHandler(AzureLogHandler):
            def createLock(self):
                self.lock = threading.RLock()

        handler = _FixedAzureLogHandler(connection_string=APPINSIGHTS_CONNECTION_STRING)
        handler.setLevel(logging.ERROR)
        handler.addFilter(_RateLimitFilter(_MAX_TELEMETRY_EVENTS_PER_SESSION))
        logging.getLogger().addHandler(handler)
        sys.excepthook = _report_unhandled_exception
        _initialized = True
    except Exception:
        pass  # best-effort: telemetria é opcional, falha aqui não deve afetar o app


def _report_unhandled_exception(exc_type, exc_value, exc_traceback):
    logging.getLogger(__name__).error(
        "Exceção não tratada", exc_info=(exc_type, exc_value, exc_traceback)
    )
    sys.__excepthook__(exc_type, exc_value, exc_traceback)
