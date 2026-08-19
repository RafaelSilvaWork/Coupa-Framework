from modules.services.mapeamento_service import is_valid_email, load_mapping, save_mapping


def test_is_valid_email_accepts_well_formed_address():
    assert is_valid_email("fulano@empresa.com.br")


def test_is_valid_email_rejects_malformed_address():
    assert not is_valid_email("fulano@@empresa")
    assert not is_valid_email("fulano-sem-arroba")
    assert not is_valid_email("")


def test_load_mapping_returns_empty_list_when_file_missing(tmp_path):
    assert load_mapping(tmp_path / "nao_existe.xlsx") == []


def test_save_and_load_mapping_roundtrip(tmp_path):
    caminho = tmp_path / "fornecedores.xlsx"
    linhas = [("ABC Ltda", "abc@empresa.com"), ("XYZ Distribuidora", "xyz@empresa.com")]

    save_mapping(caminho, linhas, nome_label="Fornecedor")
    lidas = load_mapping(caminho)

    assert lidas == linhas


def test_load_mapping_detects_email_column_regardless_of_name(tmp_path):
    import pandas as pd

    caminho = tmp_path / "customizado.xlsx"
    df = pd.DataFrame({"Nome do Fornecedor": ["ABC Ltda"], "Endereco de Email": ["abc@empresa.com"]})
    df.to_excel(caminho, index=False, engine="openpyxl")

    assert load_mapping(caminho) == [("ABC Ltda", "abc@empresa.com")]


def test_load_mapping_returns_empty_when_no_email_column(tmp_path):
    import pandas as pd

    caminho = tmp_path / "sem_email.xlsx"
    df = pd.DataFrame({"Nome": ["ABC Ltda"], "Telefone": ["11999999999"]})
    df.to_excel(caminho, index=False, engine="openpyxl")

    assert load_mapping(caminho) == []


def test_load_mapping_skips_blank_rows(tmp_path):
    import pandas as pd

    caminho = tmp_path / "com_linha_vazia.xlsx"
    df = pd.DataFrame({"Nome": ["ABC Ltda", None], "Email": ["abc@empresa.com", None]})
    df.to_excel(caminho, index=False, engine="openpyxl")

    assert load_mapping(caminho) == [("ABC Ltda", "abc@empresa.com")]


def test_save_and_load_mapping_com_codigo_roundtrip(tmp_path):
    caminho = tmp_path / "fornecedores.xlsx"
    linhas = [("ABC Ltda", "123", "abc@empresa.com"), ("XYZ Distribuidora", "", "xyz@empresa.com")]

    save_mapping(caminho, linhas, nome_label="Fornecedor", com_codigo=True)
    lidas = load_mapping(caminho, com_codigo=True)

    assert lidas == linhas


def test_load_mapping_ignores_codigo_column_when_com_codigo_false(tmp_path):
    caminho = tmp_path / "fornecedores.xlsx"
    save_mapping(caminho, [("ABC Ltda", "123", "abc@empresa.com")], nome_label="Fornecedor", com_codigo=True)

    assert load_mapping(caminho, com_codigo=False) == [("ABC Ltda", "abc@empresa.com")]
