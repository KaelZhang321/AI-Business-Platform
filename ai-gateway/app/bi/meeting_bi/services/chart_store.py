"""
图表数据缓存 — 基于 Redis。

key 格式：``chart:{chart_id}``  (12 位随机 hex)
TTL：86400 秒（24 小时）

依赖 ``settings.redis_url`` 配置。
"""
from __future__ import annotations

import json
import logging
import uuid

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover - not installed in test env
    aioredis = None  # type: ignore[assignment]

from app.bi.meeting_bi.schemas.common import BIChartConfig
from app.core.config import reveal_secret, settings

logger = logging.getLogger(__name__)

TTL_SECONDS = 86_400  # 24 hours
_KEY_PREFIX = "chart:"


def _make_key(chart_id: str) -> str:
    return f"{_KEY_PREFIX}{chart_id}"


def _get_redis() -> aioredis.Redis:
    """每次调用返回一个连接（使用连接池，由 redis.asyncio 自动管理）。"""
    return aioredis.from_url(reveal_secret(settings.redis_url), decode_responses=True)


async def save_chart(chart: BIChartConfig) -> str:
    """序列化 BIChartConfig 存入 Redis，返回 chart_id。"""
    chart_id = uuid.uuid4().hex[:12]
    payload = json.dumps(chart.model_dump(), ensure_ascii=False)
    try:
        async with _get_redis() as redis:
            await redis.setex(_make_key(chart_id), TTL_SECONDS, payload)
        logger.debug("Chart saved: chart_id=%s", chart_id)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.warning("Failed to save chart to Redis: %s", exc)
    return chart_id


async def get_chart(chart_id: str) -> dict | None:
    """从 Redis 获取图表数据，不存在或已过期返回 None。"""
    try:
        async with _get_redis() as redis:
            raw = await redis.get(_make_key(chart_id))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.warning("Failed to get chart from Redis: %s", exc)
        return None
