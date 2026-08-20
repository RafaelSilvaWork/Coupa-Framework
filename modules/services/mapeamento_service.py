"""Leitura/escrita das planilhas de mapeamento nome -> e-mail usadas no
envio de e-mail (fornecedores, unidades/regionais e solicitantes).

Compartilhado pelo editor em modules/ui_mapeamento_editor.py e pela leitura
que modules/email_sender.py já fazia via pandas - a leitura aqui usa a
mesma convenção flexível de coluna (qualquer coluna com "email"/"codigo" no
nome) para continuar lendo planilhas criadas fora do app; a escrita sempre
grava cabeçalhos padronizados, então o arquivo "se organiza" depois de
passar pelo editor uma vez.

O mapeamento de fornecedores aceita uma coluna extra de código
(com_codigo=True) - modules/email_sender.py exige nome + código batendo
para linhas que têm código preenchido, evitando que fornecedores com nome
parecido peguem o e-mail um do outro.
"""
import re
from pathlib import Path

import pandas as pd

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_REGEX.match((email or "").strip()))


def _valor_texto(valor) -> str:
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def load_mapping(path, com_codigo: bool = False) -> list[tuple[str, str] | tuple[str, str, str]]:
    """Lê uma planilha de mapeamento. Retorna lista de tuplas (nome, email) -
    ou (nome, codigo, email) quando com_codigo=True. Lista vazia se o
    arquivo não existir ou não tiver uma coluna de e-mail reconhecível."""
    path = Path(path)
    if not path.exists():
        return []

    # dtype=str evita que o pandas infira colunas como número (ex: código de
    # fornecedor só com dígitos vira 123.0 em vez de "123").
    df = pd.read_excel(path, dtype=str)
    colunas = {str(coluna).lower().strip(): coluna for coluna in df.columns}
    coluna_email = next((original for lower, original in colunas.items() if "email" in lower), None)
    if coluna_email is None:
        return []

    coluna_codigo = None
    if com_codigo:
        coluna_codigo = next(
            (original for lower, original in colunas.items() if "codigo" in lower or "código" in lower),
            None,
        )

    colunas_reservadas = {coluna_email, coluna_codigo} - {None}
    coluna_nome = next((original for original in df.columns if original not in colunas_reservadas), None)
    if coluna_nome is None:
        return []

    linhas: list[tuple[str, str] | tuple[str, str, str]] = []
    for _, linha in df.iterrows():
        nome = _valor_texto(linha.get(coluna_nome, ""))
        email = _valor_texto(linha.get(coluna_email, ""))
        if com_codigo:
            codigo = _valor_texto(linha.get(coluna_codigo, "")) if coluna_codigo else ""
            if nome or codigo or email:
                linhas.append((nome, codigo, email))
        elif nome or email:
            linhas.append((nome, email))
    return linhas


def save_mapping(path, linhas, nome_label: str = "Nome", com_codigo: bool = False) -> None:
    """Grava a planilha com cabeçalhos padronizados (<nome_label>[, Código], Email)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # "Email" sem hífen - modules/email_sender.py detecta a coluna de e-mail
    # procurando a substring "email" no nome (em minúsculas); "E-mail" com
    # hífen não bate nesse teste.
    colunas = [nome_label, "Código", "Email"] if com_codigo else [nome_label, "Email"]
    df = pd.DataFrame(linhas, columns=colunas)
    df.to_excel(path, index=False, engine="openpyxl")
