"""Leitura/escrita das planilhas de mapeamento nome -> e-mail usadas no
envio de e-mail (fornecedores, unidades/regionais e solicitantes).

Compartilhado pelo editor em modules/ui_mapeamento_editor.py e pela leitura
que modules/email_sender.py já fazia via pandas - a leitura aqui usa a
mesma convenção flexível de coluna (qualquer coluna com "email" no nome)
para continuar lendo planilhas criadas fora do app; a escrita sempre grava
cabeçalhos padronizados, então o arquivo "se organiza" depois de passar
pelo editor uma vez.
"""
import re
from pathlib import Path
from typing import List, Tuple

import pandas as pd

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_REGEX.match((email or "").strip()))


def load_mapping(path) -> List[Tuple[str, str]]:
    """Lê uma planilha nome->e-mail. Retorna lista vazia se o arquivo não
    existir ou não tiver uma coluna de e-mail reconhecível."""
    path = Path(path)
    if not path.exists():
        return []

    df = pd.read_excel(path)
    colunas = {str(coluna).lower().strip(): coluna for coluna in df.columns}
    coluna_email = next((original for lower, original in colunas.items() if "email" in lower), None)
    if coluna_email is None:
        return []
    coluna_nome = next((original for original in df.columns if original != coluna_email), None)
    if coluna_nome is None:
        return []

    linhas = []
    for _, linha in df.iterrows():
        nome = str(linha.get(coluna_nome, "")).strip()
        email = str(linha.get(coluna_email, "")).strip()
        nome = "" if nome.lower() == "nan" else nome
        email = "" if email.lower() == "nan" else email
        if nome or email:
            linhas.append((nome, email))
    return linhas


def save_mapping(path, linhas: List[Tuple[str, str]], nome_label: str = "Nome") -> None:
    """Grava a planilha com cabeçalhos padronizados (<nome_label>, Email)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # "Email" sem hífen - modules/email_sender.py detecta a coluna de e-mail
    # procurando a substring "email" no nome (em minúsculas); "E-mail" com
    # hífen não bate nesse teste.
    df = pd.DataFrame(linhas, columns=[nome_label, "Email"])
    df.to_excel(path, index=False, engine="openpyxl")
