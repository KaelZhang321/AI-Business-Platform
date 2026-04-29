from __future__ import annotations

import pytest

from app.models.schemas import IntentType, SubIntentType
from app.services.intent_classifier import IntentClassifier


class FailingLLMService:
    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        del messages, temperature
        raise RuntimeError("llm unavailable")


class StaticLLMService:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls = 0

    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        del messages, temperature
        self.calls += 1
        return self.payload


@pytest.mark.asyncio
async def test_keyword_fallback_marks_meeting_bi_queries() -> None:
    classifier = IntentClassifier(llm_service=FailingLLMService())

    result = await classifier.classify("帮我统计本次会议报名人数和签到率")

    assert result.intent is IntentType.QUERY
    assert result.sub_intent is SubIntentType.DATA_MEETING_BI
    assert result.confidence == 0.8


@pytest.mark.asyncio
async def test_llm_result_keeps_meeting_bi_sub_intent() -> None:
    classifier = IntentClassifier(
        llm_service=StaticLLMService(
            '{"intent":"query","sub_intent":"data_meeting_bi","confidence":0.92}'
        )
    )

    result = await classifier.classify("分析会议大区成交金额")

    assert result.intent is IntentType.QUERY
    assert result.sub_intent is SubIntentType.DATA_MEETING_BI
    assert result.confidence == 0.92


@pytest.mark.asyncio
async def test_keyword_fast_path_skips_llm_for_clear_queries() -> None:
    llm = StaticLLMService('{"intent":"chat","sub_intent":"general","confidence":0.99}')
    classifier = IntentClassifier(llm_service=llm)

    result = await classifier.classify("帮我查询客户数据")

    assert result.intent is IntentType.QUERY
    assert result.confidence == 0.8
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_llm_result_is_cached_for_same_message_and_context() -> None:
    llm = StaticLLMService('{"intent":"chat","sub_intent":"general","confidence":0.92}')
    classifier = IntentClassifier(llm_service=llm)

    first = await classifier.classify("你好", {"user": "u1"})
    second = await classifier.classify("你好", {"user": "u1"})

    assert first.intent is IntentType.CHAT
    assert second.intent is IntentType.CHAT
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_ambiguous_keyword_message_uses_llm_instead_of_fast_path() -> None:
    llm = StaticLLMService('{"intent":"knowledge","sub_intent":"knowledge_policy","confidence":0.91}')
    classifier = IntentClassifier(llm_service=llm)

    result = await classifier.classify("请帮我查询政策数据")

    assert result.intent is IntentType.KNOWLEDGE
    assert result.sub_intent is SubIntentType.KNOWLEDGE_POLICY
    assert llm.calls == 1
