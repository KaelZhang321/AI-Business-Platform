from __future__ import annotations

import pytest

from app.services.model_router import ModelBackend
from app.services.smart_meal_llm_service import SmartMealLLMService


class _StubRuntimeConfigService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_backends(self, service_code: str) -> list[ModelBackend]:
        self.calls.append(service_code)
        return [
            ModelBackend(
                name="smart-meal-primary",
                type="openai",
                base_url="https://ark.example.com/api/v3",
                model="doubao-smart-meal",
                api_key="ark-test-key",
                chat_path="chat/completions",
                priority=0,
            )
        ]


@pytest.mark.asyncio
async def test_smart_meal_llm_service_loads_backends_from_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """智能订餐链路应读取 smart.meal 运行时模型配置。"""

    stub = _StubRuntimeConfigService()
    monkeypatch.setattr(
        "app.services.smart_meal_llm_service.get_model_runtime_config_service",
        lambda: stub,
    )
    service = SmartMealLLMService()

    router = await service._get_router()

    assert stub.calls == ["smart.meal"]
    assert [backend.name for backend in router._backends] == ["smart-meal-primary"]
