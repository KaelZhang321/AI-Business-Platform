from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict

from app.core.config import settings
from app.models.schemas import IntentType, SubIntentType, IntentResult
from app.services.llm_service import LLMService


class IntentClassifier:
    """统一聊天入口的意图分类器。

    功能：
        优先使用 LLM 做一级/二级意图识别，在模型不可用或置信度不足时退回关键词规则，
        保证聊天主链路在弱依赖场景下仍然可用。

    返回值约束：
        始终返回 `IntentResult`，不会把 LLM 解析异常直接抛给上层工作流。

    Edge Cases:
        - LLM 返回脏 JSON 或置信度过低时，自动回退关键词规则
        - 二级意图无法识别时，统一回落到 `general`
    """

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
- query下：data_customer(客户查询/统计)、data_sales(销售/业绩查询)、data_operation(运营查询/统计)、data_meeting_bi(会议BI问数，如报名、签到、大区成交、ROI、方案情报)
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
        SubIntentType.DATA_MEETING_BI: [
            "会议", "报名", "签到", "已抵达", "到院", "大区", "成交金额", "收款金额", "投资回报率", "roi",
            "方案情报", "客户画像", "报名客户", "签到率", "目标达成", "运营数据",
        ],
        SubIntentType.DATA_CUSTOMER: ["客户", "用户数", "会员"],
        SubIntentType.DATA_SALES: ["销售", "业绩", "营收", "订单"],
        SubIntentType.DATA_OPERATION: ["运营", "活跃", "留存", "转化"],
        # task
        SubIntentType.TASK_QUERY: ["待办", "任务列表", "有哪些任务"],
        SubIntentType.TASK_CREATE: ["创建任务", "新建工单", "发起"],
        SubIntentType.TASK_APPROVE: ["审批", "审核", "批准", "驳回"],
    }

    def __init__(
        self,
        llm_service: LLMService | None = None,
        confidence_threshold: float | None = None,
        *,
        cache_ttl_seconds: int = 300,
        cache_max_size: int = 512,
    ):
        self._llm = llm_service or LLMService()
        self._threshold = confidence_threshold or settings.intent_confidence_threshold
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache_max_size = cache_max_size
        self._cache: OrderedDict[str, tuple[float, IntentResult]] = OrderedDict()
        self._logger = logging.getLogger(__name__)

    async def classify(self, message: str, context: dict | None = None) -> IntentResult:
        """对用户消息执行一级 + 二级意图分类。

        Args:
            message: 用户原始提问文本。
            context: 上游透传的上下文，例如用户身份或会话补充信息。

        Returns:
            一个稳定的 `IntentResult`，供工作流节点做路由分发。

        Edge Cases:
            - LLM 分类失败时，不中断请求，而是立即转入关键词兜底
        """
        keyword_result = self._keyword_fast_path(message)
        if keyword_result:
            keyword_result.confidence = 0.8
            return keyword_result

        cache_key = self._cache_key(message, context)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        result = await self._llm_intent(message, context)
        if result:
            self._set_cached(cache_key, result)
            return result
        return self._keyword_fallback(message)

    def _keyword_fast_path(self, message: str) -> IntentResult | None:
        """Return only when keywords unambiguously point to one primary intent."""

        matched_intents = [
            candidate for candidate, keywords in self.KEYWORD_RULES.items() if any(kw in message for kw in keywords)
        ]
        if len(matched_intents) != 1:
            return None

        intent = matched_intents[0]
        matched_sub_intents = [
            candidate for candidate, keywords in self.SUB_INTENT_KEYWORDS.items() if any(kw in message for kw in keywords)
        ]
        sub_intent = matched_sub_intents[0] if len(matched_sub_intents) == 1 else SubIntentType.GENERAL
        return IntentResult(intent=intent, sub_intent=sub_intent, confidence=0.8)

    async def _llm_intent(self, message: str, context: dict | None) -> IntentResult | None:
        """使用 LLM 做高精度意图识别。

        功能：
            让复杂自然语言先经过模型判定，减少纯关键词在多义句上的误判。

        Returns:
            命中且置信度达标时返回 `IntentResult`，否则返回 `None` 触发兜底逻辑。
        """
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
            # 低置信度结果不进入业务链路，宁可走保守兜底也不把错路由继续放大。
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
        """使用关键词执行保守兜底分类。

        功能：
            当模型不可用或返回异常时，保障查询、知识、待办等主干能力至少有一个
            粗粒度可用路由，不让整条聊天链路硬失败。
        """
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

    def _get_cached(self, cache_key: str) -> IntentResult | None:
        item = self._cache.get(cache_key)
        if not item:
            return None
        created_at, result = item
        if time.monotonic() - created_at > self._cache_ttl_seconds:
            self._cache.pop(cache_key, None)
            return None
        self._cache.move_to_end(cache_key)
        return result

    def _set_cached(self, cache_key: str, result: IntentResult) -> None:
        self._cache[cache_key] = (time.monotonic(), result)
        self._cache.move_to_end(cache_key)
        while len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)

    @staticmethod
    def _cache_key(message: str, context: dict | None) -> str:
        payload = {"message": message.strip().lower(), "context": context or {}}
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

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
