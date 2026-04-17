from __future__ import annotations

import pytest

from app.services.health_quadrant_llm_service import HealthQuadrantLLMService
from app.services.model_router import ModelBackend


class _StubRuntimeConfigService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_backends(self, service_code: str) -> list[ModelBackend]:
        self.calls.append(service_code)
        return [
            ModelBackend(
                name="health-db-primary",
                type="openai",
                base_url="https://ark.example.com/api/v3",
                model="doubao-health",
                api_key="ark-test-key",
                chat_path="chat/completions",
                priority=0,
            ),
            ModelBackend(
                name="health-db-fallback",
                type="ollama",
                base_url="http://localhost:11434",
                model="qwen2.5:7b",
                priority=10,
            ),
        ]


@pytest.mark.asyncio
async def test_health_quadrant_llm_service_loads_backends_from_runtime_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """健康四象限链路应统一读取 MySQL 运行时模型配置。"""

    stub = _StubRuntimeConfigService()
    monkeypatch.setattr(
        "app.services.health_quadrant_llm_service.get_model_runtime_config_service",
        lambda: stub,
    )
    service = HealthQuadrantLLMService()

    router = await service._get_router()

    assert stub.calls == ["health.quadrant"]
    assert [backend.name for backend in router._backends] == ["health-db-primary", "health-db-fallback"]


@pytest.mark.asyncio
async def test_health_quadrant_llm_service_router_is_lazy_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一服务实例内不重复读取配置，防止高频链路出现额外数据库压力。"""

    stub = _StubRuntimeConfigService()
    monkeypatch.setattr(
        "app.services.health_quadrant_llm_service.get_model_runtime_config_service",
        lambda: stub,
    )
    service = HealthQuadrantLLMService()

    router_one = await service._get_router()
    router_two = await service._get_router()

    assert router_one is router_two
    assert stub.calls == ["health.quadrant"]
