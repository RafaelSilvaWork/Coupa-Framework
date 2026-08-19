from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from modules.email_sender import EmailWorker, _extrair_emails_validos, _nome_pasta_esperado


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


class _FakeSMTP:
    """Substitui smtplib.SMTP nos testes - grava chamadas em vez de conectar de verdade."""

    instances = []

    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.starttls_called = False
        self.login_calls = []
        self.sendmail_calls = []
        self.quit_called = False
        _FakeSMTP.instances.append(self)

    def starttls(self):
        self.starttls_called = True

    def login(self, user, password):
        self.login_calls.append((user, password))

    def sendmail(self, from_addr, to_addrs, msg):
        self.sendmail_calls.append((from_addr, to_addrs, msg))

    def quit(self):
        self.quit_called = True


class _FailingSMTP:
    def __init__(self, server, port):
        raise OSError("conexão recusada")


def _base_smtp_config(tmp_path, **overrides):
    config = {
        "mode": "smtp",
        "sender": "remetente@example.com",
        "password": "senha-secreta",
        "smtp_server": "smtp.example.com",
        "port": 587,
        "map_fornecedores": str(tmp_path / "nao_existe_fornecedores.xlsx"),
        "map_unidades": str(tmp_path / "nao_existe_unidades.xlsx"),
    }
    config.update(overrides)
    return config


def _resultado(requisicao="1", fornecedor="ABC", pedido="100", **extra):
    item = {"requisicao": requisicao, "fornecedor": fornecedor, "pedido": pedido, "localidade": ""}
    item.update(extra)
    return item


# ---- _nome_pasta_esperado ----

def test_nome_pasta_esperado_normaliza_espacos_e_caixa():
    assert _nome_pasta_esperado("  ABC   Distribuidora  ") == "abc distribuidora"


def test_nome_pasta_esperado_remove_caracteres_invalidos_de_path():
    assert _nome_pasta_esperado("ABC/XYZ: Ltda") == "abc xyz ltda"


def test_nome_pasta_esperado_vazio_vira_sem_nome():
    assert _nome_pasta_esperado("   ") == "sem_nome"


# ---- Reuso da conexão SMTP no lote ----

def test_run_abre_uma_unica_conexao_smtp_para_o_lote(qt_app, monkeypatch, tmp_path):
    _FakeSMTP.instances = []
    monkeypatch.setattr("modules.email_sender.smtplib.SMTP", _FakeSMTP)

    results = [_resultado(requisicao="1"), _resultado(requisicao="2"), _resultado(requisicao="3")]
    worker = EmailWorker(_base_smtp_config(tmp_path), results)

    finished = []
    worker.finished_signal.connect(lambda ok, msg: finished.append((ok, msg)))
    worker.run()

    assert len(_FakeSMTP.instances) == 1  # uma única conexão para os 3 e-mails
    conn = _FakeSMTP.instances[0]
    assert conn.login_calls == [("remetente@example.com", "senha-secreta")]  # login uma única vez
    assert len(conn.sendmail_calls) == 3  # um sendmail por requisição, na mesma conexão
    assert conn.quit_called is True
    assert finished == [(True, "Processo finalizado.")]


def test_run_reporta_falha_e_nao_envia_quando_conexao_smtp_falha(qt_app, monkeypatch, tmp_path):
    monkeypatch.setattr("modules.email_sender.smtplib.SMTP", _FailingSMTP)

    worker = EmailWorker(_base_smtp_config(tmp_path), [_resultado()])

    finished = []
    worker.finished_signal.connect(lambda ok, msg: finished.append((ok, msg)))
    worker.run()

    assert len(finished) == 1
    ok, msg = finished[0]
    assert ok is False
    assert "smtp" in msg.lower()


# ---- Correspondência exata da pasta de anexos ----

def test_anexos_usam_correspondencia_exata_de_pasta_nao_substring(qt_app, monkeypatch, tmp_path):
    _FakeSMTP.instances = []
    monkeypatch.setattr("modules.email_sender.smtplib.SMTP", _FakeSMTP)

    pasta_base = tmp_path / "anexos"
    pasta_abc = pasta_base / "ABC"
    pasta_abc.mkdir(parents=True)
    (pasta_abc / "arquivo_correto.pdf").write_bytes(b"conteudo")

    # Pasta de outro fornecedor cujo nome apenas CONTÉM "ABC" como substring -
    # antes da correção, isso também era anexado por engano.
    pasta_abc_distribuidora = pasta_base / "ABC Distribuidora"
    pasta_abc_distribuidora.mkdir()
    (pasta_abc_distribuidora / "arquivo_errado.pdf").write_bytes(b"conteudo")

    captured = {}

    def _fake_send_via_smtp(self, smtp_connection, sender, destinatario_fornecedor,
                             copias_cc, subject, html_body, attachments, req):
        captured["attachments"] = list(attachments)

    monkeypatch.setattr(EmailWorker, "_send_via_smtp", _fake_send_via_smtp)

    results = [_resultado(fornecedor="ABC")]
    worker = EmailWorker(_base_smtp_config(tmp_path, pasta_arquivos=str(pasta_base)), results)
    worker.run()

    anexados = sorted(Path(p).name for p in captured["attachments"])
    assert anexados == ["arquivo_correto.pdf"]


# ---- E-mails da justificativa (item["emails"]) entrando no CC ----

def test_extrair_emails_validos_ignora_placeholder_nao_solicitado():
    assert _extrair_emails_validos("[Não Solicitado]") == []


def test_extrair_emails_validos_ignora_placeholder_nenhum_encontrado():
    assert _extrair_emails_validos("Nenhum e-mail encontrado") == []


def test_extrair_emails_validos_extrai_lista_separada_por_virgula():
    assert _extrair_emails_validos("fulano@empresa.com, cicla@empresa.com") == [
        "fulano@empresa.com",
        "cicla@empresa.com",
    ]


def test_run_adiciona_emails_da_justificativa_no_cc(qt_app, monkeypatch, tmp_path):
    _FakeSMTP.instances = []
    monkeypatch.setattr("modules.email_sender.smtplib.SMTP", _FakeSMTP)

    captured = {}

    def _fake_send_via_smtp(self, smtp_connection, sender, destinatario_fornecedor,
                             copias_cc, subject, html_body, attachments, req):
        captured["copias_cc"] = list(copias_cc)

    monkeypatch.setattr(EmailWorker, "_send_via_smtp", _fake_send_via_smtp)

    results = [_resultado(emails="fulano@empresa.com, cicla@empresa.com")]
    worker = EmailWorker(_base_smtp_config(tmp_path), results)
    worker.run()

    assert "fulano@empresa.com" in captured["copias_cc"]
    assert "cicla@empresa.com" in captured["copias_cc"]


def test_run_nao_adiciona_cc_quando_extracao_de_emails_esta_desligada(qt_app, monkeypatch, tmp_path):
    # Perfil de comprador que nao marcou "E-mails" na extracao (Aba 1) -
    # coupa_scraper.py preenche esse placeholder em vez de uma lista real.
    _FakeSMTP.instances = []
    monkeypatch.setattr("modules.email_sender.smtplib.SMTP", _FakeSMTP)

    captured = {}

    def _fake_send_via_smtp(self, smtp_connection, sender, destinatario_fornecedor,
                             copias_cc, subject, html_body, attachments, req):
        captured["copias_cc"] = list(copias_cc)

    monkeypatch.setattr(EmailWorker, "_send_via_smtp", _fake_send_via_smtp)

    results = [_resultado(emails="[Não Solicitado]")]
    worker = EmailWorker(_base_smtp_config(tmp_path), results)
    worker.run()

    assert captured["copias_cc"] == []
