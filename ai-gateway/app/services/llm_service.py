from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings


class LLMService:
    """LLM统一调用服务 - 通过 Ollama HTTP API 调用本地模型"""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120)

    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        response = await self._client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def stream_chat(self, messages: list[dict], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        async with self._client.stream("POST", "/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    chunk = json.loads(line[len("data: "):])
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield delta
*** End File
