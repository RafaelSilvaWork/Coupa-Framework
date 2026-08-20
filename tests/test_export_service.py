from modules.services.export_service import export_to_excel_file, format_results_for_excel


def test_format_results_sucesso():
    results = [{"requisicao": "100", "status": "Com pedido", "pedido": "PO 1", "fornecedor": "Forn A"}]
    rows = format_results_for_excel(results)
    assert rows[0]["Status"] == "Sucesso"
    assert rows[0]["Pedido"] == "PO 1"


def test_format_results_erro():
    results = [{"requisicao": "101", "erro": "timeout"}]
    rows = format_results_for_excel(results)
    assert rows[0]["Status"] == "Erro"


def test_format_results_sem_pedido():
    results = [{"requisicao": "102", "status": "Sem pedido emitido"}]
    rows = format_results_for_excel(results)
    assert rows[0]["Status"] == "Sem Pedido"


def test_export_to_excel_file(tmp_path):
    results = [{"requisicao": "100", "status": "Com pedido", "pedido": "PO 1"}]
    path = str(tmp_path / "out.xlsx")
    msg = export_to_excel_file(results, path)
    assert msg and msg.startswith("Salvo:")


def test_export_to_excel_file_vazio(tmp_path):
    path = str(tmp_path / "out.xlsx")
    msg = export_to_excel_file([], path)
    assert "Nenhum" in msg
