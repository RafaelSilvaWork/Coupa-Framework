import asyncio

from modules.playwright_pool import (
    PlaywrightContextManager,
    PlaywrightPool,
    cleanup_playwright_pool,
)


class _FakeContext:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _FakeContextQueFalhaAoFechar(_FakeContext):
    async def close(self):
        raise RuntimeError("contexto já foi encerrado externamente")


class _FakeBrowserType:
    def __init__(self):
        self.contexts_created = []

    async def launch_persistent_context(self, **kwargs):
        ctx = _FakeContext()
        self.contexts_created.append(ctx)
        return ctx


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeBrowserType()
        self.stopped = False

    async def stop(self):
        self.stopped = True


async def _cenario_ref_count():
    pool = PlaywrightPool()
    fake_pw = _FakePlaywright()
    pool._playwright = fake_pw
    pool._playwright_loop = asyncio.get_running_loop()

    ctx1 = await pool.get_context(user_data_dir="perfil-x")
    ctx2 = await pool.get_context(user_data_dir="perfil-x")
    assert ctx1 is ctx2, "contexto deve ser reutilizado, não recriado"
    assert pool._ref_count["perfil-x"] == 2
    assert len(fake_pw.chromium.contexts_created) == 1

    await pool.release_context("perfil-x")
    assert pool._ref_count["perfil-x"] == 1
    assert ctx1.closed is False, "não deve fechar enquanto houver referência ativa"

    await pool.release_context("perfil-x")
    assert "perfil-x" not in pool._contexts
    assert "perfil-x" not in pool._ref_count
    assert ctx1.closed is True


def test_get_context_reusa_e_conta_referencias():
    asyncio.run(_cenario_ref_count())


async def _cenario_release_desconhecido():
    pool = PlaywrightPool()
    await pool.release_context("nao-existe")


def test_release_context_chave_desconhecida_nao_falha():
    asyncio.run(_cenario_release_desconhecido())


async def _cenario_cleanup_all_tolera_falha():
    pool = PlaywrightPool()
    pool._contexts = {"a": _FakeContextQueFalhaAoFechar()}
    pool._ref_count = {"a": 1}
    pool._playwright = _FakePlaywright()

    await pool.cleanup_all()

    assert pool._contexts == {}
    assert pool._ref_count == {}
    assert pool._playwright is None


def test_cleanup_all_tolera_falha_ao_fechar_contexto():
    asyncio.run(_cenario_cleanup_all_tolera_falha())


def test_cleanup_playwright_pool_sem_instancia_nao_falha():
    PlaywrightPool._instance = None
    cleanup_playwright_pool()


def test_cleanup_playwright_pool_fecha_playwright_da_instancia():
    PlaywrightPool._instance = None
    try:
        pool = PlaywrightPool.get_instance()
        fake_pw = _FakePlaywright()
        pool._playwright = fake_pw
        pool._contexts = {}
        pool._ref_count = {}

        cleanup_playwright_pool()

        assert fake_pw.stopped is True
        assert pool._playwright is None
    finally:
        PlaywrightPool._instance = None


async def _cenario_context_manager():
    pool = PlaywrightPool.get_instance()
    fake_pw = _FakePlaywright()
    pool._playwright = fake_pw
    pool._playwright_loop = asyncio.get_running_loop()

    async with PlaywrightContextManager(user_data_dir="perfil-y") as ctx:
        assert ctx in fake_pw.chromium.contexts_created
        assert pool._ref_count["perfil-y"] == 1

    assert "perfil-y" not in pool._contexts


def test_context_manager_adquire_e_libera_via_pool():
    PlaywrightPool._instance = None
    try:
        asyncio.run(_cenario_context_manager())
    finally:
        PlaywrightPool._instance = None
