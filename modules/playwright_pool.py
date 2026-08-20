"""Gerenciador de contexto compartilhado do Playwright.

Elimina a duplicacao de abertura de contextos do Playwright que existia em:
- coupa_scraper.py (contexto para extracao)
- download_scraper.py (contexto para download)
- pdf_generator.py (contexto para geracao de PDF)

Cada um consumia ~200-400MB de RAM. Agora o pool gerencia e reusa contextos.
"""

import asyncio
import contextlib
import threading
from typing import Any

from modules.config import resolve_edge_executable


class PlaywrightPool:
    """Pool singleton de contextos do Playwright para Microsoft Edge.

    Uso:
        async with PlaywrightPool.get_context(user_data_dir="...") as context:
            page = context.pages[0] or await context.new_page()
    """

    _instance: PlaywrightPool | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._playwright = None
        self._playwright_loop: asyncio.AbstractEventLoop | None = None
        self._async_lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self._contexts: dict[str, Any] = {}
        self._ref_count: dict[str, int] = {}

    @classmethod
    def get_instance(cls) -> PlaywrightPool:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def _start_playwright(self):
        """Inicializa o Playwright, recriando a conexao se o event loop mudou.

        Cada worker (QThread) roda seu proprio event loop via
        asyncio.new_event_loop(). A conexao do driver do Playwright fica
        presa ao loop em que foi criada; reusa-la a partir de um loop
        diferente quebra o transporte assincrono ("'NoneType' object has
        no attribute 'send'" ao chamar launch_persistent_context). Por
        isso, ao detectar troca de loop, descarta a conexao antiga (e os
        contextos associados a ela, que tambem ficaram invalidos) em vez
        de tentar reaproveitar.
        """
        current_loop = asyncio.get_running_loop()
        if self._playwright is not None and self._playwright_loop is not current_loop:
            self._playwright = None
            self._contexts.clear()
            self._ref_count.clear()

        if self._playwright is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._playwright_loop = current_loop

    async def get_context(self, user_data_dir: str, channel: str = "msedge",
                          headless: bool = False, **kwargs) -> Any:
        """Retorna um contexto persistente do Edge, reutilizando se possivel."""
        current_loop = asyncio.get_running_loop()
        if self._async_lock is None or self._lock_loop is not current_loop:
            self._async_lock = asyncio.Lock()
            self._lock_loop = current_loop

        async with self._async_lock:
            caminho_edge = resolve_edge_executable()
            context_key = user_data_dir

            if context_key in self._contexts:
                self._ref_count[context_key] += 1
                return self._contexts[context_key]

            await self._start_playwright()
            context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                executable_path=caminho_edge,
                channel=channel,
                headless=headless,
                no_viewport=True,
                **kwargs
            )

            self._contexts[context_key] = context
            self._ref_count[context_key] = 1
            return context

    async def release_context(self, user_data_dir: str):
        """Libera um contexto quando nao for mais necessario.

        So fecha efetivamente quando o contagem de referencias chegar a zero.
        """
        context_key = user_data_dir
        if context_key not in self._contexts:
            return

        self._ref_count[context_key] -= 1
        if self._ref_count[context_key] <= 0:
            with contextlib.suppress(Exception):
                # best-effort: contexto já pode estar fechado/inválido
                await self._contexts[context_key].close()
            del self._contexts[context_key]
            del self._ref_count[context_key]

    async def cleanup_all(self) -> None:
        """Fecha todos os contextos e o Playwright. Chamar no encerramento do app."""
        for key in list(self._contexts.keys()):
            with contextlib.suppress(Exception):
                # best-effort: encerramento não deve travar por contexto já fechado
                await self._contexts[key].close()
        self._contexts.clear()
        self._ref_count.clear()
        if self._playwright:
            with contextlib.suppress(Exception):
                # best-effort: idem, app está encerrando de qualquer forma
                await self._playwright.stop()
            self._playwright = None
            self._playwright_loop = None


def cleanup_playwright_pool() -> None:
    """Item 3: Utilitário síncrono para chamar cleanup_all() no closeEvent do app."""
    import asyncio
    pool = PlaywrightPool._instance
    if pool is None:
        return
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(pool.cleanup_all())
        loop.close()
    except Exception:
        pass  # best-effort: chamado no closeEvent do app, não deve impedir o fechamento


class PlaywrightContextManager:
    """Context manager para uso com 'async with'.

    Uso:
        async with PlaywrightContextManager(user_data_dir="...") as context:
            page = context.pages[0] or await context.new_page()
    """

    def __init__(self, user_data_dir: str, channel: str = "msedge",
                 headless: bool = False, **kwargs):
        self.user_data_dir = user_data_dir
        self.channel = channel
        self.headless = headless
        self.kwargs = kwargs
        self._context = None

    async def __aenter__(self):
        pool = PlaywrightPool.get_instance()
        self._context = await pool.get_context(
            user_data_dir=self.user_data_dir,
            channel=self.channel,
            headless=self.headless,
            **self.kwargs
        )
        return self._context

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pool = PlaywrightPool.get_instance()
        await pool.release_context(self.user_data_dir)


class PlaywrightContextSyncManager:
    """Context manager para uso com 'with' (API síncrona do Playwright).

    Melhoria 4: padroniza a abertura de contextos do pdf_generator.py,
    que usava sync_playwright() diretamente, reutilizando o mesmo mecanismo
    de nome de perfil/base do pool. Como o pool é assíncrono, este gerenciador
    mantém o próprio ciclo de vida sync (start/stop), mas centraliza a lógica
    de resolução do executável do Edge e a criação do contexto persistente.

    Uso:
        with PlaywrightContextSyncManager(user_data_dir="...") as context:
            page = context.new_page()
    """

    def __init__(self, user_data_dir: str, channel: str = "msedge",
                 headless: bool = False, **kwargs):
        self.user_data_dir = user_data_dir
        self.channel = channel
        self.headless = headless
        self.kwargs = kwargs
        self._playwright = None
        self._context = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        caminho_edge = resolve_edge_executable()
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            executable_path=caminho_edge,
            channel=self.channel,
            headless=self.headless,
            no_viewport=True,
            **self.kwargs
        )
        return self._context

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass  # best-effort: contexto pode já estar fechado
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass  # best-effort: idem
        return False

