from __future__ import annotations

import pytest

from app.services.api_query_llm_service import ApiQueryLLMService
from app.services.model_router import ModelBackend


class _StubRuntimeConfigService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_backends(self, service_code: str) -> list[ModelBackend]:
        self.calls.append(service_code)
        return [
            ModelBackend(
                name="api-query-db",
                type="openai",
                base_url="https://ark.example.com/api/v3",
                model="doubao-test",
                api_key="ark-test-key",
                chat_path="chat/completions",
                priority=0,
            )
        ]


@pytest.mark.asyncio
async def test_api_query_llm_service_loads_backends_from_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/api-query` 的模型后端必须来自统一运行时配置服务。"""

    stub = _StubRuntimeConfigService()
    monkeypatch.setattr(
        "app.services.api_query_llm_service.get_model_runtime_config_service",
        lambda: stub,
    )
    service = ApiQueryLLMService()

    router = await service._get_router()

    assert stub.calls == ["api.query"]
    assert [backend.name for backend in router._backends] == ["api-query-db"]


@pytest.mark.asyncio
async def test_api_query_llm_service_router_is_lazy_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一服务实例内路由只初始化一次，避免重复读库和重复建客户端。"""

    stub = _StubRuntimeConfigService()
    monkeypatch.setattr(
        "app.services.api_query_llm_service.get_model_runtime_config_service",
        lambda: stub,
    )
    service = ApiQueryLLMService()

    router_one = await service._get_router()
    router_two = await service._get_router()

    assert router_one is router_two
    assert stub.calls == ["api.query"]
