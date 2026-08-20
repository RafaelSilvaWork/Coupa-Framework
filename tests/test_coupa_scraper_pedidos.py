from modules.coupa_scraper import _extrair_pedidos_emitidos


def test_extrai_um_unico_pedido():
    texto = "PO nº 12345 emitido com sucesso"
    assert _extrair_pedidos_emitidos(texto) == ["PO nº 12345"]


def test_extrai_dois_pedidos_distintos():
    texto = "PO nº 12345 emitido com sucesso. PO nº 67890 emitido com sucesso."
    assert _extrair_pedidos_emitidos(texto) == ["PO nº 12345", "PO nº 67890"]


def test_deduplica_pedido_repetido_preservando_ordem():
    texto = "PO nº 12345 emitido. PO nº 67890 emitido. PO nº 12345 emitido."
    assert _extrair_pedidos_emitidos(texto) == ["PO nº 12345", "PO nº 67890"]


def test_sem_pedido_retorna_lista_vazia():
    assert _extrair_pedidos_emitidos("Nenhum pedido foi emitido para esta requisição.") == []


def test_texto_vazio_ou_none_retorna_lista_vazia():
    assert _extrair_pedidos_emitidos("") == []
    assert _extrair_pedidos_emitidos(None) == []


def test_reconhece_variacoes_de_espacamento_e_caixa():
    texto = "po   NÚM 111 - po nº222"
    # "NÚM" não é reconhecido (só "nº"), mas "po nº222" deve ser capturado
    assert _extrair_pedidos_emitidos(texto) == ["po nº222"]
