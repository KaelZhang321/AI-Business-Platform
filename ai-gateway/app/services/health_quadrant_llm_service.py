"""健康四象限专用 LLM 服务（MySQL 配置驱动）。"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from app.services.model_router import ModelRouter
from app.services.model_runtime_config_service import get_model_runtime_config_service

_SERVICE_CODE = "health.quadrant"
logger = logging.getLogger(__name__)


class HealthQuadrantLLMService:
    """健康四象限专用模型调用服务。

    功能：
        终检意见抽取等高结构化链路的模型选择统一收敛到 MySQL，不再在代码中硬编码
        Ark/Ollama 组合策略，减少多环境维护成本。
    """

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
        """执行一次非流式模型调用。"""
        router = await self._get_router()
        logger.info(
            "health quadrant llm chat start service_code=%s message_count=%s temperature=%s response_format=%s timeout_seconds=%s",
            _SERVICE_CODE,
            len(messages),
            temperature,
            response_format,
            timeout_seconds,
        )
        result = await router.chat(
            messages,
            temperature=temperature,
            response_format=response_format,
            timeout_seconds=timeout_seconds,
        )
        logger.info(
            "health quadrant llm chat completed service_code=%s content_length=%s",
            _SERVICE_CODE,
            len(result),
        )
        return result

    async def stream_chat(self, messages: list[dict[str, Any]], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """执行一次流式模型调用。"""
        router = await self._get_router()
        async for chunk in router.stream_chat(messages, temperature=temperature):
            yield chunk

    async def close(self) -> None:
        """关闭模型路由底层客户端连接。"""
        if self._router is not None:
            await self._router.close()
            self._router = None

    async def _get_router(self) -> ModelRouter:
        """懒加载健康四象限专属 Router。

        功能：
            当线上出现“后端不可用”时，第一时间需要确认当前进程到底拿到了哪组模型配置。
            这里在初始化阶段输出后端摘要（名称/类型/地址/模型/优先级），帮助快速比对
            MySQL 配置与进程实际生效配置是否一致。
        """
        if self._router is None:
            backends = await get_model_runtime_config_service().get_backends(_SERVICE_CODE)
            logger.info(
                "health quadrant llm router initialized service_code=%s backend_count=%s backends=%s",
                _SERVICE_CODE,
                len(backends),
                [
                    {
                        "name": backend.name,
                        "type": backend.type,
                        "base_url": backend.base_url,
                        "chat_path": backend.chat_path,
                        "model": backend.model,
                        "priority": backend.priority,
                    }
                    for backend in backends
                ],
            )
            self._router = ModelRouter(backends=backends)
        return self._router
