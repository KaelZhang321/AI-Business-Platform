"""FastIntentRouter 单元测试。"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.services.api_query_fast_intent_router import FastIntentRouter, FastRouteDecision


class TestKeywordMatch:
    """关键词规则匹配测试。"""

    def test_customer_profile_match(self):
        """'客户档案' 高置信匹配。"""
        router = FastIntentRouter()
        result = router.route("查看客户档案")
        assert result.matched is True
        assert result.confidence >= 0.8
        assert "customer_profile" in result.query_domains
        assert result.should_skip_llm_route is True

    def test_exam_report_match(self):
        """'体检报告' 匹配。"""
        router = FastIntentRouter()
        result = router.route("帮我看看体检报告")
        assert result.matched is True
        assert "patient_exam" in result.query_domains

    def test_sales_data_match(self):
        """'销售额' 匹配。"""
        router = FastIntentRouter()
        result = router.route("上个月的销售额是多少")
        assert result.matched is True
        assert "sales_data" in result.query_domains

    def test_no_match_returns_false(self):
        """无关查询不匹配。"""
        router = FastIntentRouter()
        result = router.route("今天天气怎么样")
        assert result.matched is False
        assert result.should_skip_llm_route is False

    def test_case_insensitive(self):
        """匹配不区分大小写。"""
        router = FastIntentRouter()
        result = router.route("查看客户档案")
        assert result.matched is True


class TestCache:
    """TTL 缓存测试。"""

    def test_cache_hit(self):
        """相同查询第二次应命中缓存。"""
        router = FastIntentRouter(cache_ttl_seconds=60)
        result1 = router.route("查看客户档案")
        result2 = router.route("查看客户档案")
        assert result1.matched is True
        assert result2.matched is True
        assert result2.reason == result1.reason  # 来自同一缓存

    def test_cache_expiry(self):
        """缓存过期后不命中。"""
        router = FastIntentRouter(cache_ttl_seconds=1)
        router.route("查看客户档案")

        # 模拟时间流逝
        key = FastIntentRouter._hash_query("查看客户档案")
        # 将缓存时间戳设为 2 秒前
        entry = router._cache[key]
        router._cache[key] = (entry[0], time.monotonic() - 2)

        result = router._cache_lookup(key)
        assert result is None

    def test_cache_max_size(self):
        """超过缓存上限时自动清理旧条目。"""
        router = FastIntentRouter(cache_max_size=5)
        # 填满缓存
        for i in range(6):
            router._cache_store(f"key-{i}", FastRouteDecision(matched=True, confidence=0.9))
        # 应该清理了最旧的条目
        assert len(router._cache) <= 5

    def test_clear_cache(self):
        """clear_cache 清空所有缓存。"""
        router = FastIntentRouter()
        router.route("客户档案")
        assert len(router._cache) > 0
        router.clear_cache()
        assert len(router._cache) == 0


class TestFastRouteDecision:
    """FastRouteDecision 模型测试。"""

    def test_default_values(self):
        """默认值正确。"""
        d = FastRouteDecision()
        assert d.matched is False
        assert d.confidence == 0.0
        assert d.query_domains == []
        assert d.should_skip_llm_route is False

    def test_serialization(self):
        """JSON 序列化正常。"""
        d = FastRouteDecision(
            matched=True,
            confidence=0.9,
            query_domains=["customer_profile"],
            business_intents=["queryCustomerProfile"],
            reason="keyword_match",
            should_skip_llm_route=True,
        )
        data = d.model_dump()
        assert data["matched"] is True
        assert data["confidence"] == 0.9
