import base64
import contextlib
import os
import re
import smtplib
import threading
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import pandas as pd
import requests
from PyQt6.QtCore import QThread, pyqtSignal

from modules.config import MAP_FORNECEDORES, MAP_UNIDADES, get_power_automate_url

_CARACTERES_INVALIDOS_PASTA = re.compile(r'[\\/:*?"<>|\n\r\t]')
_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _extrair_emails_validos(texto: str) -> list:
    """Extrai e-mails válidos de item["emails"] (coupa_scraper.py).

    Esse campo vem preenchido com uma lista de e-mails encontrados na
    Justificativa da requisição, ou com um texto-placeholder como
    "[Não Solicitado]" (extração de e-mails desligada no perfil do
    comprador) ou "Nenhum e-mail encontrado" (extração ligada, mas nada
    encontrado). O regex filtra esses placeholders naturalmente, sem
    precisar conhecer o texto exato usado pelo scraper.
    """
    return _EMAIL_REGEX.findall(texto or "")


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
    _cache: dict[str, tuple[float, Any]] = {}
    _max_size = 10
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get(self, caminho: str) -> Any | None:
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

    def invalidate(self, caminho: str | None = None) -> None:
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

    def __init__(self, smtp_config: dict[str, Any], results: list[dict[str, Any]], attachment_path: str = ""):
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
                    # dtype=str evita que o pandas infira colunas como número
                    # (ex: código de fornecedor só com dígitos vira 123.0 em
                    # vez de "123", quebrando a comparação exata de código).
                    self.df_fornecedores = pd.read_excel(caminho_fornecedores, dtype=str)
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
                    self.df_solicitantes = pd.read_excel(caminho_solicitantes, dtype=str)
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
                    self.df_unidades = pd.read_excel(caminho_unidades, dtype=str)
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
        # Comparação exata (não mais substring nos dois sentidos) - evita
        # que um nome curto (ex: "ABC") case com outro que só o contém como
        # parte do nome (ex: "ABC Distribuidora"), pegando o e-mail errado.
        for col in candidate_columns:
            col_lower = df[col].astype(str).str.strip().str.lower()
            matches = df.loc[col_lower == term_norm, email_columns[0]].dropna()
            matches = matches[matches.astype(str).str.strip() != ""]
            if not matches.empty:
                return str(matches.iloc[0]).strip()
        return ""

    def _find_supplier_email(self, fornecedor: str, fornecedor_num: str = "") -> str:
        """Busca o e-mail do fornecedor por nome, exigindo também o código
        quando a planilha de mapeamento tem uma coluna de código E a linha
        correspondente tem esse código preenchido - evita que fornecedores
        homônimos (nome igual/parecido, empresas diferentes) peguem o
        e-mail um do outro. Linhas sem código na planilha continuam batendo
        só pelo nome (compatível com planilhas antigas, sem essa coluna).
        """
        df = self.df_fornecedores
        if not fornecedor.strip() or df is None:
            return ""
        nome_norm = fornecedor.strip().lower()
        num_norm = (fornecedor_num or "").strip().lower()

        email_columns = [c for c in df.columns if "email" in c]
        if not email_columns:
            return ""
        codigo_columns = [c for c in df.columns if "codigo" in c or "código" in c]
        nome_columns = [c for c in df.columns if c not in email_columns and c not in codigo_columns]
        if not nome_columns:
            return ""
        nome_col = nome_columns[0]
        nome_lower = df[nome_col].astype(str).str.strip().str.lower()

        if codigo_columns and num_norm:
            codigo_lower = df[codigo_columns[0]].astype(str).str.strip().str.lower()
            tem_codigo_na_linha = codigo_lower.str.len() > 0
            mask = (tem_codigo_na_linha & (nome_lower == nome_norm) & (codigo_lower == num_norm)) | (
                ~tem_codigo_na_linha & (nome_lower == nome_norm)
            )
        else:
            mask = nome_lower == nome_norm

        matches = df.loc[mask, email_columns[0]].dropna()
        matches = matches[matches.astype(str).str.strip() != ""]
        if not matches.empty:
            return str(matches.iloc[0]).strip()
        return ""

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

        power_automate_url = self.smtp_config.get("power_automate_url") or get_power_automate_url()
        if send_mode == "power_automate" and not power_automate_url:
            self.finished_signal.emit(
                False,
                "URL do flow do Power Automate não configurada. Configure em Gerenciar Perfis.",
            )
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
            self._enviar_todos(
                send_mode, smtp_connection, sender, template, pasta_base_arquivos, power_automate_url,
            )
        finally:
            if smtp_connection is not None:
                with contextlib.suppress(Exception):
                    smtp_connection.quit()  # best-effort: conexão pode já ter caído

        password = None
        self.finished_signal.emit(True, "Processo finalizado.")

    def _enviar_todos(
        self, send_mode, smtp_connection, sender, template, pasta_base_arquivos, power_automate_url="",
    ):
        """Agrupa os resultados por fornecedor e dispara 1 e-mail por grupo.

        Um fornecedor com várias requisições/pedidos no mesmo lote recebe um
        único e-mail consolidado (assunto com todos os pedidos, corpo com um
        bloco por pedido, anexos da pasta do fornecedor uma única vez) em vez
        de um e-mail repetido por linha.
        """
        grupos: dict[str, list[dict[str, Any]]] = {}
        for item in self.results:
            # amazonq-ignore-next-line
            if "erro" in item or item.get("status") == "Sem pedido emitido":
                continue
            chave = _nome_pasta_esperado(item.get("fornecedor", "").strip())
            grupos.setdefault(chave, []).append(item)

        for itens in grupos.values():
            self._enviar_grupo_fornecedor(
                itens, send_mode, smtp_connection, sender, template, pasta_base_arquivos, power_automate_url,
            )

    def _enviar_grupo_fornecedor(
        self, itens, send_mode, smtp_connection, sender, template, pasta_base_arquivos, power_automate_url,
    ):
        primeiro = itens[0]
        fornecedor_nome = primeiro.get("fornecedor", "").strip()
        fornecedor_num = primeiro.get("fornecedor_num", "").strip()

        destinatario_fornecedor = self._find_supplier_email(fornecedor_nome, fornecedor_num)
        if not destinatario_fornecedor:
            destinatario_fornecedor = sender

        copias_cc = []
        for item in itens:
            if item.get("criado_por"):
                email_criado_por = self._find_person_email(item.get("criado_por", ""))
                if email_criado_por:
                    copias_cc.append(email_criado_por)
            if item.get("solicitado_por"):
                email_solicitado_por = self._find_person_email(item.get("solicitado_por", ""))
                if email_solicitado_por:
                    copias_cc.append(email_solicitado_por)
            if item.get("destino") and self.df_unidades is not None:
                destino_email = self._find_destination_email(item.get("localidade", ""))
                if destino_email:
                    copias_cc.append(destino_email)
            copias_cc.extend(_extrair_emails_validos(item.get("emails", "")))

        comprador_email = self.smtp_config.get("comprador_email", "")
        if comprador_email:
            for email in re.split(r"[;,]", comprador_email):
                email = email.strip()
                if email:
                    copias_cc.append(email)

        copias_cc = list(dict.fromkeys([c for c in copias_cc if c and c.strip()]))

        requisicoes = [str(item.get("requisicao", "")) for item in itens]
        pedidos = [str(item.get("pedido", "")) for item in itens if item.get("pedido")]
        subject = f"AUTORIZAÇÃO PC {'/'.join(pedidos)}"

        if template:
            blocos_html = [
                template.replace("{pedido}", str(item.get("pedido", "")))
                .replace("{req}", str(item.get("requisicao", "")))
                .replace("{fornecedor}", fornecedor_nome)
                .replace("{criado_por}", str(item.get("criado_por", "")))
                .replace("{solicitado_por}", str(item.get("solicitado_por", "")))
                .replace("{localidade}", item.get("localidade", "").strip())
                .replace("{comprador}", str(item.get("comprador", "")))
                for item in itens
            ]
            html_body = "<hr>".join(blocos_html)
        else:
            linhas_html = "".join(
                f"<li>Requisição #{item.get('requisicao')} - Pedido: {item.get('pedido')}</li>"
                for item in itens
            )
            html_body = f"<html><body><h3>Fornecedor: {fornecedor_nome}</h3><ul>{linhas_html}</ul></body></html>"

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

        label_req = ", ".join(requisicoes)
        self.log_signal.emit(
            f"Disparando e-mail consolidado para {fornecedor_nome} ({len(itens)} pedido(s), Req #{label_req})..."
        )

        if send_mode == "smtp":
            self._send_via_smtp(
                smtp_connection, sender, destinatario_fornecedor,
                copias_cc, subject, html_body, attachments, label_req,
            )
        elif send_mode == "power_automate":
            self._send_via_power_automate(
                power_automate_url, destinatario_fornecedor,
                copias_cc, subject, html_body, attachments, label_req,
            )
        else:
            self._send_via_outlook(sender, destinatario_fornecedor, copias_cc, subject, html_body, attachments)

    def _send_via_smtp(
        self, smtp_connection, sender, destinatario_fornecedor,
        copias_cc, subject, html_body, attachments, label_req,
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
            self.log_signal.emit(f"✅ E-mail enviado: Req #{label_req} via SMTP!")
        except Exception as smtp_err:
            self.log_signal.emit(f"❌ Falha envio #{label_req} via SMTP: {str(smtp_err)}")

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

    def _send_via_power_automate(
        self, url, destinatario_fornecedor, copias_cc, subject, html_body, attachments, label_req,
    ):
        payload = {
            "destinatario": destinatario_fornecedor,
            "cc": copias_cc,
            "assunto": subject,
            "corpo_html": html_body,
            "anexos": self._codificar_anexos_base64(attachments),
        }
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            self.log_signal.emit(f"✅ E-mail enviado: Req #{label_req} via Power Automate!")
        except requests.RequestException as power_automate_err:
            self.log_signal.emit(f"❌ Falha envio #{label_req} via Power Automate: {str(power_automate_err)}")

    def _codificar_anexos_base64(self, attachments):
        anexos = []
        for caminho in attachments:
            try:
                with open(caminho, "rb") as f:
                    conteudo_base64 = base64.b64encode(f.read()).decode("ascii")
                anexos.append({"nome": os.path.basename(caminho), "conteudo_base64": conteudo_base64})
            except OSError as e:
                self.log_signal.emit(f"Erro ao anexar {os.path.basename(caminho)}: {str(e)}")
        return anexos

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
