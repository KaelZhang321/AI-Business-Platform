"""
缓存失效监听器 — 监听 RabbitMQ cache.invalidation 队列，
收到知识库变更事件后清除本地 RAG 结果缓存 + Milvus 语义缓存。
"""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika

from app.core.config import settings

logger = logging.getLogger(__name__)

# 本地 RAG 结果缓存（简易内存缓存，可升级为 Redis）
_rag_cache: dict[str, object] = {}

# 语义缓存服务实例（由 main.py lifespan 注入）
_semantic_cache_service = None


def set_semantic_cache_service(service) -> None:
    """注入语义缓存服务实例。"""
    global _semantic_cache_service
    _semantic_cache_service = service


def get_rag_cache() -> dict[str, object]:
    return _rag_cache


def invalidate_rag_cache(category: str | None = None) -> int:
    """清除 RAG 缓存，返回清除的条目数。"""
    if category:
        keys = [k for k in _rag_cache if k.startswith(f"rag:{category}:")]
        for k in keys:
            _rag_cache.pop(k, None)
        return len(keys)
    count = len(_rag_cache)
    _rag_cache.clear()
    return count


def invalidate_semantic_cache(kb_version: int | None = None) -> int:
    """清除 Milvus 语义缓存。"""
    if _semantic_cache_service is None:
        return 0
    return _semantic_cache_service.invalidate(kb_version)


async def start_cache_invalidation_listener() -> None:
    """启动 RabbitMQ 消费者，监听 cache.invalidation 队列。"""
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        queue = await channel.declare_queue("cache.invalidation", durable=True)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        body = json.loads(message.body.decode())
                        event_type = body.get("type", "")
                        action = body.get("action", "")
                        category = body.get("category", "")

                        if event_type == "knowledge":
                            # 1. 清除内存 RAG 缓存
                            cleared_rag = invalidate_rag_cache(category or None)
                            # 2. 清除 Milvus 语义缓存
                            kb_version = body.get("kb_version")
                            cleared_sc = invalidate_semantic_cache(kb_version)
                            logger.info(
                                "缓存失效: type=%s, action=%s, category=%s, "
                                "rag_cleared=%d, semantic_cache_cleared=%d",
                                event_type, action, category,
                                cleared_rag, cleared_sc,
                            )
                    except Exception as exc:
                        logger.warning("处理缓存失效消息失败: %s", exc)
    except Exception as exc:
        logger.warning("缓存失效监听器启动失败（RabbitMQ 不可用）: %s", exc)
