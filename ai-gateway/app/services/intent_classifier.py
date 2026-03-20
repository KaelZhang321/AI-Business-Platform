from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.models.schemas import IntentType
from app.services.llm_service import LLMService


class IntentClassifier:
    """意图分类服务 - LLM优先 + 关键词兜底。"""

    SYSTEM_PROMPT = """
你是一名企业AI助理，需要根据用户问题判断所属意图，并返回JSON：
{"intent": "chat|knowledge|query|task", "confidence": 0-1}

定义：
- chat: 闲聊、无特定任务
- knowledge: 需要从知识库/文档检索
- query: 需要查询结构化数据、生成SQL、统计
- task: 查询或操作待办、流程、审批
""".strip()

    KEYWORD_RULES: dict[IntentType, list[str]] = {
        IntentType.QUERY: ["查询", "统计", "多少", "报表", "数据", "sql"],
        IntentType.KNOWLEDGE: ["文档", "知识", "搜索", "查找资料", "政策"],
        IntentType.TASK: ["待办", "任务", "审批", "工单", "提醒"],
    }

    def __init__(self, llm_service: LLMService | None = None, confidence_threshold: float | None = None):
        self._llm = llm_service or LLMService()
        self._threshold = confidence_threshold or settings.intent_confidence_threshold
        self._logger = logging.getLogger(__name__)

    async def classify(self, message: str, context: dict | None = None) -> IntentType:
        """对用户消息进行意图分类"""
        intent = await self._llm_intent(message, context)
        if intent:
            return intent
        return self._keyword_fallback(message)

    async def _llm_intent(self, message: str, context: dict | None) -> IntentType | None:
        payload = {
            "message": message,
            "context": context or {},
        }
        try:
            response = await self._llm.chat(
                [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.1,
            )
            data = json.loads(response)
            intent_value = str(data.get("intent", "")).lower()
            confidence = float(data.get("confidence", 0))
            if confidence < self._threshold:
                return None
            for intent in IntentType:
                if intent.value == intent_value:
                    return intent
        except Exception as exc:  # pragma: no cover - resilience
            self._logger.warning("LLM intent classification fallback: %s", exc)
        return None

    def _keyword_fallback(self, message: str) -> IntentType:
        for intent, keywords in self.KEYWORD_RULES.items():
            if any(keyword in message for keyword in keywords):
                return intent
        return IntentType.CHAT
