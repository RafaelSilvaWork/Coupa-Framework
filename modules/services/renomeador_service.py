import os
import re
import shutil
from pathlib import Path


class RenomeadorService:
    """Serviço de domínio para regras de renomeação de arquivos PDF."""

    @staticmethod
    def limpar_texto(texto: str) -> str:
        texto = texto.strip()
        texto = re.sub(r'[\\/:*?"<>|]', "", texto)
        texto = re.sub(r"\s+", " ", texto)
        return texto

    @staticmethod
    def gerar_nome_arquivo(id_coupa: str, fornecedor: str, unidade_entrega: str = "") -> str:
        fornecedor = RenomeadorService.limpar_texto(fornecedor)
        unidade_entrega = RenomeadorService.limpar_texto(unidade_entrega)
        if unidade_entrega:
            base = f"PO {id_coupa} - {fornecedor} - {unidade_entrega}"
        else:
            base = f"PO {id_coupa} - {fornecedor}"
        nome = f"{base}.pdf"
        max_len = 180
        if len(nome) <= max_len:
            return nome

        if unidade_entrega:
            unidade_entrega = unidade_entrega[: max_len - len(f"PO {id_coupa} - {fornecedor} - ")].rstrip()
            return f"PO {id_coupa} - {fornecedor} - {unidade_entrega}.pdf"
        fornecedor = fornecedor[: max_len - len(f"PO {id_coupa} - ")].rstrip()
        return f"PO {id_coupa} - {fornecedor}.pdf"

    @staticmethod
    def renomear_arquivo(origem: str, destino: str, backup_dir: str) -> tuple[bool, str]:
        origem_path = Path(origem)
        destino_path = Path(destino)
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        if destino_path.exists():
            return False, "Arquivo existe"

        try:
            shutil.copy2(origem_path, backup_path / origem_path.name)
            os.rename(origem_path, destino_path)
            return True, "OK"
        except OSError as exc:
            return False, str(exc)
