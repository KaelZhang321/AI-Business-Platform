from __future__ import annotations

import pytest

from app.core.error_codes import BusinessError
from app.models.schemas import TranscriptExtractData
from app.services.model_router import ModelBackend
from app.services.prompt_template_repository import PromptTemplateRecord
from app.services.transcript_extract_service import TranscriptExtractService


class _StubPromptRepository:
    def __init__(self, template: PromptTemplateRecord | None) -> None:
        self.template = template
        self.calls: list[str] = []

    async def get_by_service_code(self, service_code: str) -> PromptTemplateRecord | None:
        self.calls.append(service_code)
        return self.template

    async def close(self) -> None:
        return None


class _StubRuntimeConfigService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_backends(self, service_code: str) -> list[ModelBackend]:
        self.calls.append(service_code)
        return [
            ModelBackend(
                name="transcript-extract-db",
                type="openai",
                base_url="https://ark.example.com/api/v3",
                model="doubao-test",
                api_key="ark-test-key",
                chat_path="chat/completions",
                priority=0,
            )
        ]


class _StubRouter:
    def __init__(self, raw_content: str) -> None:
        self.raw_content = raw_content
        self.calls: list[dict[str, object]] = []

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        *,
        response_format: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "response_format": response_format,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.raw_content

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_transcript_extract_service_returns_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """服务应完成 taskCode 路由、Prompt 渲染与 JSON 结果解析。"""

    repository = _StubPromptRepository(
        PromptTemplateRecord(
            service_code="transcript.extract.task1",
            system_prompt="system prompt",
            user_prompt="请分析 transcript：{{ transcript }}",
            enabled=True,
        )
    )
    runtime_config = _StubRuntimeConfigService()
    stub_router = _StubRouter('{"summary":"ok","riskLevel":"medium"}')
    monkeypatch.setattr(
        "app.services.transcript_extract_service.get_model_runtime_config_service",
        lambda: runtime_config,
    )
    monkeypatch.setattr(
        "app.services.transcript_extract_service.ModelRouter",
        lambda backends: stub_router,
    )
    service = TranscriptExtractService(prompt_repository=repository)

    result = await service.extract(task_code="task1", transcript="客户说最近睡眠差")

    assert result == TranscriptExtractData(
        task_code="task1",
        service_code="transcript.extract.task1",
        result={"summary": "ok", "riskLevel": "medium"},
    )
    assert repository.calls == ["transcript.extract.task1"]
    assert runtime_config.calls == ["transcript.extract.task1"]
    assert stub_router.calls[0]["temperature"] == 0
    assert stub_router.calls[0]["response_format"] == {"type": "json_object"}
    messages = stub_router.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "system prompt"
    assert "客户说最近睡眠差" in messages[1]["content"]


@pytest.mark.asyncio
async def test_transcript_extract_service_rejects_unsupported_task_code() -> None:
    """未知任务必须在进入模型调用前被拦截。"""

    service = TranscriptExtractService(prompt_repository=_StubPromptRepository(None))

    with pytest.raises(BusinessError, match="unsupported taskCode"):
        await service.extract(task_code="unknown-task", transcript="demo")


@pytest.mark.asyncio
async def test_transcript_extract_service_rejects_invalid_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """模型返回非对象 JSON 时必须失败，避免前端拿到伪成功响应。"""

    repository = _StubPromptRepository(
        PromptTemplateRecord(
            service_code="transcript.extract.task2",
            system_prompt="system prompt",
            user_prompt="请分析 transcript：{{ transcript }}",
            enabled=True,
        )
    )
    runtime_config = _StubRuntimeConfigService()
    stub_router = _StubRouter("not-json")
    monkeypatch.setattr(
        "app.services.transcript_extract_service.get_model_runtime_config_service",
        lambda: runtime_config,
    )
    monkeypatch.setattr(
        "app.services.transcript_extract_service.ModelRouter",
        lambda backends: stub_router,
    )
    service = TranscriptExtractService(prompt_repository=repository)

    with pytest.raises(BusinessError, match="模型未返回合法 JSON 对象"):
        await service.extract(task_code="task2", transcript="demo")
