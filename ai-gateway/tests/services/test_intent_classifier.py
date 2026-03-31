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

    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        del messages, temperature
        return self.payload


@pytest.mark.asyncio
async def test_keyword_fallback_marks_meeting_bi_queries() -> None:
    classifier = IntentClassifier(llm_service=FailingLLMService())

    result = await classifier.classify("帮我统计本次会议报名人数和签到率")

    assert result.intent is IntentType.QUERY
    assert result.sub_intent is SubIntentType.DATA_MEETING_BI
    assert result.confidence == 0.5


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
