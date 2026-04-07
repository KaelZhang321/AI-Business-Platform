from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.api_query_llm_service import ApiQueryLLMService


def test_api_query_llm_service_builds_ark_backend_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/api-query` 必须固定读取 Ark 配置，不能继续借道全局 openai_* 变量。"""
    monkeypatch.setattr(settings, "ark_api_key", "ark-test-key")
    monkeypatch.setattr(settings, "ark_api_base", "https://ark.example.com/api/v3")
    monkeypatch.setattr(settings, "ark_default_model", "doubao-test")

    service = ApiQueryLLMService()
    backend = service._build_backend()

    assert backend.name == "api-query-ark"
    assert backend.base_url == "https://ark.example.com/api/v3"
    assert backend.model == "doubao-test"
    assert backend.api_key == "ark-test-key"
    assert backend.chat_path == "chat/completions"


def test_api_query_llm_service_requires_ark_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺少 Ark Key 时直接阻断，是为了防止 `/api-query` 静默落回其他模型。"""
    monkeypatch.setattr(settings, "ark_api_key", "")
    monkeypatch.setattr(settings, "ark_api_base", "https://ark.example.com/api/v3")
    monkeypatch.setattr(settings, "ark_default_model", "doubao-test")

    service = ApiQueryLLMService()

    with pytest.raises(RuntimeError, match="ARK_API_KEY"):
        service._build_backend()
