import asyncio
import threading

from modules.coupa_scraper import CoupaScraper


def _make_scraper(pause_event=None, login_confirmation_event=None, cancel_event=None):
    return CoupaScraper(
        requisicoes=["123"],
        config_extrair={},
        pause_event=pause_event,
        login_confirmation_event=login_confirmation_event,
        cancel_event=cancel_event,
    )


def test_aguardar_confirmacao_login_returns_false_when_cancelled():
    # Login nunca é confirmado, mas o cancelamento já foi solicitado -
    # sem isso, essa espera ficava travada para sempre (só fechando o app).
    scraper = _make_scraper(
        login_confirmation_event=threading.Event(),
        cancel_event=threading.Event(),
    )
    scraper.cancel_event.set()

    resultado = asyncio.run(scraper.aguardar_confirmacao_login(log_callback=lambda msg: None))

    assert resultado is False


def test_aguardar_confirmacao_login_returns_true_when_confirmed():
    login_event = threading.Event()
    login_event.set()
    scraper = _make_scraper(login_confirmation_event=login_event, cancel_event=threading.Event())

    resultado = asyncio.run(scraper.aguardar_confirmacao_login(log_callback=lambda msg: None))

    assert resultado is True


def test_aguardar_retomada_returns_false_when_cancelled_while_paused():
    pause_event = threading.Event()
    pause_event.set()
    scraper = _make_scraper(pause_event=pause_event, cancel_event=threading.Event())
    scraper.cancel_event.set()

    resultado = asyncio.run(scraper.aguardar_retomada(log_callback=lambda msg: None))

    assert resultado is False


def test_aguardar_retomada_returns_true_when_not_paused():
    scraper = _make_scraper(pause_event=threading.Event(), cancel_event=threading.Event())

    resultado = asyncio.run(scraper.aguardar_retomada(log_callback=lambda msg: None))

    assert resultado is True
