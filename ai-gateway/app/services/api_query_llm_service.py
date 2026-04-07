"""`/api-query` 专用 LLM 服务。

功能：
    将 `api_query` 的 Stage-2 / Stage-3 / Stage-5 统一绑定到 Volcengine Ark，
    避免这些高结构化链路继续漂浮在网关默认模型路由上，导致同一请求在不同环境下
    落到不同模型、输出稳定性失控。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.core.config import settings
from app.services.model_router import ModelBackend, ModelRouter

_ARK_CHAT_COMPLETIONS_PATH = "chat/completions"


class ApiQueryLLMService:
    """`/api-query` 专用的 Ark 模型调用服务。

    功能：
        为 `api_query` 提供一条独立于全局默认路由的模型链路，确保第二阶段路由、
        第三阶段 Planner 和第五阶段 Renderer 使用同一模型族，减少结构化输出漂移。

    Edge Cases:
        - 若缺少 `ARK_API_KEY`，会在首次真正发起模型请求时抛出清晰配置错误
        - 若 `ARK_API_BASE` 带有 `/api/v3` 前缀，也会通过相对路径拼接命中正确接口
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
        """执行一次 `/api-query` 专用的非流式模型调用。

        Args:
            messages: OpenAI-compatible 消息数组。
            temperature: 推理温度。`api_query` 通常会传入 0.0 以收敛结构化输出。
            response_format: 结构化输出约束，例如 `{"type": "json_object"}`。
            timeout_seconds: 单次请求超时时间。

        Returns:
            模型返回的文本内容。

        Raises:
            RuntimeError: 当 Ark 关键配置缺失时抛出，阻止 `/api-query` 误落到其他模型。
        """
        return await self._get_router().chat(
            messages,
            temperature=temperature,
            response_format=response_format,
            timeout_seconds=timeout_seconds,
        )

    async def stream_chat(self, messages: list[dict[str, Any]], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """执行一次 `/api-query` 专用的流式模型调用。"""
        async for chunk in self._get_router().stream_chat(messages, temperature=temperature):
            yield chunk

    async def close(self) -> None:
        """关闭 Ark 客户端连接，避免测试或热更新场景遗留长连接。"""
        if self._router is not None:
            await self._router.close()
            self._router = None

    def _get_router(self) -> ModelRouter:
        """懒加载 Ark Router。

        功能：
            `/api-query` 的 direct 快路与规则渲染路径未必真的会触发 LLM。
            这里延迟初始化，避免“只是实例化服务”就因为缺少 Ark 配置把非 LLM 分支一并拖死。
        """
        if self._router is None:
            self._router = ModelRouter(backends=[self._build_backend()])
        return self._router

    @staticmethod
    def _build_backend() -> ModelBackend:
        """构建 `/api-query` 专用的 Ark 后端。

        功能：
            Ark 的 OpenAI-compatible 基础路径通常已经包含 `/api/v3`，因此不能继续复用
            通用 `/v1/chat/completions` 的绝对路径，否则会把基础路径前缀吞掉。

        Returns:
            只包含一个 Ark 后端的 `ModelBackend`。

        Raises:
            RuntimeError: 当 Ark 配置不完整时抛出，提示调用方修复环境变量。
        """
        if not settings.ark_api_key:
            raise RuntimeError("api_query 未配置 ARK_API_KEY，无法调用 Volcengine Ark。")
        if not settings.ark_api_base:
            raise RuntimeError("api_query 未配置 ARK_API_BASE，无法调用 Volcengine Ark。")
        if not settings.ark_default_model:
            raise RuntimeError("api_query 未配置 ARK_DEFAULT_MODEL，无法调用 Volcengine Ark。")

        return ModelBackend(
            name="api-query-ark",
            type="openai",
            base_url=settings.ark_api_base,
            model=settings.ark_default_model,
            api_key=settings.ark_api_key,
            chat_path=_ARK_CHAT_COMPLETIONS_PATH,
            priority=0,
        )
