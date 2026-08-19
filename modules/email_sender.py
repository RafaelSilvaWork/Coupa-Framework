import os
import re
import threading
import time
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from modules.config import MAP_FORNECEDORES, MAP_UNIDADES

_CARACTERES_INVALIDOS_PASTA = re.compile(r'[\\/:*?"<>|\n\r\t]')


def _nome_pasta_esperado(fornecedor_nome: str) -> str:
    """Normaliza o nome do fornecedor do mesmo jeito que
    Organizador.sanitizar_nome (modules/organizador.py) normaliza ao criar a
    pasta de anexos, para comparar por igualdade exata em vez de substring.

    Sem isso, `"ABC" in pasta.lower()` também casava com pastas de
    fornecedores diferentes cujo nome só contém "ABC" como parte do nome
    (ex: "ABC Distribuidora" e "ABC Ltda"), anexando arquivos da empresa
    errada no e-mail.
    """
    nome_limpo = _CARACTERES_INVALIDOS_PASTA.sub(" ", fornecedor_nome).strip()
    nome_limpo = re.sub(r"\s+", " ", nome_limpo).strip()
    return (nome_limpo if nome_limpo else "SEM_NOME").lower()


class SpreadsheetCache:
    """Item 14: Cache LRU para planilhas de mapeamento com verificação de timestamp.

    Evita recarregar as mesmas planilhas a cada execução do EmailWorker.
    Se o arquivo não foi modificado desde o último carregamento, retorna os dados em cache.
    Thread-safe via threading.Lock (Item 14).
    """
    _instance = None
    _cache: Dict[str, Tuple[float, Any]] = {}
    _max_size = 10
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get(self, caminho: str) -> Optional[Any]:
        """Retorna dados do cache se o arquivo não foi modificado."""
        with self._lock:
            if caminho not in self._cache:
                return None
            timestamp, data = self._cache[caminho]
        try:
            mtime = os.path.getmtime(caminho)
            if mtime <= timestamp:
                return data
        except OSError:
            pass
        return None

    def set(self, caminho: str, data: Any) -> None:
        """Armazena dados em cache com timestamp atual."""
        try:
            timestamp = os.path.getmtime(caminho)
        except OSError:
            timestamp = time.time()

        with self._lock:
            if len(self._cache) >= self._max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[caminho] = (timestamp, data)

    def invalidate(self, caminho: Optional[str] = None) -> None:
        """Invalida cache de um arquivo específico ou de todos."""
        with self._lock:
            if caminho:
                self._cache.pop(caminho, None)
            else:
                self._cache.clear()

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

try:
    import win32com.client
except ImportError:
    win32com = None


class EmailWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, smtp_config: Dict[str, Any], results: List[Dict[str, Any]], attachment_path: str = ""):
        super().__init__()
        self.smtp_config = smtp_config
        self.results = results
        self.attachment_path = attachment_path
        self.df_fornecedores = None
        self.df_unidades = None
        self.df_solicitantes = None
        self.load_mapping_spreadsheets()

    def load_mapping_spreadsheets(self):
        """Item 14: Carrega planilhas de mapeamento com SpreadsheetCache LRU.

        Evita recarregar planilhas inalteradas entre execuções do EmailWorker.
        O cache verifica o timestamp do arquivo para decidir se recarrega.
        """
        cache = SpreadsheetCache()
        caminho_fornecedores = self.smtp_config.get("map_fornecedores", MAP_FORNECEDORES)
        caminho_unidades = self.smtp_config.get("map_unidades", MAP_UNIDADES)
        caminho_solicitantes = self.smtp_config.get("map_solicitantes", "")

        # Fornecedores
        if os.path.exists(caminho_fornecedores):
            cached = cache.get(str(caminho_fornecedores))
            if cached is not None:
                self.df_fornecedores = cached
                self.log_signal.emit(f"📦 Cache: {caminho_fornecedores} carregado do cache")
            else:
                try:
                    self.df_fornecedores = pd.read_excel(caminho_fornecedores)
                    self.df_fornecedores.columns = [c.lower().strip() for c in self.df_fornecedores.columns]
                    cache.set(str(caminho_fornecedores), self.df_fornecedores)
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Erro ao carregar {caminho_fornecedores}: {str(e)}")
        else:
            self.log_signal.emit(f"⚠️ Mapa de fornecedores não encontrado em: {caminho_fornecedores}")

        # Solicitantes
        if caminho_solicitantes and os.path.exists(caminho_solicitantes):
            cached = cache.get(str(caminho_solicitantes))
            if cached is not None:
                self.df_solicitantes = cached
                self.log_signal.emit(f"📦 Cache: {caminho_solicitantes} carregado do cache")
            else:
                try:
                    self.df_solicitantes = pd.read_excel(caminho_solicitantes)
                    self.df_solicitantes.columns = [c.lower().strip() for c in self.df_solicitantes.columns]
                    cache.set(str(caminho_solicitantes), self.df_solicitantes)
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Erro ao carregar {caminho_solicitantes}: {str(e)}")
        elif caminho_solicitantes:
            self.log_signal.emit(f"⚠️ Mapa de solicitantes não encontrado em: {caminho_solicitantes}")
# amazonq-ignore-next-line

        # Unidades
        if os.path.exists(caminho_unidades):
            cached = cache.get(str(caminho_unidades))
            if cached is not None:
                self.df_unidades = cached
                self.log_signal.emit(f"📦 Cache: {caminho_unidades} carregado do cache")
            else:
                try:
                    self.df_unidades = pd.read_excel(caminho_unidades)
                    self.df_unidades.columns = [c.lower().strip() for c in self.df_unidades.columns]
                    cache.set(str(caminho_unidades), self.df_unidades)
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Erro ao carregar {caminho_unidades}: {str(e)}")
        else:
            self.log_signal.emit(f"⚠️ Mapa de unidades/regionais não encontrado em: {caminho_unidades}")

    def _find_email_in_df(self, df, search_term: str) -> str:
        if not search_term.strip() or df is None:
            return ""
        term_norm = search_term.strip().lower()
        email_columns = [c for c in df.columns if "email" in c]
        if not email_columns:
            return ""
        candidate_columns = [c for c in df.columns if c not in email_columns]
        # Item 12: vetorizado com pandas em vez de iterrows()
        for col in candidate_columns:
            col_lower = df[col].astype(str).str.strip().str.lower()
            mask = col_lower.str.contains(term_norm, regex=False, na=False) | col_lower.apply(
                lambda v: bool(v) and v in term_norm
            )
            matches = df.loc[mask, email_columns[0]].dropna()
            matches = matches[matches.astype(str).str.strip() != ""]
            if not matches.empty:
                return str(matches.iloc[0]).strip()
        return ""

    def _find_supplier_email(self, fornecedor: str) -> str:
        return self._find_email_in_df(self.df_fornecedores, fornecedor)

    def _find_person_email(self, nome: str) -> str:
        return self._find_email_in_df(self.df_solicitantes, nome)

    def _find_destination_email(self, destino: str) -> str:
        return self._find_email_in_df(self.df_unidades, destino)

    def run(self):
        self.log_signal.emit("Processando regras de negócio e mapeando destinatários...")
        send_mode = self.smtp_config.get("mode", "smtp")
        sender = self.smtp_config.get("sender")
        password = self.smtp_config.get("password")
        smtp_server = self.smtp_config.get("smtp_server")
        port = int(self.smtp_config.get("port", 587))
        template = self.smtp_config.get("template", "")
        pasta_base_arquivos = self.smtp_config.get("pasta_arquivos", "")
        # Limpa senha da memória após extrair
        self.smtp_config.pop("password", None)

        if send_mode == "smtp" and (not sender or not password or not smtp_server):
            self.finished_signal.emit(False, "Configuração SMTP do Remetente ausente.")
            return

        if send_mode == "outlook" and win32com is None:
            self.finished_signal.emit(False, "Módulo pywin32 não encontrado. Instale com 'pip install pywin32'.")
            return

        # Uma única conexão SMTP autenticada para o lote inteiro, em vez de
        # reconectar e relogar a cada e-mail: além de mais rápido, evita
        # esbarrar em limites de login por minuto que provedores como
        # Office 365/Gmail costumam aplicar quando há muitos pedidos na
        # mesma extração.
        smtp_connection = None
        if send_mode == "smtp":
            try:
                smtp_connection = smtplib.SMTP(smtp_server, port)
                smtp_connection.starttls()
                smtp_connection.login(sender, password)
            except Exception as smtp_err:
                self.finished_signal.emit(False, f"Falha ao conectar ao servidor SMTP: {smtp_err}")
                return

        try:
            self._enviar_todos(send_mode, smtp_connection, sender, template, pasta_base_arquivos)
        finally:
            if smtp_connection is not None:
                try:
                    smtp_connection.quit()
                except Exception:
                    pass

        password = None
        self.finished_signal.emit(True, "Processo finalizado.")

    def _enviar_todos(self, send_mode, smtp_connection, sender, template, pasta_base_arquivos):
        for item in self.results:
            # amazonq-ignore-next-line
            if "erro" in item or item.get("status") == "Sem pedido emitido":
                continue

            req = item.get("requisicao")
            fornecedor_nome = item.get("fornecedor", "").strip()
            localidade = item.get("localidade", "").strip()

            destinatario_fornecedor = self._find_supplier_email(fornecedor_nome)
            if not destinatario_fornecedor:
                destinatario_fornecedor = sender

            copias_cc = []
            if item.get("criado_por"):
                email_criado_por = self._find_person_email(item.get("criado_por", ""))
                if email_criado_por:
                    copias_cc.append(email_criado_por)
            if item.get("solicitado_por"):
                email_solicitado_por = self._find_person_email(item.get("solicitado_por", ""))
                if email_solicitado_por:
                    copias_cc.append(email_solicitado_por)
            comprador_email = self.smtp_config.get("comprador_email", "")
            if comprador_email:
                for email in re.split(r"[;,]", comprador_email):
                    email = email.strip()
                    if email:
                        copias_cc.append(email)

            if item.get("destino") and self.df_unidades is not None:
                localidade = item.get("localidade", "")
                destino_email = self._find_destination_email(localidade)
                if destino_email:
                    copias_cc.append(destino_email)

            copias_cc = list(dict.fromkeys([c for c in copias_cc if c and c.strip()]))

            self.log_signal.emit(f"Disparando e-mail individual para Req #{req}...")
            pedidos = str(item.get("pedido", ""))
            subject = f"AUTORIZAÇÃO PC {pedidos}"

            if template:
                html_body = (
                    template.replace("{pedido}", str(item.get("pedido", "")))
                    .replace("{req}", str(req))
                    .replace("{fornecedor}", fornecedor_nome)
                    .replace("{criado_por}", str(item.get("criado_por", "")))
                    .replace("{solicitado_por}", str(item.get("solicitado_por", "")))
                    .replace("{localidade}", localidade)
                    .replace("{comprador}", str(item.get("comprador", "")))
                )
            else:
                html_body = f"<html><body><h3>Requisição #{req}</h3><p>Pedido: {item.get('pedido')}</p></body></html>"

            attachments = []
            if self.attachment_path and os.path.exists(self.attachment_path):
                attachments.append(self.attachment_path)

            if pasta_base_arquivos and os.path.exists(pasta_base_arquivos):
                nome_pasta_esperado = _nome_pasta_esperado(fornecedor_nome)
                for pasta in os.listdir(pasta_base_arquivos):
                    if pasta.lower() == nome_pasta_esperado:
                        caminho_pasta = os.path.join(pasta_base_arquivos, pasta)
                        for arquivo in os.listdir(caminho_pasta):
                            caminho_arquivo = os.path.join(caminho_pasta, arquivo)
                            if os.path.isfile(caminho_arquivo):
                                attachments.append(caminho_arquivo)
                                self.log_signal.emit(f"📎 Anexado arquivo da pasta: {arquivo}")

            if send_mode == "smtp":
                self._send_via_smtp(
                    smtp_connection, sender, destinatario_fornecedor,
                    copias_cc, subject, html_body, attachments, req,
                )
            else:
                self._send_via_outlook(sender, destinatario_fornecedor, copias_cc, subject, html_body, attachments)

    def _send_via_smtp(
        self, smtp_connection, sender, destinatario_fornecedor,
        copias_cc, subject, html_body, attachments, req,
    ):
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = destinatario_fornecedor
        if copias_cc:
            msg["Cc"] = ", ".join(copias_cc)
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        for caminho in attachments:
            self._anexar_arquivo(msg, caminho)

        try:
            smtp_connection.sendmail(sender, [destinatario_fornecedor] + copias_cc, msg.as_string())
            self.log_signal.emit(f"✅ E-mail enviado: Req #{req} via SMTP!")
        except Exception as smtp_err:
            self.log_signal.emit(f"❌ Falha envio #{req} via SMTP: {str(smtp_err)}")

    def _send_via_outlook(self, sender, destinatario_fornecedor, copias_cc, subject, html_body, attachments):
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.Subject = subject
            mail.To = destinatario_fornecedor
            if copias_cc:
                mail.CC = ", ".join(copias_cc)
            mail.HTMLBody = html_body

            for caminho in attachments:
                if os.path.exists(caminho):
                    mail.Attachments.Add(os.path.abspath(caminho))

            mail.Send()
            self.log_signal.emit(f"✅ E-mail enviado via Outlook: {subject}")
        except Exception as outlook_err:
            self.log_signal.emit(f"❌ Falha envio via Outlook: {str(outlook_err)}")

    def _anexar_arquivo(self, msg, caminho):
        try:
            with open(caminho, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(caminho)}")
                msg.attach(part)
        except Exception as e:
            self.log_signal.emit(f"Erro ao anexar {os.path.basename(caminho)}: {str(e)}")
