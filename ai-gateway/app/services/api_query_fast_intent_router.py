"""FastIntentRouter — 规则优先 + TTL 缓存的快速意图路由。

在调用 LLM route_query 之前，先尝试通过规则和缓存判断意图，
高置信命中时跳过 LLM 调用，将意图识别延迟从 1-30s 降低到 <10ms。
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FastRouteDecision(BaseModel):
    """快速路由决策结果。"""

    matched: bool = Field(False, description="是否成功匹配")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="匹配置信度")
    query_domains: list[str] = Field(default_factory=list, description="命中的业务域")
    business_intents: list[str] = Field(default_factory=list, description="命中的业务意图编码")
    selected_api_id: str | None = Field(None, description="直接命中的接口ID")
    reason: str = Field("", description="匹配原因")
    should_skip_llm_route: bool = Field(False, description="是否应跳过 LLM route")


# 业务关键词规则表 — 高频场景
_KEYWORD_RULES: list[dict[str, Any]] = [
    {
        "keywords": ["客户档案", "客户信息", "客户资料", "客户详情", "查看客户"],
        "query_domains": ["customer_profile"],
        "business_intents": ["queryCustomerProfile"],
        "confidence": 0.9,
    },
    {
        "keywords": ["体检报告", "体检结果", "检查报告", "体检单"],
        "query_domains": ["patient_exam"],
        "business_intents": ["queryExamReport"],
        "confidence": 0.85,
    },
    {
        "keywords": ["销售数据", "销售额", "销售统计", "营收", "业绩"],
        "query_domains": ["sales_data"],
        "business_intents": ["querySalesData"],
        "confidence": 0.85,
    },
    {
        "keywords": ["预约", "预约记录", "预约列表", "预约信息"],
        "query_domains": ["reservation"],
        "business_intents": ["queryReservation"],
        "confidence": 0.85,
    },
    {
        "keywords": ["合同", "合同列表", "合同信息", "签约"],
        "query_domains": ["contract"],
        "business_intents": ["queryContract"],
        "confidence": 0.85,
    },
    {
        "keywords": ["报名", "报名记录", "报名数据", "报名统计"],
        "query_domains": ["registration"],
        "business_intents": ["queryRegistration"],
        "confidence": 0.8,
    },
]


class FastIntentRouter:
    """规则优先 + TTL 缓存的快速意图路由器。

    识别优先级：
    1. 业务关键词和 synonym 规则匹配
    2. 进程内 TTL 意图缓存（基于 query hash）
    3. 未命中则返回 matched=False，由调用方决定是否走 LLM
    """

    def __init__(self, cache_ttl_seconds: int = 300, cache_max_size: int = 1000) -> None:
        self._cache_ttl = cache_ttl_seconds
        self._cache_max_size = cache_max_size
        self._cache: dict[str, tuple[FastRouteDecision, float]] = {}

    def route(self, query: str, context: dict[str, Any] | None = None) -> FastRouteDecision:
        """执行快速意图路由。

        Args:
            query: 用户自然语言输入
            context: 可选的页面上下文（page, module, selectedEntity 等）

        Returns:
            FastRouteDecision 路由决策
        """
        # Step 1: 检查缓存
        cache_key = self._hash_query(query)
        cached = self._cache_lookup(cache_key)
        if cached is not None:
            logger.debug("FastIntentRouter cache hit: %s", cache_key[:8])
            return cached

        # Step 2: 关键词规则匹配
        decision = self._keyword_match(query)

        # Step 3: 高置信命中时写入缓存
        if decision.matched and decision.confidence >= 0.8:
            decision.should_skip_llm_route = True
            self._cache_store(cache_key, decision)
            logger.info(
                "FastIntentRouter matched: domains=%s confidence=%.2f reason=%s",
                decision.query_domains,
                decision.confidence,
                decision.reason,
            )

        return decision

    def _keyword_match(self, query: str) -> FastRouteDecision:
        """基于关键词规则表进行匹配。"""
        query_lower = query.lower().strip()

        for rule in _KEYWORD_RULES:
            for keyword in rule["keywords"]:
                if keyword in query_lower:
                    return FastRouteDecision(
                        matched=True,
                        confidence=rule["confidence"],
                        query_domains=rule["query_domains"],
                        business_intents=rule["business_intents"],
                        reason=f"keyword_match: '{keyword}'",
                        should_skip_llm_route=True,
                    )

        return FastRouteDecision(matched=False, reason="no_keyword_match")

    def _cache_lookup(self, key: str) -> FastRouteDecision | None:
        """查找缓存，过期则删除。"""
        entry = self._cache.get(key)
        if entry is None:
            return None
        decision, timestamp = entry
        if time.monotonic() - timestamp > self._cache_ttl:
            del self._cache[key]
            return None
        return decision

    def _cache_store(self, key: str, decision: FastRouteDecision) -> None:
        """写入缓存，超过上限时清理最旧条目。"""
        if len(self._cache) >= self._cache_max_size:
            # 清理最旧的 20% 条目
            sorted_keys = sorted(self._cache, key=lambda k: self._cache[k][1])
            for old_key in sorted_keys[: len(sorted_keys) // 5]:
                del self._cache[old_key]
        self._cache[key] = (decision, time.monotonic())

    def clear_cache(self) -> None:
        """清空缓存。"""
        self._cache.clear()

    @staticmethod
    def _hash_query(query: str) -> str:
        """基于 query 内容生成缓存 key。"""
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()
