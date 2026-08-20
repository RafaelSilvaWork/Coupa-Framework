from modules.logger import UILogger


class _FakeLogWidget:
    """Substitui QTextEdit nos testes - só precisa aceitar .append(str)."""

    def __init__(self):
        self.appended = []

    def append(self, html: str) -> None:
        self.appended.append(html)


def test_info_nao_falha_com_widget_none():
    UILogger.info(None, "mensagem qualquer")


def test_info_escreve_no_widget_com_rotulo_info():
    widget = _FakeLogWidget()
    UILogger.info(widget, "Processo iniciado")
    assert len(widget.appended) == 1
    assert "[INFO]" in widget.appended[0]
    assert "Processo iniciado" in widget.appended[0]


def test_warning_escreve_no_widget_com_rotulo_aviso():
    widget = _FakeLogWidget()
    UILogger.warning(widget, "Cuidado")
    assert "[AVISO]" in widget.appended[0]


def test_error_escreve_no_widget_com_rotulo_erro():
    widget = _FakeLogWidget()
    UILogger.error(widget, "Falhou")
    assert "[ERRO]" in widget.appended[0]


def test_success_escreve_no_widget_com_rotulo_ok():
    widget = _FakeLogWidget()
    UILogger.success(widget, "Deu certo")
    assert "[OK]" in widget.appended[0]


def test_plain_escreve_texto_sem_html():
    widget = _FakeLogWidget()
    UILogger.plain(widget, "Mensagem crua")
    assert widget.appended[0].endswith("Mensagem crua")
    assert "<span" not in widget.appended[0]


def test_auto_classifica_emoji_de_erro_como_erro():
    widget = _FakeLogWidget()
    UILogger.auto(widget, "❌ Falha ao processar pedido")
    assert "[ERRO]" in widget.appended[0]


def test_auto_classifica_mensagem_iniciada_em_erro_como_erro():
    widget = _FakeLogWidget()
    UILogger.auto(widget, "Erro ao conectar no servidor")
    assert "[ERRO]" in widget.appended[0]


def test_auto_nao_classifica_como_erro_quando_erro_nao_esta_no_inicio():
    """'erro' no meio da frase (sem emoji) não deve disparar o nível ERRO."""
    widget = _FakeLogWidget()
    UILogger.auto(widget, "Nenhum erro encontrado, processo concluído")
    assert "[ERRO]" not in widget.appended[0]


def test_auto_classifica_emoji_de_sucesso_como_ok():
    widget = _FakeLogWidget()
    UILogger.auto(widget, "✅ Processo concluído")
    assert "[OK]" in widget.appended[0]


def test_auto_classifica_palavra_sucesso_como_ok():
    widget = _FakeLogWidget()
    UILogger.auto(widget, "Envio finalizado com sucesso")
    assert "[OK]" in widget.appended[0]


def test_auto_classifica_aviso_como_aviso():
    widget = _FakeLogWidget()
    UILogger.auto(widget, "⚠️ Atenção: pasta vazia")
    assert "[AVISO]" in widget.appended[0]


def test_auto_classifica_mensagem_neutra_como_info():
    widget = _FakeLogWidget()
    UILogger.auto(widget, "Iniciando extração de dados...")
    assert "[INFO]" in widget.appended[0]


def test_auto_prioriza_erro_sobre_sucesso_quando_ambos_presentes():
    widget = _FakeLogWidget()
    UILogger.auto(widget, "❌ Processo concluído com falha")
    assert "[ERRO]" in widget.appended[0]


def test_auto_nao_falha_com_widget_none():
    UILogger.auto(None, "❌ Falha")
