from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.models.schemas import IntentType, SubIntentType, IntentResult
from app.services.llm_service import LLMService


class IntentClassifier:
    """意图分类服务 - LLM优先 + 关键词兜底，支持一级+二级意图。"""

    SYSTEM_PROMPT = """
你是一名企业AI助理，需要根据用户问题判断所属意图，并返回JSON：
{"intent": "chat|knowledge|query|task", "sub_intent": "<二级意图>", "confidence": 0-1}

一级意图定义：
- chat: 闲聊、问候、无特定任务
- knowledge: 需要从知识库/文档检索
- query: 需要查询结构化数据、生成SQL、统计
- task: 查询或操作待办、流程、审批

二级意图定义：
- knowledge下：knowledge_policy(制度/流程/政策咨询)、knowledge_product(产品/服务咨询)、knowledge_medical(医学/健康咨询)
- query下：data_customer(客户查询/统计)、data_sales(销售/业绩查询)、data_operation(运营查询/统计)
- task下：task_query(查询待办)、task_create(创建任务)、task_approve(审批操作)
- 无法判断二级意图时返回 general
""".strip()

    KEYWORD_RULES: dict[IntentType, list[str]] = {
        IntentType.QUERY: ["查询", "统计", "多少", "报表", "数据", "sql"],
        IntentType.KNOWLEDGE: ["文档", "知识", "搜索", "查找资料", "政策"],
        IntentType.TASK: ["待办", "任务", "审批", "工单", "提醒"],
    }

    SUB_INTENT_KEYWORDS: dict[SubIntentType, list[str]] = {
        # knowledge
        SubIntentType.KNOWLEDGE_POLICY: ["制度", "政策", "流程", "规定", "规范"],
        SubIntentType.KNOWLEDGE_PRODUCT: ["产品", "服务", "功能", "方案"],
        SubIntentType.KNOWLEDGE_MEDICAL: ["医学", "健康", "诊断", "用药", "治疗"],
        # query
        SubIntentType.DATA_CUSTOMER: ["客户", "用户数", "会员"],
        SubIntentType.DATA_SALES: ["销售", "业绩", "营收", "订单"],
        SubIntentType.DATA_OPERATION: ["运营", "活跃", "留存", "转化"],
        # task
        SubIntentType.TASK_QUERY: ["待办", "任务列表", "有哪些任务"],
        SubIntentType.TASK_CREATE: ["创建任务", "新建工单", "发起"],
        SubIntentType.TASK_APPROVE: ["审批", "审核", "批准", "驳回"],
    }

    def __init__(self, llm_service: LLMService | None = None, confidence_threshold: float | None = None):
        self._llm = llm_service or LLMService()
        self._threshold = confidence_threshold or settings.intent_confidence_threshold
        self._logger = logging.getLogger(__name__)

    async def classify(self, message: str, context: dict | None = None) -> IntentResult:
        """对用户消息进行一级+二级意图分类，返回 IntentResult。"""
        result = await self._llm_intent(message, context)
        if result:
            return result
        return self._keyword_fallback(message)

    async def _llm_intent(self, message: str, context: dict | None) -> IntentResult | None:
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
            sub_intent_value = str(data.get("sub_intent", "general")).lower()
            confidence = float(data.get("confidence", 0))
            if confidence < self._threshold:
                return None

            intent = self._match_intent(intent_value)
            if not intent:
                return None

            sub_intent = self._match_sub_intent(sub_intent_value)
            return IntentResult(intent=intent, sub_intent=sub_intent, confidence=confidence)
        except Exception as exc:  # pragma: no cover - resilience
            self._logger.warning("LLM intent classification fallback: %s", exc)
        return None

    def _keyword_fallback(self, message: str) -> IntentResult:
        intent = IntentType.CHAT
        for candidate, keywords in self.KEYWORD_RULES.items():
            if any(kw in message for kw in keywords):
                intent = candidate
                break

        sub_intent = SubIntentType.GENERAL
        for candidate, keywords in self.SUB_INTENT_KEYWORDS.items():
            if any(kw in message for kw in keywords):
                sub_intent = candidate
                break

        return IntentResult(intent=intent, sub_intent=sub_intent, confidence=0.5)

    @staticmethod
    def _match_intent(value: str) -> IntentType | None:
        for intent in IntentType:
            if intent.value == value:
                return intent
        return None

    @staticmethod
    def _match_sub_intent(value: str) -> SubIntentType:
        for sub in SubIntentType:
            if sub.value == value:
                return sub
        return SubIntentType.GENERAL
