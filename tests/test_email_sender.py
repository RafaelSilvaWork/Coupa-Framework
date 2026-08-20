import base64
import email
from email.header import decode_header
from pathlib import Path

import pytest
import requests
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

    results = [
        _resultado(requisicao="1", fornecedor="ABC"),
        _resultado(requisicao="2", fornecedor="XYZ"),
        _resultado(requisicao="3", fornecedor="DEF"),
    ]
    worker = EmailWorker(_base_smtp_config(tmp_path), results)

    finished = []
    worker.finished_signal.connect(lambda ok, msg: finished.append((ok, msg)))
    worker.run()

    assert len(_FakeSMTP.instances) == 1  # uma única conexão para os 3 e-mails
    conn = _FakeSMTP.instances[0]
    assert conn.login_calls == [("remetente@example.com", "senha-secreta")]  # login uma única vez
    assert len(conn.sendmail_calls) == 3  # 3 fornecedores diferentes -> 3 e-mails, mesma conexão
    assert conn.quit_called is True
    assert finished == [(True, "Processo finalizado.")]


def test_run_agrupa_pedidos_do_mesmo_fornecedor_em_um_unico_email(qt_app, monkeypatch, tmp_path):
    """Requisições diferentes do mesmo fornecedor viram 1 e-mail só, com todos os pedidos no assunto."""
    _FakeSMTP.instances = []
    monkeypatch.setattr("modules.email_sender.smtplib.SMTP", _FakeSMTP)

    results = [
        _resultado(requisicao="1", fornecedor="ABC", pedido="100"),
        _resultado(requisicao="2", fornecedor="ABC", pedido="200"),
        _resultado(requisicao="3", fornecedor="XYZ", pedido="300"),
    ]
    worker = EmailWorker(_base_smtp_config(tmp_path), results)
    worker.run()

    conn = _FakeSMTP.instances[0]
    assert len(conn.sendmail_calls) == 2  # 2 fornecedores -> 2 e-mails

    def _assunto(msg_raw: str) -> str:
        partes = decode_header(email.message_from_string(msg_raw)["Subject"])
        return "".join(
            (texto.decode(charset or "utf-8") if isinstance(texto, bytes) else texto)
            for texto, charset in partes
        )

    def _corpo_html(msg_raw: str) -> str:
        parsed = email.message_from_string(msg_raw)
        parte_html = next(p for p in parsed.walk() if p.get_content_type() == "text/html")
        return parte_html.get_payload(decode=True).decode("utf-8")

    mensagens = [msg for (_, _, msg) in conn.sendmail_calls]
    msg_abc = next(m for m in mensagens if "100/200" in _assunto(m))
    corpo_abc = _corpo_html(msg_abc)
    assert "Requisição #1" in corpo_abc
    assert "Requisição #2" in corpo_abc


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


# ---- Busca de e-mail por nome: comparação exata, não substring ----

def test_find_email_in_df_usa_comparacao_exata(qt_app, tmp_path):
    import pandas as pd

    worker = EmailWorker(_base_smtp_config(tmp_path), [])
    worker.df_fornecedores = pd.DataFrame({
        "fornecedor": ["ABC", "ABC Distribuidora"],
        "email": ["abc@empresa.com", "abc-distribuidora@empresa.com"],
    })

    assert worker._find_supplier_email("ABC") == "abc@empresa.com"
    assert worker._find_supplier_email("ABC Distribuidora") == "abc-distribuidora@empresa.com"


def test_find_email_in_df_nao_casa_nome_curto_com_substring(qt_app, tmp_path):
    import pandas as pd

    worker = EmailWorker(_base_smtp_config(tmp_path), [])
    # Só existe "ABC Distribuidora" cadastrado - antes da correção, buscar
    # por "ABC" batia por substring e retornava esse e-mail por engano.
    worker.df_fornecedores = pd.DataFrame({
        "fornecedor": ["ABC Distribuidora"],
        "email": ["abc-distribuidora@empresa.com"],
    })

    assert worker._find_supplier_email("ABC") == ""


# ---- Modo de envio Power Automate ----

class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_run_envia_via_power_automate_com_payload_correto(qt_app, monkeypatch, tmp_path):
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(200)

    monkeypatch.setattr("modules.email_sender.requests.post", _fake_post)

    results = [_resultado(requisicao="1", fornecedor="ABC", pedido="100")]
    config = _base_smtp_config(
        tmp_path, mode="power_automate", power_automate_url="https://exemplo.com/invoke?sig=abc",
    )
    worker = EmailWorker(config, results)

    finished = []
    worker.finished_signal.connect(lambda ok, msg: finished.append((ok, msg)))
    worker.run()

    assert captured["url"] == "https://exemplo.com/invoke?sig=abc"
    assert captured["json"]["destinatario"] == "remetente@example.com"  # sem fornecedor cadastrado, cai no sender
    assert captured["json"]["assunto"] == "AUTORIZAÇÃO PC 100"
    assert isinstance(captured["json"]["cc"], list)
    assert captured["json"]["anexos"] == []
    assert finished == [(True, "Processo finalizado.")]


def test_run_falha_quando_url_do_power_automate_nao_configurada(qt_app, monkeypatch, tmp_path):
    monkeypatch.setattr("modules.email_sender.get_power_automate_url", lambda: "")

    config = _base_smtp_config(tmp_path, mode="power_automate")
    config.pop("power_automate_url", None)
    worker = EmailWorker(config, [_resultado()])

    finished = []
    worker.finished_signal.connect(lambda ok, msg: finished.append((ok, msg)))
    worker.run()

    assert len(finished) == 1
    ok, msg = finished[0]
    assert ok is False
    assert "power automate" in msg.lower() or "não configurada" in msg.lower()


def test_run_registra_falha_quando_power_automate_retorna_erro(qt_app, monkeypatch, tmp_path):
    def _fake_post(url, json=None, timeout=None):
        return _FakeResponse(500)

    monkeypatch.setattr("modules.email_sender.requests.post", _fake_post)

    logs = []
    config = _base_smtp_config(
        tmp_path, mode="power_automate", power_automate_url="https://exemplo.com/invoke?sig=abc",
    )
    worker = EmailWorker(config, [_resultado()])
    worker.log_signal.connect(logs.append)
    worker.run()

    assert any("falha" in log.lower() for log in logs)


def test_codificar_anexos_base64(qt_app, tmp_path):
    arquivo = tmp_path / "pedido.pdf"
    arquivo.write_bytes(b"conteudo do pdf de teste")

    worker = EmailWorker(_base_smtp_config(tmp_path), [])
    anexos = worker._codificar_anexos_base64([str(arquivo)])

    assert len(anexos) == 1
    assert anexos[0]["nome"] == "pedido.pdf"
    assert base64.b64decode(anexos[0]["conteudo_base64"]) == b"conteudo do pdf de teste"


# ---- Busca de e-mail do fornecedor por nome + código ----

def test_find_supplier_email_sem_coluna_codigo_bate_so_pelo_nome(qt_app, tmp_path):
    import pandas as pd

    worker = EmailWorker(_base_smtp_config(tmp_path), [])
    worker.df_fornecedores = pd.DataFrame({
        "fornecedor": ["ABC Ltda"],
        "email": ["abc@empresa.com"],
    })

    # Planilha antiga, sem coluna de código - comportamento inalterado.
    assert worker._find_supplier_email("ABC Ltda", "999") == "abc@empresa.com"


def test_find_supplier_email_com_codigo_exige_nome_e_codigo_batendo(qt_app, tmp_path):
    import pandas as pd

    worker = EmailWorker(_base_smtp_config(tmp_path), [])
    worker.df_fornecedores = pd.DataFrame({
        "fornecedor": ["ABC Ltda", "ABC Ltda"],
        "codigo": ["111", "222"],
        "email": ["abc111@empresa.com", "abc222@empresa.com"],
    })

    assert worker._find_supplier_email("ABC Ltda", "111") == "abc111@empresa.com"
    assert worker._find_supplier_email("ABC Ltda", "222") == "abc222@empresa.com"


def test_find_supplier_email_com_codigo_errado_nao_bate(qt_app, tmp_path):
    import pandas as pd

    worker = EmailWorker(_base_smtp_config(tmp_path), [])
    worker.df_fornecedores = pd.DataFrame({
        "fornecedor": ["ABC Ltda"],
        "codigo": ["111"],
        "email": ["abc@empresa.com"],
    })

    # Nome bate, mas código informado (extração) diverge do cadastrado -
    # nao deve retornar o e-mail (evita entregar pro fornecedor errado).
    assert worker._find_supplier_email("ABC Ltda", "999") == ""


def test_find_supplier_email_linha_sem_codigo_cai_no_nome(qt_app, tmp_path):
    import pandas as pd

    worker = EmailWorker(_base_smtp_config(tmp_path), [])
    # Mistura: uma linha com código, outra sem (planilha em transição).
    worker.df_fornecedores = pd.DataFrame({
        "fornecedor": ["ABC Ltda", "XYZ Distribuidora"],
        "codigo": ["111", ""],
        "email": ["abc@empresa.com", "xyz@empresa.com"],
    })

    assert worker._find_supplier_email("XYZ Distribuidora", "999") == "xyz@empresa.com"
