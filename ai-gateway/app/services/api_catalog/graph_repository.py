"""Neo4j 访问 seam。

功能：
    统一封装 GraphRAG 访问图数据库时的连接、降级和返回契约。
    Phase 04-01 的目标不是把 Stage 2/3/同步逻辑一次写完，而是先固定住
    “图层对外长什么样”，让后续每一波实现都能在同一边界内推进。

返回值约束：
    - 任何 Neo4j 故障都必须折叠成可降级结果，而不是把底层异常直接泄漏给 workflow
    - `fetch_subgraph()` 返回 `ApiCatalogSubgraphResult`
    - `sync_api_subgraph()` 返回 `GraphSyncImpactResult`
"""

from __future__ import annotations

import logging
from typing import Iterable

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import settings
from app.services.api_catalog.graph_models import (
    ApiCatalogSubgraphResult,
    GraphSyncImpactResult,
    NormalizedFieldBinding,
)

logger = logging.getLogger(__name__)


class GraphRepositoryError(RuntimeError):
    """图仓储统一异常基类。"""


class GraphRepository:
    """GraphRAG 仓储接口。

    功能：
        对上游 service 暴露稳定方法集合，避免 workflow / retriever / sync 直接依赖 Neo4j driver。
    """

    async def verify_connectivity(self) -> bool:
        """检查图仓储可用性。"""
        raise NotImplementedError

    async def fetch_subgraph(
        self,
        *,
        anchor_api_ids: Iterable[str],
        max_hops: int,
        support_limit: int,
        related_domains: list[str] | None = None,
        field_degree_cutoff: int | None = None,
    ) -> ApiCatalogSubgraphResult:
        """提取候选子图。"""
        raise NotImplementedError

    async def sync_api_subgraph(
        self,
        *,
        api_id: str,
        bindings: list[NormalizedFieldBinding],
        sync_run_id: str,
        metadata_version: str | None = None,
    ) -> GraphSyncImpactResult:
        """同步单 API 子图。"""
        raise NotImplementedError

    async def close(self) -> None:
        """释放仓储占用的外部资源。"""
        raise NotImplementedError


class Neo4jGraphRepository(GraphRepository):
    """基于 Neo4j 的图仓储默认实现。

    功能：
        先固化连接和降级行为；真正的 Stage 2 Cypher 与同步事务逻辑会在后续计划中补齐。
    """

    def __init__(
        self,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._uri = uri or settings.neo4j_uri
        self._user = user or settings.neo4j_user
        self._password = password or settings.neo4j_password
        self._enabled = settings.api_catalog_graph_enabled if enabled is None else enabled
        self._driver: AsyncDriver | None = None

    def _get_driver(self) -> AsyncDriver:
        """懒加载 Neo4j driver。

        功能：
            GraphRAG 允许按 feature flag 灰度发布；只有图功能真正启用时才建立连接，
            避免“配置已发版但图数据库尚未就绪”时把整个网关拖死。
        """
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(self._uri, auth=(self._user, self._password))
        return self._driver

    async def verify_connectivity(self) -> bool:
        """验证 Neo4j 可达性。"""
        if not self._enabled:
            return False
        try:
            await self._get_driver().verify_connectivity()
            return True
        except Exception as exc:  # pragma: no cover - 依赖外部图数据库
            logger.warning("graph repository connectivity check failed: %s", exc)
            return False

    async def fetch_subgraph(
        self,
        *,
        anchor_api_ids: Iterable[str],
        max_hops: int,
        support_limit: int,
        related_domains: list[str] | None = None,
        field_degree_cutoff: int | None = None,
    ) -> ApiCatalogSubgraphResult:
        """返回子图提取的降级安全结果。

        功能：
            Phase 04-01 先固定对外结果结构；真正的单次 Cypher 子图提取会在 04-04 写入。
        """
        anchor_list = list(anchor_api_ids)
        if not self._enabled:
            return ApiCatalogSubgraphResult(
                anchor_api_ids=anchor_list,
                graph_degraded=True,
                degraded_reason="graph_disabled",
            )

        try:
            # 这里先执行一次最轻量的连通性兜底，确保后续接入真实 Cypher 前，
            # 调用方已经可以按统一返回结构处理“图可用 / 图降级”两种状态。
            await self._get_driver().verify_connectivity()
            _ = max_hops, support_limit, related_domains, field_degree_cutoff
            return ApiCatalogSubgraphResult(anchor_api_ids=anchor_list)
        except Exception as exc:  # pragma: no cover - 依赖外部图数据库
            logger.warning("graph subgraph fetch degraded: anchors=%s error=%s", anchor_list, exc)
            return ApiCatalogSubgraphResult(
                anchor_api_ids=anchor_list,
                graph_degraded=True,
                degraded_reason=str(exc),
            )

    async def sync_api_subgraph(
        self,
        *,
        api_id: str,
        bindings: list[NormalizedFieldBinding],
        sync_run_id: str,
        metadata_version: str | None = None,
    ) -> GraphSyncImpactResult:
        """返回同步入口的占位契约。

        功能：
            让 indexer / graph sync service 可以先依赖稳定接口，再在 04-03 中补齐事务细节。
        """
        _ = bindings
        if not self._enabled:
            return GraphSyncImpactResult(
                api_id=api_id,
                impacted_api_ids=[api_id],
                sync_run_id=sync_run_id,
                metadata_version=metadata_version,
            )
        try:
            await self._get_driver().verify_connectivity()
            return GraphSyncImpactResult(
                api_id=api_id,
                impacted_api_ids=[api_id],
                sync_run_id=sync_run_id,
                metadata_version=metadata_version,
            )
        except Exception as exc:  # pragma: no cover - 依赖外部图数据库
            raise GraphRepositoryError(f"graph sync prerequisite failed for api_id={api_id}: {exc}") from exc

    async def close(self) -> None:
        """关闭 Neo4j driver。"""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

