"""GraphRAG Redis cache seam。

功能：
    为 Stage 2 子图缓存、Stage 3 校验缓存和字段绑定缓存提供统一的读写入口。
    这里先固定缓存 key 结构、序列化协议和降级行为，后续再逐步补齐 singleflight
    和热点预热等更重的在线优化。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.services.api_catalog.graph_models import (
    ApiCatalogSubgraphResult,
    GraphCacheHitResult,
    GraphCacheInvalidationRequest,
    GraphValidationCacheEntry,
)

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "api_catalog:graph"


class GraphCacheService:
    """GraphRAG 缓存服务。

    功能：
        统一处理 GraphRAG 的 Redis 访问和降级，避免调用方自行拼 key、序列化和吞异常。
    """

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        enabled: bool | None = None,
        default_ttl_seconds: int | None = None,
        singleflight_ttl_seconds: int | None = None,
    ) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._enabled = settings.api_catalog_graph_cache_enabled if enabled is None else enabled
        self._default_ttl_seconds = default_ttl_seconds or settings.api_catalog_graph_cache_ttl_seconds
        self._singleflight_ttl_seconds = (
            singleflight_ttl_seconds or settings.api_catalog_graph_cache_singleflight_ttl_seconds
        )
        self._client: aioredis.Redis | None = None

    def _get_client(self) -> aioredis.Redis:
        """懒加载 Redis client。"""
        if self._client is None:
            self._client = aioredis.from_url(self._redis_url, encoding="utf-8", decode_responses=True)
        return self._client

    def build_cache_key(self, scope: str, key: str) -> str:
        """构造 GraphRAG 缓存 key。"""
        return f"{_CACHE_PREFIX}:{scope}:{key}"

    def build_singleflight_key(self, key: str) -> str:
        """构造缓存单飞锁 key。"""
        return f"{_CACHE_PREFIX}:singleflight:{key}"

    async def get_subgraph(self, key: str) -> GraphCacheHitResult:
        """读取子图缓存。"""
        cache_key = self.build_cache_key("subgraph", key)
        if not self._enabled:
            return GraphCacheHitResult(key=cache_key, hit=False)
        try:
            raw_payload = await self._get_client().get(cache_key)
            if not raw_payload:
                return GraphCacheHitResult(key=cache_key, hit=False)
            return GraphCacheHitResult(
                key=cache_key,
                hit=True,
                subgraph=ApiCatalogSubgraphResult.model_validate_json(raw_payload),
            )
        except Exception as exc:  # pragma: no cover - 依赖外部 Redis
            logger.warning("graph cache get_subgraph degraded: key=%s error=%s", cache_key, exc)
            return GraphCacheHitResult(key=cache_key, hit=False)

    async def set_subgraph(
        self,
        key: str,
        subgraph: ApiCatalogSubgraphResult,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """写入子图缓存。"""
        if not self._enabled:
            return
        cache_key = self.build_cache_key("subgraph", key)
        try:
            await self._get_client().set(cache_key, subgraph.model_dump_json(), ex=ttl_seconds or self._default_ttl_seconds)
        except Exception as exc:  # pragma: no cover - 依赖外部 Redis
            logger.warning("graph cache set_subgraph skipped: key=%s error=%s", cache_key, exc)

    async def get_validation(self, key: str) -> GraphValidationCacheEntry | None:
        """读取图校验缓存。"""
        cache_key = self.build_cache_key("validate", key)
        if not self._enabled:
            return None
        try:
            raw_payload = await self._get_client().get(cache_key)
            if not raw_payload:
                return None
            return GraphValidationCacheEntry.model_validate_json(raw_payload)
        except Exception as exc:  # pragma: no cover - 依赖外部 Redis
            logger.warning("graph cache get_validation degraded: key=%s error=%s", cache_key, exc)
            return None

    async def set_validation(
        self,
        key: str,
        entry: GraphValidationCacheEntry,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """写入图校验缓存。"""
        if not self._enabled:
            return
        cache_key = self.build_cache_key("validate", key)
        try:
            await self._get_client().set(cache_key, entry.model_dump_json(), ex=ttl_seconds or self._default_ttl_seconds)
        except Exception as exc:  # pragma: no cover - 依赖外部 Redis
            logger.warning("graph cache set_validation skipped: key=%s error=%s", cache_key, exc)

    async def set_field_binding_summary(
        self,
        key: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """写入字段绑定摘要缓存。"""
        if not self._enabled:
            return
        cache_key = self.build_cache_key("field_binding", key)
        try:
            await self._get_client().set(cache_key, json.dumps(payload, ensure_ascii=False), ex=ttl_seconds or self._default_ttl_seconds)
        except Exception as exc:  # pragma: no cover - 依赖外部 Redis
            logger.warning("graph cache set_field_binding_summary skipped: key=%s error=%s", cache_key, exc)

    async def invalidate(self, request: GraphCacheInvalidationRequest) -> int:
        """按受影响 API 定向删除缓存。"""
        if not self._enabled or not request.impacted_api_ids:
            return 0

        keys_to_delete: list[str] = []
        for api_id in request.impacted_api_ids:
            for scope in request.scopes:
                keys_to_delete.append(self.build_cache_key(scope, api_id))

        try:
            return int(await self._get_client().delete(*keys_to_delete))
        except Exception as exc:  # pragma: no cover - 依赖外部 Redis
            logger.warning("graph cache invalidate degraded: api_ids=%s error=%s", request.impacted_api_ids, exc)
            return 0

    async def acquire_singleflight(self, key: str) -> bool:
        """尝试获取缓存单飞锁。

        功能：
            后续 Stage 2 未命中回源时，需要用最小互斥避免同一热点 anchor 同时打爆图仓储。
        """
        if not self._enabled:
            return False
        lock_key = self.build_singleflight_key(key)
        try:
            return bool(
                await self._get_client().set(lock_key, "1", ex=self._singleflight_ttl_seconds, nx=True)
            )
        except Exception as exc:  # pragma: no cover - 依赖外部 Redis
            logger.warning("graph cache singleflight degraded: key=%s error=%s", lock_key, exc)
            return False

    async def release_singleflight(self, key: str) -> None:
        """释放缓存单飞锁。"""
        if not self._enabled:
            return
        lock_key = self.build_singleflight_key(key)
        try:
            await self._get_client().delete(lock_key)
        except Exception as exc:  # pragma: no cover - 依赖外部 Redis
            logger.warning("graph cache singleflight release skipped: key=%s error=%s", lock_key, exc)

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

