from collections.abc import AsyncGenerator


class LLMService:
    """LLM统一调用服务 - 支持Ollama本地模型和外部API"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.base_url = base_url
        self.model = model

    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """同步对话"""
        # TODO: 通过LangChain ChatOllama调用
        return "LLM服务开发中"

    async def stream_chat(self, messages: list[dict], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """流式对话"""
        # TODO: 流式调用Ollama/外部API
        yield "LLM流式服务开发中"
