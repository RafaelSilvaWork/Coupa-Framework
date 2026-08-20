"""Gerenciamento centralizado do fluxo automático entre abas.

Este módulo substitui a lógica espalhada de:
- Flags _modo_automatico_N (getattr frágil)
- Orquestração de execução sequencial via QTimer
- Validação de pré-requisitos das abas

Uso:
    runner = AutomaticFlowRunner(parent_framework)
    runner.start(results, [2, 3, 4, 5, 6])
"""

import contextlib
import re
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class ModoAutomatico:
    """Gerencia o estado de modo automático de forma centralizada.

    Substitui as flags _modo_automatico_2, _modo_automatico_3 etc.
    espalhadas em arquivos diferentes, evitando erros de esquecimento.

    Melhoria 5: singleton real via __new__ — todas as chamadas
    ``ModoAutomatico()`` retornam a MESMA instância, eliminando os
    pseudo-singletons duplicados que existiam em ui_downloader,
    ui_pdf_generator e ui_email_sender.
    """

    _instancia_unica = None

    def __new__(cls):
        if cls._instancia_unica is None:
            cls._instancia_unica = super().__new__(cls)
        return cls._instancia_unica

    def __init__(self):
        # Guard: evita re-inicializar o estado a cada chamada do singleton
        if not hasattr(self, "_inicializado"):
            self._ativo = False
            self._aba_origem: str | None = None
            self._inicializado = True

    def ativar(self, aba_origem: str = "Aba 1"):
        self._ativo = True
        self._aba_origem = aba_origem

    def desativar(self):
        self._ativo = False
        self._aba_origem = None

    @property
    def ativo(self) -> bool:
        return self._ativo

    @property
    def aba_origem(self) -> str | None:
        return self._aba_origem

    def __bool__(self):
        return self._ativo


def get_modo_automatico() -> ModoAutomatico:
    """Ponto de acesso único e centralizado ao singleton ModoAutomatico.

    Melhoria 5: todos os widgets e o runner devem usar esta função em vez de
    declarar o próprio atributo ``self._modo_automatico``. Assim, o estado do
    modo automático fica consolidado em um único ponto (fluxo_orquestrador).
    """
    return ModoAutomatico()


class AutomaticFlowRunner(QObject):
    """Orquestra a execução automática em cadeia entre as abas.

    Encapsula toda a lógica de:
    - Preparação de dados (requisições, pedidos)
    - Validação de pré-requisitos
    - Execução sequencial via signals (sem delays arbitrários)
    - Callbacks de finalização

    Substitui os métodos em CoupaExtractorWidget:
    - iniciar_fluxo_automatico()
    - _executar_proxima_aba()
    - _aba_automatica_finalizada()
    - _fluxo_finalizado()
    - encadear_proximas_abas()
    - validar_requisitos_fluxo()
    """

    # Delay mínimo para permitir que a UI processe a troca de aba (showEvent)
    # antes de executar a próxima aba. 50ms é suficiente sem causar lentidão perceptível.
    UI_DELAY_MS = 50

    flow_finished = pyqtSignal(bool, str)

    _ABA_MAP = {
        2: "tab_downloader",
        3: "tab_pdf_generator",
        4: "tab_renomeador",
        5: "tab_organizador",
        6: "tab_email_sender",
    # amazonq-ignore-next-line
    }

    _ABA_NAMES = {
        2: "Aba 2 - Baixador de Orçamentos",
        3: "Aba 3 - Gerador de PDF de Pedidos",
        4: "Aba 4 - Renomeador",
        5: "Aba 5 - Organizador",
        6: "Aba 6 - Disparo de E-mails",
    }

    def __init__(self, parent_framework):
        super().__init__(parent_framework)
        self.parent_fw = parent_framework
        self._modo = get_modo_automatico()
        self._widget_conectado = None
        self._log_callback = None
        self._reset_state()

    def _reset_state(self):
        """Reseta o estado interno do runner."""
        self._abas_executar: list[int] = []
        self._aba_atual_index = 0
        self._requisicoes_ok = False
        self._pedidos_ok = False
        self._results: list[dict[str, Any]] = []

    # --- Mapeamento de abas ---

    def _get_widget(self, aba_num: int):
        """Retorna o widget da aba pelo número."""
        attr_name = self._ABA_MAP.get(aba_num)
        if attr_name and hasattr(self.parent_fw, attr_name):
            return getattr(self.parent_fw, attr_name)
        return None

    # --- Preparação dos dados ---

    def _preparar_dados(self, results: list[dict[str, Any]]):
        """Extrai requisições e pedidos dos resultados."""
        requisicoes = []
        pedidos = []
        for item in results:
            if item.get("status") == "Com pedido":
                req = str(item.get("requisicao", "")).strip()
                if req:
                    requisicoes.append(req)
                pedido_texto = item.get("pedido", "")
                match_num = re.search(r'\d+', pedido_texto)
                if match_num:
                    pedidos.append(f"{match_num.group(0)}\t{item.get('requisicao', '')}")
        return requisicoes, pedidos

    # --- Validação ---

    def validar_requisitos(self, abas: list[int], results: list[dict[str, Any]]) -> list[str]:
        """Valida pré-requisitos de todas as abas selecionadas.

        Deriva requisições/pedidos dos resultados da extração e delega a
        validação de configuração para validar_pre_requisitos_abas.
        (Melhoria 9: lógica centralizada no runner, sem duplicação na Aba 1.)

        Returns:
            Lista de mensagens de falha. Se vazia, todos os pré-requisitos foram atendidos.
        """
        requisicoes, pedidos = self._preparar_dados(results)
        return self.validar_pre_requisitos_abas(
            abas,
            tem_requisicoes=bool(requisicoes),
            tem_pedidos=bool(pedidos),
        )

    def validar_pre_requisitos_abas(
        self,
        abas: list[int],
        tem_requisicoes: bool = True,
        tem_pedidos: bool = True,
    ) -> list[str]:
        """Valida os pré-requisitos de CONFIGURAÇÃO das abas (Melhoria 9).

        Usado pela Aba 1 antes da extração (open_edge_for_login), quando os
        resultados ainda não existem — por isso recebe flags de disponibilidade
        de dados em vez de results. A validação com os dados reais da extração
        é feita depois, via validar_requisitos().

        Args:
            abas: Lista de números das abas a validar.
            tem_requisicoes: Se a extração fornecerá requisições (Aba 2).
            tem_pedidos: Se a extração fornecerá pedidos (Aba 3).

        Returns:
            Lista de falhas. Vazia se todos os pré-requisitos foram atendidos.
        """
        tem_dados = {2: tem_requisicoes, 3: tem_pedidos, 4: True, 5: True, 6: True}
        falhas = []

        for aba_num in abas:
            nome_aba = self._ABA_NAMES.get(aba_num, f"Aba {aba_num}")

            if not tem_dados.get(aba_num, True):
                falhas.append(f"  - {nome_aba}: sem dados da extração (pulando)")
                continue

            widget = self._get_widget(aba_num)
            if widget and hasattr(widget, 'check_prerequisites'):
                ok, msg = widget.check_prerequisites()
                if not ok:
                    falhas.append(f"  - {nome_aba}: {msg}")

        return falhas

    # --- Execução do fluxo ---

    def start(self, results: list[dict[str, Any]], abas: list[int], log_callback=None):
        """Inicia o fluxo automático.

        Args:
            results: Resultados da extração da Aba 1
            abas: Lista de números das abas a executar
            log_callback: Função para logging
        """
        if self._modo.ativo:
            if log_callback:
                log_callback("Fluxo automático já em andamento. Ignorando nova solicitação.")
            return

        self._modo.ativar()
        self._results = results

        requisicoes, pedidos = self._preparar_dados(results)
        self._requisicoes_ok = bool(requisicoes)
        self._pedidos_ok = bool(pedidos)

        # Validar pré-requisitos
        falhas = self.validar_requisitos(abas, results)
        if falhas:
            msg = "Fluxo automático NÃO pode ser iniciado.\n\n"
            msg += "Configure os requisitos abaixo nas respectivas abas antes de executar:\n\n"
            msg += "\n".join(falhas)
            if log_callback:
                log_callback(msg)
            self._modo.desativar()
            self.flow_finished.emit(False, msg)
            return

        # Preencher dados nas abas
        aba2 = self._get_widget(2)
        aba3 = self._get_widget(3)
        aba6 = self._get_widget(6)

        if 2 in abas and self._requisicoes_ok and aba2:
            aba2.txt_req_list.setPlainText("\n".join(requisicoes))
            if hasattr(aba2, 'log'):
                aba2.log(f"Recebido(s) {len(requisicoes)} requisição(ões) da Aba 1 via fluxo automático.")

        if 3 in abas and self._pedidos_ok and aba3:
            aba3.txt_pedidos.setPlainText("\n".join(pedidos))
            if hasattr(aba3, 'log'):
                aba3.log(f"Recebido(s) {len(pedidos)} pedido(s) da Aba 1 via fluxo automático.")

        if 6 in abas and aba6 and hasattr(aba6, 'receber_resultados'):
            aba6.receber_resultados(results)

        if not self._requisicoes_ok and not self._pedidos_ok:
            if log_callback:
                log_callback("Cadeia: nenhuma requisição com pedido emitido para propagar às próximas abas.")
            self._modo.desativar()
            self.flow_finished.emit(True, "Nenhum dado para propagar.")
            return

        # Iniciar execução sequencial
        self._abas_executar = [a for a in abas if a in [2, 3, 4, 5, 6]]
        self._aba_atual_index = 0

        if log_callback:
            log_callback(f"Iniciando fluxo automático: Abas {self._abas_executar} serão executadas em sequência.")

        primeiro_widget = self._get_widget(self._abas_executar[0]) if self._abas_executar else None
        if primeiro_widget and hasattr(self.parent_fw, 'tab_widget'):
            self.parent_fw.tab_widget.setCurrentWidget(primeiro_widget)

        # Usa UI_DELAY_MS = 0 para agendar na próxima iteração do event loop,
        # sem delay arbitrário. A UI terá tempo de processar a troca de aba.
        QTimer.singleShot(self.UI_DELAY_MS, self._executar_proxima_aba)

    def _executar_proxima_aba(self):
        """Executa a próxima aba da fila."""
        if self._aba_atual_index >= len(self._abas_executar):
            self._fluxo_finalizado()
            return

        aba_num = self._abas_executar[self._aba_atual_index]
        widget = self._get_widget(aba_num)

        if not widget:
            self._aba_atual_index += 1
            self._agendar_proxima_aba()
            return

        # Pular abas sem dados
        if aba_num == 2 and not self._requisicoes_ok:
            self._aba_atual_index += 1
            self._agendar_proxima_aba()
            return
        if aba_num == 3 and not self._pedidos_ok:
            self._aba_atual_index += 1
            self._agendar_proxima_aba()
            return

        # Verificar pré-requisitos
        if hasattr(widget, 'check_prerequisites'):
            ok, msg = widget.check_prerequisites()
            if not ok:
                self._aba_atual_index += 1
                self._agendar_proxima_aba()
                return

        # Conectar sinal de finalização
        if hasattr(widget, 'automatico_finished'):
            with contextlib.suppress(TypeError):
                widget.automatico_finished.disconnect()
            widget.automatico_finished.connect(self._aba_finalizada)

        # Navegar para a aba
        if hasattr(self.parent_fw, 'tab_widget'):
            self.parent_fw.tab_widget.setCurrentWidget(widget)

        # Executar
        if hasattr(widget, 'executar_automatico'):
            widget.executar_automatico()
        else:
            self._aba_atual_index += 1
            self._agendar_proxima_aba()

    def _agendar_proxima_aba(self):
        """Agenda a próxima aba usando UI_DELAY_MS para garantir que o event loop
        processe a troca de aba antes de executar_automatico ser chamado.
        """
        QTimer.singleShot(self.UI_DELAY_MS, self._executar_proxima_aba)

    def _aba_finalizada(self, sucesso: bool, mensagem: str):
        """Callback quando uma aba conclui sua execução."""
        self._aba_atual_index += 1
        self._agendar_proxima_aba()

    def _fluxo_finalizado(self):
        """Finaliza o fluxo automático."""
        self._modo.desativar()
        self.flow_finished.emit(True, "Fluxo automático concluído com sucesso!")

