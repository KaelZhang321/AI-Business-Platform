from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.services.model_router import ModelRouter


class LLMService:
    """LLM统一调用服务 — 通过 ModelRouter 路由到可用后端（Ollama / vLLM / OpenAI）"""

    def __init__(self):
        self._router = ModelRouter()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        *,
        response_format: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        """执行一次非流式模型调用。

        功能：
            为业务层提供统一的模型访问入口，并把结构化输出、超时等治理能力
            透传给底层 Router，避免每条链路各自拼接兼容参数。

        Args:
            messages: OpenAI-compatible 消息数组。
            temperature: 推理温度。
            response_format: 可选的结构化输出约束。
            timeout_seconds: 单次请求超时时间。

        Returns:
            模型返回的纯文本内容。

        Edge Cases:
            如果当前后端不支持 `response_format`，异常会向上抛，由调用方决定是否降级重试。
        """
        return await self._router.chat(
            messages,
            temperature=temperature,
            response_format=response_format,
            timeout_seconds=timeout_seconds,
        )

    async def stream_chat(self, messages: list[dict], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        async for chunk in self._router.stream_chat(messages, temperature=temperature):
            yield chunk
