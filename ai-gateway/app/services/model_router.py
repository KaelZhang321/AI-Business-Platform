"""ModelRouter — 多后端模型路由，支持 Ollama / vLLM / OpenAI API 切换与 fallback。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelBackend:
    """模型后端配置。"""

    name: str
    type: str  # ollama | vllm | openai
    base_url: str
    model: str
    priority: int = 0  # 越小优先级越高
    enabled: bool = True
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120)
        return self._client


class ModelRouter:
    """按优先级选择后端，支持 fallback。"""

    def __init__(self, backends: list[ModelBackend] | None = None):
        if backends:
            self._backends = sorted(backends, key=lambda b: b.priority)
        else:
            self._backends = self._default_backends()

    @staticmethod
    def _default_backends() -> list[ModelBackend]:
        backends = [
            ModelBackend(
                name="ollama-local",
                type="ollama",
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                priority=0,
            ),
        ]
        if settings.openai_api_key:
            backends.append(
                ModelBackend(
                    name="openai-api",
                    type="openai",
                    base_url=settings.openai_base_url or "https://api.openai.com",
                    model="gpt-4o-mini",
                    priority=10,
                )
            )
        return backends

    def _enabled_backends(self) -> list[ModelBackend]:
        return [b for b in self._backends if b.enabled]

    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        for backend in self._enabled_backends():
            try:
                return await self._call_chat(backend, messages, temperature)
            except Exception as exc:
                logger.warning("Backend '%s' failed: %s, trying next...", backend.name, exc)
        raise RuntimeError("所有模型后端均不可用")

    async def stream_chat(self, messages: list[dict], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        last_error: Exception | None = None
        for backend in self._enabled_backends():
            try:
                async for chunk in self._call_stream(backend, messages, temperature):
                    yield chunk
                return
            except Exception as exc:
                logger.warning("Backend '%s' stream failed: %s, trying next...", backend.name, exc)
                last_error = exc
        raise RuntimeError(f"所有模型后端均不可用: {last_error}")

    async def _call_chat(self, backend: ModelBackend, messages: list[dict], temperature: float) -> str:
        client = backend.client()
        headers = self._build_headers(backend)
        payload = {
            "model": backend.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if backend.type == "ollama":
            payload["options"] = {"temperature": temperature}
            del payload["temperature"]

        resp = await client.post("/v1/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def _call_stream(
        self, backend: ModelBackend, messages: list[dict], temperature: float
    ) -> AsyncGenerator[str, None]:
        client = backend.client()
        headers = self._build_headers(backend)
        payload = {
            "model": backend.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }
        if backend.type == "ollama":
            payload["options"] = {"temperature": temperature}
            del payload["temperature"]

        async with client.stream("POST", "/v1/chat/completions", json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                raw = line[len("data: "):]
                if raw.strip() == "[DONE]":
                    break
                chunk = json.loads(raw)
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta

    @staticmethod
    def _build_headers(backend: ModelBackend) -> dict[str, str]:
        headers: dict[str, str] = {}
        if backend.type == "openai" and settings.openai_api_key:
            headers["Authorization"] = f"Bearer {settings.openai_api_key}"
        return headers
