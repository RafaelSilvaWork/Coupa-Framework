from pathlib import Path

import pytest

from modules.organizador import Organizador


@pytest.fixture
def setup_dirs(tmp_path):
    propostas = tmp_path / "propostas"
    pedidos = tmp_path / "pedidos"
    destino = tmp_path / "destino"
    propostas.mkdir()
    pedidos.mkdir()
    destino.mkdir()
    return propostas, pedidos, destino


def make_xlsx(path: Path, rows: list):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["RC", "PO", "FORNECEDOR"])
    for row in rows:
        ws.append(row)
    wb.save(path)


def test_sanitizar_nome():
    org = Organizador("", "", "", "", "RC", "PO", "FORNECEDOR", lambda m: None)
    # caracteres inválidos viram espaço; espaços duplos são colapsados
    assert org.sanitizar_nome("Forn/Esc:*") == "Forn Esc"
    assert org.sanitizar_nome("  ") == "SEM_NOME"


def test_buscar_arquivo_por_codigo(tmp_path):
    (tmp_path / "123456_proposta.pdf").write_bytes(b"")
    (tmp_path / "outro.pdf").write_bytes(b"")
    org = Organizador("", "", "", "", "RC", "PO", "FORNECEDOR", lambda m: None)
    arquivos = [f for f in tmp_path.rglob("*") if f.is_file()]
    result = org.buscar_arquivo_por_codigo(arquivos, "123456")
    assert len(result) == 1
    assert result[0].name == "123456_proposta.pdf"


def test_executar_copia_arquivos(setup_dirs, tmp_path):
    propostas, pedidos, destino = setup_dirs
    planilha = tmp_path / "plan.xlsx"
    make_xlsx(planilha, [["RC001", "PO001", "Fornecedor A"]])
    (propostas / "RC001_orcamento.pdf").write_bytes(b"pdf")

    logs = []
    org = Organizador(
        propostas=str(propostas),
        pedidos="",
        destino=str(destino),
        planilha=str(planilha),
        col_rc="RC",
        col_po="PO",
        col_fornecedor="FORNECEDOR",
        logger=logs.append,
    )
    org.executar()

    pasta_forn = destino / "Fornecedor A"
    assert pasta_forn.is_dir()
    arquivos = list(pasta_forn.iterdir())
    assert len(arquivos) == 1
    assert "RC001" in arquivos[0].name
