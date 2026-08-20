import asyncio
import contextlib
import re
import threading
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from modules.config import (
    PERFIL_EDGE_DOWNLOAD,
    get_coupa_base_url,
    resolve_edge_executable,
)
from modules.playwright_pool import PlaywrightContextManager

_JS_NEXT_SIBLING_TEXT = (
    "(element) => element.nextElementSibling ? "
    "element.nextElementSibling.innerText : element.innerText"
)

_TIPOS_RECURSO_BLOQUEADOS = ("image", "media", "font", "stylesheet")


def _bloquear_recursos_pesados(route):
    """Aborta imagem/mídia/fonte/CSS para acelerar a extração.

    Só é registrado DEPOIS do login confirmado (ver _extrair) - se ativo
    durante a tela de login do Coupa/SSO, ela carrega sem nenhum estilo,
    o que dificulta o login manual.
    """
    if route.request.resource_type in _TIPOS_RECURSO_BLOQUEADOS:
        return route.abort()
    return route.continue_()


def _describe_network_error(exc: Exception) -> str | None:
    """Traduz erros comuns de rede/conexão do Playwright para uma mensagem
    acionável em vez do texto cru da exceção (ex: "net::ERR_NAME_NOT_RESOLVED
    at https://...", que não deixa claro se o problema é a internet, a URL
    configurada ou o Coupa fora do ar).

    Retorna None quando o erro não é reconhecido como falha de rede/conexão -
    nesse caso o chamador deve usar a mensagem original da exceção.
    """
    texto_lower = str(exc).lower()

    if "err_name_not_resolved" in texto_lower or "err_internet_disconnected" in texto_lower:
        return (
            "Sem conexão com a internet, ou a URL da instância do Coupa está "
            "incorreta. Verifique sua rede e a configuração em COUPA_BASE_URL."
        )
    if "err_connection_refused" in texto_lower or "err_connection_timed_out" in texto_lower:
        return (
            "Não foi possível conectar à instância do Coupa configurada. "
            "Ela pode estar fora do ar, ou sua rede/VPN está bloqueando o acesso."
        )
    if "timeout" in texto_lower and ("goto" in texto_lower or "navigat" in texto_lower or "waiting for" in texto_lower):
        return (
            "O Coupa demorou demais para responder (timeout). Sua conexão pode "
            "estar lenta, ou o Coupa está sobrecarregado - tente novamente."
        )
    return None


def _extrair_pedidos_emitidos(msgbar_texto: str) -> list[str]:
    """Extrai todos os "PO nº X" presentes na barra de status (#msgbar) do Coupa.

    Uma requisição pode ter mais de um pedido emitido (ex: item dividido
    entre fornecedores diferentes) - por isso usa findall em vez de search,
    e deduplica preservando a ordem de aparição.
    """
    matches = re.findall(r'PO\s*nº\s*\d+', msgbar_texto or "", re.IGNORECASE)
    return list(dict.fromkeys(matches))


class CoupaScraper:
    """Scraper para extrair dados de requisições do Coupa."""

    def __init__(
        self,
        requisicoes: list[str],
        config_extrair: dict[str, bool],
        pause_event=None,
        login_confirmation_event=None,
        cancel_event=None,
    ):
        self.requisicoes = requisicoes
        self.config_extrair = config_extrair
        self.pause_event = pause_event
        self.login_confirmation_event = login_confirmation_event
        self.cancel_event = cancel_event

    async def aguardar_retomada(self, log_callback) -> bool:
        """Aguarda retomada. Sleep reduzido de 0.5s para 0.1s (5x mais responsivo).

        Retorna False se a extração foi cancelada enquanto pausada - antes
        disso não havia como sair dessa espera a não ser fechando o app
        inteiro, já que só o pause_event era checado no loop.
        """
        if not self.pause_event or not self.pause_event.is_set():
            # amazonq-ignore-next-line
            return True

        log_callback("⏸️ Extração pausada. Clique em 'Retomar Extração' para continuar.")
        while self.pause_event.is_set():
            if self.cancel_event and self.cancel_event.is_set():
                return False
            await asyncio.sleep(0.1)
        log_callback("▶️ Extração retomada.")
        return True

    async def aguardar_confirmacao_login(self, log_callback) -> bool:
        """Aguarda confirmação de login. Sleep reduzido de 0.5s para 0.1s (5x mais responsivo).

        Retorna False se a extração foi cancelada nessa espera - sem isso,
        um Edge que não abre corretamente ou uma pessoa que não consegue
        concluir o login travava aqui indefinidamente, sem nenhuma saída
        além de fechar o aplicativo inteiro.
        """
        log_callback(
            "🔐 Faça o login no Coupa no Edge e clique em 'Confirmar Login e Iniciar Extração'."
        )
        while not self.login_confirmation_event.is_set():
            if self.cancel_event and self.cancel_event.is_set():
                return False
            await asyncio.sleep(0.1)
        log_callback("✅ Login confirmado. Iniciando extração...")
        return True

    async def run(self, log_callback, edge_ready_callback=None) -> list[dict[str, Any]]:
        extracted_data: list[dict[str, Any]] = []
        log_callback("⚡ Iniciando Edge em modo rápido...")

        caminho_edge = resolve_edge_executable()
        if not caminho_edge:
            log_callback("ERRO CRÍTICO: Caminho do Microsoft Edge não encontrado.")
            log_callback(
                "💡 Defina a variável de ambiente EDGE_EXECUTABLE_PATH ou instale o Edge no caminho padrão."
            )
            return [{"Erro": "Microsoft Edge não encontrado."}]

        user_data_dir = Path(PERFIL_EDGE_DOWNLOAD)
        try:
            user_data_dir.mkdir(parents=True, exist_ok=True)
        except Exception as dir_err:
            log_callback(f"Erro ao acessar pasta de perfil: {str(dir_err)}")
            return [{"Erro": f"Falha de permissão de pasta: {str(dir_err)}"}]

        # Melhoria 3: usa o PlaywrightPool/PlaywrightContextManager em vez de
        # abrir um contexto novo via async_playwright() a cada execução.
        try:
            async with PlaywrightContextManager(user_data_dir=str(user_data_dir)) as context:
                return await self._extrair(
                    context,
                    log_callback,
                    edge_ready_callback,
                    extracted_data,
                )
        except Exception as e:
            log_callback(f"ERRO CRÍTICO: {str(e)}")
            log_callback("\n💡 Certifique-se de FECHAR o Microsoft Edge antes de executar!")
            return [{"Erro": f"Feche o Edge e tente novamente. Detalhe: {str(e)}"}]

    async def _extrair(
        self,
        context,
        log_callback,
        edge_ready_callback,
        extracted_data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Executa a extração das requisições dentro de um contexto gerenciado."""
        coupa_base_url = get_coupa_base_url()
        pages = context.pages
        page = pages[0] if pages else await context.new_page()
        page.set_default_timeout(5000)

        try:
            await page.goto(coupa_base_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            mensagem_rede = _describe_network_error(e)
            if mensagem_rede:
                # Erro de rede na primeira navegação é fatal para a extração
                # inteira - continuar tentaria acessar todas as requisições
                # uma por uma e falharia identicamente em cada uma.
                log_callback(f"❌ {mensagem_rede}")
                return [{"Erro": mensagem_rede}]
            log_callback(f"Não foi possível abrir a página inicial do Coupa: {str(e)}")

        if edge_ready_callback:
            edge_ready_callback()
        if not await self.aguardar_confirmacao_login(log_callback):
            log_callback("❌ Extração cancelada pelo usuário.")
            return extracted_data

        # Só bloqueia imagem/mídia/fonte/CSS a partir daqui - com o login já
        # confirmado, essas páginas não precisam mais carregar com estilo
        # completo, e a extração fica mais rápida.
        with contextlib.suppress(Exception):
            # rota já definida em contexto reutilizado
            await context.route("**/*", _bloquear_recursos_pesados)

        for idx, req in enumerate(self.requisicoes, 1):
            if not await self.aguardar_retomada(log_callback):
                log_callback("❌ Extração cancelada pelo usuário.")
                break
            if self.cancel_event and self.cancel_event.is_set():
                log_callback("❌ Extração cancelada pelo usuário.")
                break
            url_requisicao = f"{coupa_base_url.rstrip('/')}/requisition_headers/{req.strip()}"
            log_callback(f"[{idx}/{len(self.requisicoes)}] Acessando Requisição #{req}...")

            try:
                await page.goto(url_requisicao, wait_until="domcontentloaded", timeout=30000)

                if "login" in page.url.lower() or await page.query_selector("input[type='password']"):
                    log_callback("⚠️ Login detectado! Faça o login manualmente...")
                    await page.wait_for_url(lambda url: "login" not in url.lower(), timeout=300000)
                    await page.wait_for_load_state("domcontentloaded")

                await page.wait_for_selector("body", state="attached", timeout=5000)

                # A confirmação de pedido emitido aparece na barra de status
                # (#msgbar) do Coupa, já carregada junto com o HTML da
                # própria página - não é reescrita a cada verificação. Por
                # isso a leitura tem que vir ANTES de qualquer limpeza: limpar
                # primeiro (como uma versão anterior deste código fazia)
                # apaga esse conteúdo sem que ele seja recriado, fazendo
                # requisições com pedido real saírem como "sem pedido". Só
                # depois de ler é que a barra é limpa, para não vazar esse
                # texto para a checagem da PRÓXIMA requisição (que é o bug
                # original: pedido de uma requisição anterior "grudando" na
                # seguinte, já que #msgbar não é recriado entre navegações).
                seletor_msgbar_com_po = "#msgbar:has-text('PO nº')"
                with contextlib.suppress(Exception):
                    await page.wait_for_selector(seletor_msgbar_com_po, state="attached", timeout=2500)

                pedidos_encontrados: list[str] = []
                msgbar_elemento = await page.query_selector("#msgbar")
                if msgbar_elemento:
                    raw_text = await msgbar_elemento.inner_text()
                    pedidos_encontrados = _extrair_pedidos_emitidos(raw_text)

                await page.evaluate(
                    "() => { const el = document.getElementById('msgbar'); "
                    "if (el) el.textContent = ''; }"
                )

                if not pedidos_encontrados:
                    log_callback(f"⚠️ Requisição #{req} ignorada: Nenhum pedido emitido.")
                    extracted_data.append({"requisicao": req, "status": "Sem pedido emitido"})
                    continue

                if len(pedidos_encontrados) > 1:
                    log_callback(
                        f"ℹ️ Requisição #{req} tem {len(pedidos_encontrados)} pedidos emitidos: "
                        f"{', '.join(pedidos_encontrados)}."
                    )

                fornecedor_nome = "Não localizado"
                fornecedor_numero = "Não localizado"

                aba_carrinho = await page.query_selector("a:has-text('Itens do carrinho')")
                if aba_carrinho:
                    await aba_carrinho.click()
                    with contextlib.suppress(Exception):
                        # timeout esperado quando o fornecedor não tem link de detalhe
                        await page.wait_for_selector("a[href*='/suppliers/show/']", timeout=3000)

                fornecedor_link = await page.query_selector("a.s-coupaSimpleTooltip[href*='/suppliers/show/']")
                if not fornecedor_link:
                    fornecedor_link = await page.query_selector("a[href*='/suppliers/show/']")

                if fornecedor_link:
                    title_text = await fornecedor_link.get_attribute("title")
                    if title_text:
                        partes = [parte.strip() for parte in title_text.split(" - ") if parte.strip()]
                        if len(partes) >= 2:
                            fornecedor_numero = partes[0]
                            fornecedor_nome = partes[1]
                        else:
                            match_split = re.search(r'^(\d+)\s*[-–]\s*(.+)$', title_text)
                            if match_split:
                                fornecedor_numero = match_split.group(1).strip()
                                fornecedor_nome = match_split.group(2).strip()
                            else:
                                fornecedor_nome = title_text
                    else:
                        fornecedor_nome = await fornecedor_link.inner_text()
                        fornecedor_nome = fornecedor_nome.strip()

                criado_por = "[Não Solicitado]"
                criado_por_email = ""
                if self.config_extrair.get("criado_por", True):
                    criado_por_label = await page.query_selector(
                        "td:has-text('Criado por'), label:has-text('Criado por'), "
                        "span:has-text('Criado por')"
                    )
                    if criado_por_label:
                        criado_por = await page.evaluate(
                            _JS_NEXT_SIBLING_TEXT,
                            criado_por_label,
                        )
                        criado_por = criado_por.replace("Criado por", "").strip()
                        email_match = re.search(
                            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                            criado_por,
                        )
                        if email_match:
                            criado_por_email = email_match.group(0)

                solicitado_por = "[Não Solicitado]"
                solicitado_por_email = ""
                if self.config_extrair.get("solicitado_por", True):
                    solicitado_por_label = await page.query_selector(
                        "td:has-text('Solicitado por'), label:has-text('Solicitado por'), "
                        "span:has-text('Solicitado por')"
                    )
                    if solicitado_por_label:
                        solicitado_por = await page.evaluate(
                            _JS_NEXT_SIBLING_TEXT,
                            solicitado_por_label,
                        )
                        solicitado_por = solicitado_por.split("(")[0].replace("Solicitado por", "").strip()
                        email_match = re.search(
                            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                            solicitado_por,
                        )
                        if email_match:
                            solicitado_por_email = email_match.group(0)

                emails = "[Não Solicitado]"
                if self.config_extrair.get("emails", False):
                    emails = "Nenhum e-mail encontrado"
                    justificativa_label = await page.query_selector(
                        "td:has-text('Justificativa'), label:has-text('Justificativa'), "
                        "span:has-text('Justificativa')"
                    )
                    if justificativa_label:
                        justificativa_texto = await page.evaluate(
                            _JS_NEXT_SIBLING_TEXT,
                            justificativa_label,
                        )
                        emails_encontrados = re.findall(
                            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                            justificativa_texto,
                        )
                        if emails_encontrados:
                            emails = ", ".join(list(dict.fromkeys(emails_encontrados)))

                cidade_estado = "[Não Solicitado]"
                if self.config_extrair.get("destino", False):
                    cidade_estado = "Não localizado"
                    endereco_label = await page.query_selector(
                        "h3:has-text('Endereço de entrega'), div:has-text('Endereço de entrega'), "
                        "td:has-text('Endereço')"
                    )
                    if endereco_label:
                        endereco_texto = await page.evaluate(
                            "(element) => { let p = element.closest('.card, .section, table, div, td'); "
                            "return p ? p.innerText : ''; }",
                            endereco_label,
                        )
                        if not endereco_texto.strip():
                            endereco_texto = await page.evaluate(
                                _JS_NEXT_SIBLING_TEXT,
                                endereco_label,
                            )
                        if endereco_texto:
                            match_cep_cidade = re.search(
                                r'\d{5}-\d{3}\s+([A-Za-zÀ-ÿ0-9\-\s]+?)\s+Brasil\b',
                                endereco_texto,
                                re.IGNORECASE,
                            )
                            if not match_cep_cidade:
                                match_cep_cidade = re.search(
                                    r'\d{5}-\d{3}\s+([A-ZÀ-ÿ\s]+?)\s+[A-Z]{2}\b',
                                    endereco_texto,
                                    re.IGNORECASE,
                                )
                            if match_cep_cidade:
                                cidade_estado = match_cep_cidade.group(1).strip()
                            else:
                                linhas = [ln.strip() for ln in endereco_texto.split("\n") if ln.strip()]
                                for linha in reversed(linhas):
                                    match_l = re.search(r'^([A-Z\s]+?)\s+([A-Z]{2})$', linha)
                                    if match_l:
                                        cidade_estado = f"{match_l.group(1).strip()} / {match_l.group(2).strip()}"
                                        break

                for pedido_texto in pedidos_encontrados:
                    extracted_data.append(
                        {
                            "requisicao": req,
                            "status": "Com pedido",
                            "pedido": pedido_texto,
                            "fornecedor": fornecedor_nome,
                            "fornecedor_num": fornecedor_numero,
                            "criado_por": criado_por,
                            "criado_por_email": criado_por_email,
                            "solicitado_por": solicitado_por,
                            "solicitado_por_email": solicitado_por_email,
                            "emails": emails,
                            "localidade": cidade_estado,  # campo canônico único (Item 9)
                        }
                    )

            except Exception as e:
                mensagem_rede = _describe_network_error(e)
                if mensagem_rede:
                    log_callback(f"❌ Requisição #{req}: {mensagem_rede}")
                    extracted_data.append({"requisicao": req, "erro": mensagem_rede})
                    # Erro de rede também é fatal aqui: as requisições restantes
                    # atingiriam o mesmo host indisponível e falhariam identicamente.
                    log_callback("❌ Erro de rede - abortando as requisições restantes.")
                    break
                else:
                    log_callback(f"Erro na requisição #{req}: {str(e)}")
                    extracted_data.append({"requisicao": req, "erro": f"Falha na extração: {str(e)}"})

        return extracted_data


class AutomationWorker(QThread):
    log_signal = pyqtSignal(str)
    edge_ready_signal = pyqtSignal()
    finished_signal = pyqtSignal(list)
    progress_signal = pyqtSignal(int)  # Item 21: Sinal de progresso (0-100)

    def __init__(self, requisicoes: list[str], config_extrair: dict[str, bool]):
        super().__init__()
        self.requisicoes = requisicoes
        self.config_extrair = config_extrair
        self.pause_event = threading.Event()
        self.login_confirmation_event = threading.Event()
        self.cancel_event = threading.Event()

    def pausar(self):
        self.pause_event.set()

    def retomar(self):
        self.pause_event.clear()

    def confirmar_login(self):
        self.login_confirmation_event.set()

    def cancelar(self):
        """Sinaliza cancelamento - checado a cada 0.1s tanto na espera de
        pausa quanto na de confirmação de login (ver CoupaScraper), então a
        thread encerra rapidamente sem precisar fechar o app inteiro."""
        self.cancel_event.set()

    def run(self):
        """Melhoria 6: try/except garante que finished_signal SEMPRE seja emitido."""
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            scraper = CoupaScraper(
                self.requisicoes,
                self.config_extrair,
                self.pause_event,
                self.login_confirmation_event,
                self.cancel_event,
            )

            def log_with_progress(msg: str):
                self.log_signal.emit(msg)
                match = re.search(r'\[(\d+)/(\d+)\]', msg)
                if match:
                    current = int(match.group(1))
                    total_req = int(match.group(2))
                    if total_req > 0:
                        self.progress_signal.emit(int((current / total_req) * 100))
                elif "extração" in msg.lower() and "concluída" in msg.lower():
                    self.progress_signal.emit(100)

            results = loop.run_until_complete(
                scraper.run(log_with_progress, self.edge_ready_signal.emit)
            )
            self.finished_signal.emit(results)
        except Exception as e:
            self.log_signal.emit(f"❌ ERRO CRÍTICO na thread de extração: {str(e)}")
            try:
                import traceback
                self.log_signal.emit(traceback.format_exc())
            except Exception:
                pass  # best-effort: não deixa o log do traceback mascarar o erro original
            # Garante que a UI não fique presa com botões desabilitados
            self.finished_signal.emit([{"erro": f"Falha crítica na automação: {str(e)}"}])
        finally:
            if loop is not None:
                with contextlib.suppress(Exception):
                    loop.close()  # best-effort: loop pode já estar fechado

