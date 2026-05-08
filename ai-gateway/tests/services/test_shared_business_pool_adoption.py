from __future__ import annotations

import pytest

from app.services.api_catalog.business_intents import BusinessIntentCatalogService
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.generic_query_executor import GenericQueryExecutor
from app.services.health_quadrant_repository import HealthQuadrantRepository, HealthQuadrantRepositoryError
from app.services.model_runtime_config_service import ModelRuntimeConfigService
from app.services.ui_catalog_service import UICatalogService


class _FakePool:
    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


@pytest.mark.asyncio
async def test_model_runtime_config_service_requires_injected_pool() -> None:
    """模型运行时配置服务不应在运行期自建业务库连接池。"""

    service = ModelRuntimeConfigService()

    with pytest.raises(RuntimeError, match="AppResources.start"):
        from app.services.model_runtime_config_service import get_model_runtime_config_service

        get_model_runtime_config_service()
    with pytest.raises(Exception, match="业务库连接池未注入"):
        await service._get_pool()


@pytest.mark.asyncio
async def test_registry_source_requires_injected_pool() -> None:
    """注册表访问器不应在运行期自建业务库连接池。"""

    source = ApiCatalogRegistrySource()

    with pytest.raises(Exception, match="业务库连接池未注入"):
        await source._get_pool()


@pytest.mark.asyncio
async def test_business_intent_catalog_requires_injected_pool() -> None:
    """业务意图目录服务不应在运行期自建业务库连接池。"""

    service = BusinessIntentCatalogService()

    with pytest.raises(Exception, match="业务库连接池未注入"):
        await service._get_pool()


@pytest.mark.asyncio
async def test_ui_catalog_service_requires_injected_pool() -> None:
    """UI 目录服务不应在运行期自建业务库连接池。"""

    service = UICatalogService()

    with pytest.raises(Exception, match="业务库连接池未注入"):
        await service._get_pool()


@pytest.mark.asyncio
async def test_generic_query_executor_requires_injected_pool() -> None:
    """通用问数执行器不应在运行期自建业务库连接池。"""

    executor = GenericQueryExecutor()

    with pytest.raises(Exception, match="业务库连接池未注入"):
        await executor._get_pool()


@pytest.mark.asyncio
async def test_health_quadrant_repository_requires_injected_pool() -> None:
    """健康四象限仓储不应在运行期自建业务库连接池。"""

    repository = HealthQuadrantRepository()

    with pytest.raises(HealthQuadrantRepositoryError, match="业务库连接池未注入"):
        await repository._get_pool()
