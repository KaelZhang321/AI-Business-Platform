from __future__ import annotations

from collections.abc import AsyncGenerator

from app.services.model_router import ModelRouter


class LLMService:
    """LLM统一调用服务 — 通过 ModelRouter 路由到可用后端（Ollama / vLLM / OpenAI）"""

    def __init__(self):
        self._router = ModelRouter()

    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        return await self._router.chat(messages, temperature=temperature)

    async def stream_chat(self, messages: list[dict], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        async for chunk in self._router.stream_chat(messages, temperature=temperature):
            yield chunk
