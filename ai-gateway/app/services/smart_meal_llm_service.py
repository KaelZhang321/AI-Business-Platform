"""智能订餐专用 LLM 服务（MySQL 配置驱动）。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.services.model_router import ModelRouter
from app.services.model_runtime_config_service import get_model_runtime_config_service

_SERVICE_CODE = "smart.meal"


class SmartMealLLMService:
    """智能订餐专用模型调用服务。"""

    def __init__(self) -> None:
        self._router: ModelRouter | None = None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        *,
        response_format: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        """执行一次智能订餐专用非流式调用。"""
        router = await self._get_router()
        return await router.chat(
            messages,
            temperature=temperature,
            response_format=response_format,
            timeout_seconds=timeout_seconds,
        )

    async def stream_chat(self, messages: list[dict[str, Any]], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """执行一次智能订餐专用流式调用。"""
        router = await self._get_router()
        async for chunk in router.stream_chat(messages, temperature=temperature):
            yield chunk

    async def close(self) -> None:
        """关闭模型路由底层客户端连接。"""
        if self._router is not None:
            await self._router.close()
            self._router = None

    async def _get_router(self) -> ModelRouter:
        """懒加载智能订餐专属 Router。"""
        if self._router is None:
            backends = await get_model_runtime_config_service().get_backends(_SERVICE_CODE)
            self._router = ModelRouter(backends=backends)
        return self._router
