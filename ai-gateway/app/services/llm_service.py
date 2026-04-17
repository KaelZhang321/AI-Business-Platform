from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.services.model_router import ModelRouter
from app.services.model_runtime_config_service import get_model_runtime_config_service

_SERVICE_CODE = "gateway.default"


class LLMService:
    """网关通用 LLM 调用服务。

    功能：
        把通用链路（聊天、意图分类、参数抽取等）的模型路由统一切换到 MySQL 配置，
        避免在不同模块里继续散落 `.env` 级别的模型选择逻辑。
    """

    def __init__(self):
        self._router: ModelRouter | None = None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        *,
        response_format: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        """执行一次非流式模型调用。

        Args:
            messages: OpenAI-compatible 消息数组。
            temperature: 推理温度。
            response_format: 可选结构化输出约束。
            timeout_seconds: 单次请求超时。

        Returns:
            模型返回文本。

        Raises:
            RuntimeError: 当数据库未配置 `gateway.default` 的后端时抛出。
        """
        router = await self._get_router()
        return await router.chat(
            messages,
            temperature=temperature,
            response_format=response_format,
            timeout_seconds=timeout_seconds,
        )

    async def stream_chat(self, messages: list[dict], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """执行一次流式模型调用。"""
        router = await self._get_router()
        async for chunk in router.stream_chat(messages, temperature=temperature):
            yield chunk

    async def close(self) -> None:
        """关闭当前服务持有的 Router 连接。"""
        if self._router is not None:
            await self._router.close()
            self._router = None

    async def _get_router(self) -> ModelRouter:
        """懒加载 Router。

        功能：
            仅在真正触发模型调用时读取数据库配置，减少“仅实例化服务对象”造成的无效
            DB 访问。
        """
        if self._router is None:
            backends = await get_model_runtime_config_service().get_backends(_SERVICE_CODE)
            self._router = ModelRouter(backends=backends)
        return self._router
