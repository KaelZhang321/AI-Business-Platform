from __future__ import annotations

import pytest

from app.services.llm_service import LLMService
from app.services.model_router import ModelBackend


class _StubRuntimeConfigService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_backends(self, service_code: str) -> list[ModelBackend]:
        self.calls.append(service_code)
        return [
            ModelBackend(
                name="gateway-db-primary",
                type="openai",
                base_url="https://api.example.com/v1",
                model="gpt-test",
                api_key="key-test",
                chat_path="chat/completions",
                priority=0,
            )
        ]


@pytest.mark.asyncio
async def test_llm_service_loads_backends_from_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """通用 LLM 服务应从统一运行时配置中心读取后端，不再直接依赖本地环境变量。"""

    stub = _StubRuntimeConfigService()
    monkeypatch.setattr(
        "app.services.llm_service.get_model_runtime_config_service",
        lambda: stub,
    )
    service = LLMService()

    router = await service._get_router()

    assert stub.calls == ["gateway.default"]
    assert [backend.name for backend in router._backends] == ["gateway-db-primary"]
