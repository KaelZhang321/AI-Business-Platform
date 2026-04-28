from __future__ import annotations

import pytest

from app.core import resources as resources_module
from app.core.resources import AppResources
from app.services.model_runtime_config_service import get_model_runtime_config_service
from app.services.api_catalog.business_intents import get_business_intent_catalog_service


class _FakePool:
    def __init__(self) -> None:
        self.close_calls = 0
        self.wait_closed_calls = 0

    def close(self) -> None:
        self.close_calls += 1

    async def wait_closed(self) -> None:
        self.wait_closed_calls += 1


class _FakeRAGService:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_app_resources_owns_single_business_mysql_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """应用级资源容器必须只创建并关闭一次业务库连接池。"""

    fake_pool = _FakePool()
    created: list[dict[str, int]] = []

    async def fake_create_business_mysql_pool(*, minsize: int, maxsize: int):  # noqa: ANN202
        created.append({"minsize": minsize, "maxsize": maxsize})
        return fake_pool

    monkeypatch.setattr(resources_module, "create_business_mysql_pool", fake_create_business_mysql_pool)
    monkeypatch.setattr(resources_module, "RAGService", _FakeRAGService)

    app_resources = AppResources()
    await app_resources.start()

    assert created == [{"minsize": 1, "maxsize": 10}]
    assert app_resources.model_runtime_config_service._pool is fake_pool
    assert app_resources.prompt_template_repository._pool is fake_pool
    assert app_resources.ui_catalog_service._pool is fake_pool
    assert get_model_runtime_config_service() is app_resources.model_runtime_config_service
    assert get_business_intent_catalog_service() is app_resources.business_intent_catalog_service

    await app_resources.close()

    assert fake_pool.close_calls == 1
    assert fake_pool.wait_closed_calls == 1


@pytest.mark.asyncio
async def test_injected_business_pool_is_not_closed_by_repository() -> None:
    """被注入的共享 pool 只能由 AppResources 关闭，repository close 只清理自有资源。"""

    from app.services.prompt_template_repository import PromptTemplateRepository

    fake_pool = _FakePool()
    repository = PromptTemplateRepository(pool=fake_pool)  # type: ignore[arg-type]

    await repository.close()

    assert fake_pool.close_calls == 0
    assert fake_pool.wait_closed_calls == 0


@pytest.mark.asyncio
async def test_health_quadrant_repository_uses_injected_business_pool() -> None:
    """健康四象限结果仓储复用应用级业务库 pool，不再单独建池。"""

    from app.services.health_quadrant_repository import HealthQuadrantRepository

    fake_pool = _FakePool()
    repository = HealthQuadrantRepository(pool=fake_pool)  # type: ignore[arg-type]

    assert await repository._get_pool() is fake_pool
    await repository.close()

    assert fake_pool.close_calls == 0
    assert fake_pool.wait_closed_calls == 0


@pytest.mark.asyncio
async def test_health_quadrant_mysql_pools_borrows_business_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """多数据源管理器借用业务库 pool 时，只能释放自己创建的 ODS pool。"""

    from app.services import health_quadrant_mysql_pools as pools_module
    from app.services.health_quadrant_mysql_pools import HealthQuadrantMySQLPools

    shared_business_pool = _FakePool()
    owned_ods_pool = _FakePool()
    created: list[dict[str, object]] = []

    async def fake_create_pool(**kwargs):  # noqa: ANN202
        created.append(kwargs)
        return owned_ods_pool

    monkeypatch.setattr(pools_module.aiomysql, "create_pool", fake_create_pool)

    pools = HealthQuadrantMySQLPools(business_pool=shared_business_pool)  # type: ignore[arg-type]

    assert await pools.get_business_pool() is shared_business_pool
    assert await pools.get_ods_pool() is owned_ods_pool

    await pools.close()

    assert len(created) == 1
    assert shared_business_pool.close_calls == 0
    assert shared_business_pool.wait_closed_calls == 0
    assert owned_ods_pool.close_calls == 1
    assert owned_ods_pool.wait_closed_calls == 1
