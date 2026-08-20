"""Servico de exportacao de dados para formatos externos (Excel, CSV).

Extrai a logica de negocio de exportacao dos widgets de UI,
permitindo reuso e testes unitarios independentes do PyQt.
"""
from typing import Any

import pandas as pd


def format_results_for_excel(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converte a lista de resultados brutos da extracao em linhas formatadas para Excel.

    Args:
        results: Lista de dicionarios com dados extraidos do Coupa.

    Returns:
        Lista de dicionarios prontos para converter em DataFrame.
    """
    formatted_list = []
    for item in results:
        req = item.get("requisicao", "")
        if "erro" in item:
            formatted_list.append({
                "Requisição": req,
                "Status": "Erro",
                "Pedido": "Falhou",
                "Fornecedor (Nome)": "-",
                "Fornecedor (Número)": "-",
                "Criado Por": "-",
                "Solicitado Por": "-",
                "E-mails na Justificativa": "-",
                "Destino": "-",
            })
        elif item.get("status") == "Sem pedido emitido":
            formatted_list.append({
                "Requisição": req,
                "Status": "Sem Pedido",
                "Pedido": "Nenhum",
                "Fornecedor (Nome)": "-",
                "Fornecedor (Número)": "-",
                "Criado Por": "-",
                "Solicitado Por": "-",
                "E-mails na Justificativa": "-",
                "Destino": "-",
            })
        else:
            formatted_list.append({
                "Requisição": req,
                "Status": "Sucesso",
                "Pedido": item.get("pedido", "-"),
                "Fornecedor (Nome)": item.get("fornecedor", "-"),
                "Fornecedor (Número)": item.get("fornecedor_num", "-"),
                "Criado Por": item.get("criado_por", "-"),
                "Solicitado Por": item.get("solicitado_por", "-"),
                "E-mails na Justificativa": item.get("emails", "-"),
                "Destino": item.get("localidade", "-"),
            })
    return formatted_list


def export_to_excel_file(
    results: list[dict[str, Any]],
    file_path: str,
    sheet_name: str = "Resultados Coupa",
) -> str | None:
    """Exporta os resultados para um arquivo Excel (.xlsx).

    Args:
        results: Lista de resultados extraidos.
        file_path: Caminho completo onde salvar o arquivo.
        sheet_name: Nome da aba na planilha.

    Returns:
        Mensagem de sucesso ou None em caso de erro.
    """
    try:
        formatted_list = format_results_for_excel(results)
        if not formatted_list:
            return "Nenhum dado para exportar."

        df = pd.DataFrame(formatted_list)
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        return f"Salvo: {file_path}"
    except Exception as e:
        return f"Erro ao exportar: {str(e)}"

