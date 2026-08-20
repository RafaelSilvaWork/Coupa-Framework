"""Barramento centralizado de dados entre abas (DataBus).

Substitui o acesso direto via `parent_fw.tab_coupa.last_results` que:
1. Acopla fortemente todos os widgets ao FrameworkApp (Item 5)
2. Duplica logica de extracao de dados em 3 widgets diferentes (Item 7)
3. Dificulta testes unitarios

Uso:
    # Na Aba 1 (origem):
    DataBus.store("extraction_results", results)

    # Nas abas 2, 3, 6 (destino):
    results = DataBus.get("extraction_results", [])

    # Metodos de conveniencia:
    DataBus.get_requisicoes_com_pedido()   # -> List[str]
    DataBus.get_pedidos_extraidos()         # -> List[str]
"""

import re
import threading
from datetime import datetime
from typing import Any


class DataBus:
    """Barramento de dados singleton para compartilhamento entre abas.

    Attributes:
        _store: Dicionario interno de dados compartilhados.
        _lock: Lock para acesso thread-safe a partir de QThreads (Item 14).
    """

    _store: dict[str, Any] = {}
    _lock = threading.Lock()

    @classmethod
    def store(cls, key: str, value: Any) -> None:
        """Armazena um valor no barramento."""
        with cls._lock:
            cls._store[key] = value

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Recupera um valor do barramento."""
        with cls._lock:
            return cls._store.get(key, default)

    @classmethod
    def clear(cls, key: str | None = None) -> None:
        """Limpa um item especifico ou todo o barramento."""
        with cls._lock:
            if key:
                cls._store.pop(key, None)
            else:
                cls._store.clear()

    @classmethod
    def has(cls, key: str) -> bool:
        """Verifica se uma chave existe no barramento."""
        with cls._lock:
            return key in cls._store
# amazonq-ignore-next-line

    # --- Metodos de conveniencia para dados de extracao ---

    @classmethod
    def store_extraction_results(cls, results: list[dict[str, Any]]) -> None:
        """Armazena os resultados completos da extracao da Aba 1."""
        cls.store("extraction_results", results)
        cls.store("extraction_timestamp", datetime.now())

    @classmethod
    def get_extraction_results(cls) -> list[dict[str, Any]]:
        """Retorna os resultados completos da extracao."""
        return cls.get("extraction_results", [])

    @classmethod
    def get_requisicoes_com_pedido(cls) -> list[str]:
        """Retorna lista de requisicoes que possuem pedido emitido.

        Uso: Aba 2 (Baixador de Orcamentos)
        """
        results = cls.get_extraction_results()
        requisicoes = []
        for item in results:
            if item.get("status") == "Com pedido":
                req = str(item.get("requisicao", "")).strip()
                if req:
                    requisicoes.append(req)
        return requisicoes

    @classmethod
    def get_pedidos_extraidos(cls) -> list[str]:
        """Retorna lista de pedidos extraidos no formato 'pedido\\trequisicao'.

        Uso: Aba 3 (Gerador de PDF de Pedidos)
        """
        results = cls.get_extraction_results()
        pedidos = []
        for item in results:
            if item.get("status") == "Com pedido":
                pedido_texto = item.get("pedido", "")
                req_num = item.get("requisicao", "")
                match_num = re.search(r'\d+', pedido_texto)
                if match_num:
                    pedido_num = match_num.group(0)
                    pedidos.append(f"{pedido_num}\t{req_num}")
        return pedidos

    @classmethod
    def get_resultados_validos_para_email(cls) -> list[dict[str, Any]]:
        """Retorna resultados validos para envio de e-mail.

        Uso: Aba 6 (Disparo de E-mails)
        Filtra itens com erro ou sem pedido emitido.
        """
        results = cls.get_extraction_results()
        return [
            r for r in results
            if "erro" not in r and r.get("status") != "Sem pedido emitido"
        ]

