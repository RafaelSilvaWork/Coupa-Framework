import pandas as pd
import pytest
from PyQt6.QtWidgets import QApplication

from modules.pdf_generator import PdfGeneratorWorker


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def _worker(qt_app, tmp_path, pedidos, requisicoes_por_pedido=None):
    return PdfGeneratorWorker(
        pedidos=pedidos,
        pasta_saida=str(tmp_path),
        requisicoes_por_pedido=requisicoes_por_pedido,
    )


def test_gerar_relatorio_uma_linha_por_pedido_sem_requisicoes_mapeadas(qt_app, tmp_path):
    worker = _worker(qt_app, tmp_path, ["PED-100", "PED-200"])
    resultados = {
        "PED-100": {"status": "Sucesso", "detalhe": "PDF gerado com sucesso"},
        "PED-200": {"status": "Erro", "detalhe": "Documento ainda em processamento interno"},
    }

    caminho = worker.gerar_relatorio(resultados)

    assert caminho.exists()
    assert caminho.name.startswith("Relatorio_Geracao_PDF_")
    df = pd.read_excel(caminho, sheet_name="Resultado PDFs", keep_default_na=False)
    assert list(df["Número do Pedido"]) == ["PED-100", "PED-200"]
    assert list(df["Número da Requisição"]) == ["Não informada", "Não informada"]
    assert list(df["Status"]) == ["Sucesso", "Erro"]
    assert df.loc[df["Número do Pedido"] == "PED-100", "Arquivo PDF"].iloc[0] == "PED-100.pdf"
    assert df.loc[df["Número do Pedido"] == "PED-200", "Arquivo PDF"].iloc[0] == ""


def test_gerar_relatorio_expande_uma_linha_por_requisicao_mapeada(qt_app, tmp_path):
    worker = _worker(
        qt_app, tmp_path, ["PED-100"],
        requisicoes_por_pedido={"PED-100": ["REQ-1", "REQ-2"]},
    )
    resultados = {"PED-100": {"status": "Sucesso", "detalhe": "PDF gerado com sucesso"}}

    caminho = worker.gerar_relatorio(resultados)

    df = pd.read_excel(caminho, sheet_name="Resultado PDFs", keep_default_na=False)
    assert len(df) == 2
    assert list(df["Número da Requisição"]) == ["REQ-1", "REQ-2"]
    assert (df["Número do Pedido"] == "PED-100").all()


def test_gerar_relatorio_marca_pedido_sem_resultado_como_cancelado(qt_app, tmp_path):
    worker = _worker(qt_app, tmp_path, ["PED-999"])

    caminho = worker.gerar_relatorio(resultados={})

    df = pd.read_excel(caminho, sheet_name="Resultado PDFs", keep_default_na=False)
    assert df.iloc[0]["Status"] == "Cancelado"
    assert df.iloc[0]["Detalhe"] == "Não processado"
    assert df.iloc[0]["Arquivo PDF"] == ""


def test_cancelar_marca_flag_de_cancelamento(qt_app, tmp_path):
    worker = _worker(qt_app, tmp_path, ["PED-100"])
    assert worker.cancelado is False

    worker.cancelar()

    assert worker.cancelado is True
