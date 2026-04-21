from __future__ import annotations

import pytest

from app.services.model_router import ModelBackend


@pytest.mark.asyncio
async def test_model_backend_client_disables_env_proxy_by_default() -> None:
    """模型路由默认不继承系统代理，避免本地/容器脏代理导致外部 LLM 连接失败。"""

    backend = ModelBackend(
        name="ark-primary",
        type="openai",
        base_url="https://ark.example.com/api/v3",
        model="doubao-test",
        chat_path="chat/completions",
    )
    client = backend.client()
    try:
        assert client._trust_env is False
    finally:
        await backend.close()
