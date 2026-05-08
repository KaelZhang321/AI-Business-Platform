"""Stage 2 混合召回器。

功能：
    保留现有 Milvus 分层召回价值，同时把 Neo4j 子图扩散与 Graph Cache 接到第二阶段：

    1. Milvus 先负责定位锚点接口
    2. Redis Graph Cache 优先拦住热点请求
    3. Neo4j 用 `COMPANION` 做范围剪枝，并回捞真实字段路径
    4. 若图缓存正在被其它请求回填，当前请求优先等待缓存，避免并发打爆图库
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.config import settings
from app.services.api_catalog.graph_cache import GraphCacheService
from app.services.api_catalog.graph_models import ApiCatalogSubgraphResult
from app.services.api_catalog.graph_repository import GraphRepository, Neo4jGraphRepository
from app.services.api_catalog.retriever import ApiCatalogRetriever
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchFilters, ApiCatalogSearchResult

logger = logging.getLogger(__name__)

_SINGLEFLIGHT_WAIT_ATTEMPTS = 6
_SINGLEFLIGHT_POLL_INTERVAL_SECONDS = 0.05

AnchorSearcher = Callable[..., Awaitable[list[ApiCatalogSearchResult]]]
EntryLoader = Callable[[list[str]], Awaitable[list[ApiCatalogEntry]]]


@dataclass(slots=True)
class ApiCatalogHybridSearchResult:
    """混合召回结果。

    功能：
        兼容当前 workflow 仍然主要消费 `candidates` 的事实，同时把 Stage 2 真正需要的
        `subgraph` 暴露出来，供后续 Wave 3/4 直接接到 planner / validator / runtime context。
    """

    anchors: list[ApiCatalogSearchResult]
    candidates: list[ApiCatalogSearchResult]
    subgraph: ApiCatalogSubgraphResult


class ApiCatalogHybridRetriever(ApiCatalogRetriever):
    """Milvus + Neo4j + Redis 的 Stage 2 混合召回器。"""

    def __init__(
        self,
        *,
        graph_repository: GraphRepository | None = None,
        graph_cache: GraphCacheService | None = None,
        anchor_searcher: AnchorSearcher | None = None,
        entry_loader: EntryLoader | None = None,
    ) -> None:
        super().__init__()
        self._graph_repository = graph_repository or Neo4jGraphRepository()
        self._graph_cache = graph_cache or GraphCacheService()
        self._anchor_searcher = anchor_searcher
        self._entry_loader = entry_loader
        self._subgraph_results_by_trace_id: dict[str, ApiCatalogSubgraphResult] = {}

    async def search_subgraph_stratified(
        self,
        query: str,
        *,
        domains: list[str],
        top_k: int = 3,
        per_domain_top_k: int | None = None,
        score_threshold: float | None = None,
        filters: ApiCatalogSearchFilters | dict[str, list[str]] | None = None,
        trace_id: str | None = None,
    ) -> ApiCatalogHybridSearchResult:
        """执行带子图扩散的分层召回。"""

        anchors = await self._search_anchors(
            query,
            domains=domains,
            top_k=top_k,
            per_domain_top_k=per_domain_top_k,
            score_threshold=score_threshold,
            filters=filters,
            trace_id=trace_id,
        )
        anchor_api_ids = [result.entry.id for result in anchors[: settings.api_catalog_graph_anchor_top_k]]
        related_domains = domains if settings.api_catalog_graph_related_domain_enabled else []
        subgraph = await self._resolve_subgraph(anchor_api_ids, related_domains=related_domains)
        support_results = await self._load_support_results(subgraph.support_api_ids, anchors=anchors)
        candidates = _merge_candidate_results(anchors, support_results)
        if trace_id:
            self._subgraph_results_by_trace_id[trace_id] = subgraph
        return ApiCatalogHybridSearchResult(anchors=anchors, candidates=candidates, subgraph=subgraph)

    async def search_stratified(
        self,
        query: str,
        *,
        domains: list[str],
        top_k: int = 3,
        per_domain_top_k: int | None = None,
        score_threshold: float | None = None,
        filters: ApiCatalogSearchFilters | dict[str, list[str]] | None = None,
        trace_id: str | None = None,
    ) -> list[ApiCatalogSearchResult]:
        """兼容旧接口，仅返回候选列表。"""

        result = await self.search_subgraph_stratified(
            query,
            domains=domains,
            top_k=top_k,
            per_domain_top_k=per_domain_top_k,
            score_threshold=score_threshold,
            filters=filters,
            trace_id=trace_id,
        )
        return result.candidates

    def get_subgraph_result(self, trace_id: str) -> ApiCatalogSubgraphResult | None:
        """按 trace_id 读取最近一次 Stage 2 子图结果。"""

        return self._subgraph_results_by_trace_id.get(trace_id)

    async def _search_anchors(
        self,
        query: str,
        *,
        domains: list[str],
        top_k: int,
        per_domain_top_k: int | None,
        score_threshold: float | None,
        filters: ApiCatalogSearchFilters | dict[str, list[str]] | None,
        trace_id: str | None,
    ) -> list[ApiCatalogSearchResult]:
        """先走现有 Milvus 分层召回，保住已经验证过的锚点价值。"""

        if self._anchor_searcher is not None:
            return await self._anchor_searcher(
                query,
                domains=domains,
                top_k=top_k,
                per_domain_top_k=per_domain_top_k,
                score_threshold=score_threshold,
                filters=filters,
                trace_id=trace_id,
            )
        return await super().search_stratified(
            query,
            domains=domains,
            top_k=top_k,
            per_domain_top_k=per_domain_top_k,
            score_threshold=score_threshold,
            filters=filters,
            trace_id=trace_id,
        )

    async def _resolve_subgraph(
        self,
        anchor_api_ids: list[str],
        *,
        related_domains: list[str],
    ) -> ApiCatalogSubgraphResult:
        """解析锚点对应的局部子图。"""

        if not anchor_api_ids:
            return ApiCatalogSubgraphResult(anchor_api_ids=[])
        if not settings.api_catalog_graph_enabled:
            return ApiCatalogSubgraphResult(
                anchor_api_ids=anchor_api_ids,
                graph_degraded=True,
                degraded_reason="graph_disabled",
            )

        cache_key = _build_subgraph_cache_lookup_key(
            anchor_api_ids=anchor_api_ids,
            max_hops=settings.api_catalog_graph_expand_hops,
            support_limit=settings.api_catalog_graph_support_limit,
            related_domains=related_domains,
        )
        cache_hit = await self._graph_cache.get_subgraph(cache_key)
        if cache_hit.hit and cache_hit.subgraph is not None:
            return cache_hit.subgraph

        if await self._graph_cache.acquire_singleflight(cache_key):
            try:
                subgraph = await self._graph_repository.fetch_subgraph(
                    anchor_api_ids=anchor_api_ids,
                    max_hops=settings.api_catalog_graph_expand_hops,
                    support_limit=settings.api_catalog_graph_support_limit,
                    related_domains=related_domains,
                    field_degree_cutoff=settings.api_catalog_graph_field_degree_cutoff,
                )
                if not subgraph.graph_degraded:
                    await self._graph_cache.set_subgraph(
                        cache_key,
                        subgraph,
                        index_api_ids=[*anchor_api_ids, *subgraph.support_api_ids],
                    )
                return subgraph
            finally:
                await self._graph_cache.release_singleflight(cache_key)

        # 未拿到单飞锁的请求优先等缓存，而不是继续并发回源打图库。
        return await self._wait_for_inflight_subgraph(cache_key, anchor_api_ids)

    async def _wait_for_inflight_subgraph(
        self,
        cache_key: str,
        anchor_api_ids: list[str],
    ) -> ApiCatalogSubgraphResult:
        """等待其它请求把热点子图回填到缓存。"""

        for _ in range(_SINGLEFLIGHT_WAIT_ATTEMPTS):
            await asyncio.sleep(_SINGLEFLIGHT_POLL_INTERVAL_SECONDS)
            cache_hit = await self._graph_cache.get_subgraph(cache_key)
            if cache_hit.hit and cache_hit.subgraph is not None:
                return cache_hit.subgraph

        return ApiCatalogSubgraphResult(
            anchor_api_ids=anchor_api_ids,
            graph_degraded=True,
            degraded_reason="graph_singleflight_wait_timeout",
        )

    async def _load_support_results(
        self,
        support_api_ids: list[str],
        *,
        anchors: list[ApiCatalogSearchResult],
    ) -> list[ApiCatalogSearchResult]:
        """把 support API id 列表回填成完整检索结果。"""

        anchor_ids = {anchor.entry.id for anchor in anchors}
        filtered_support_ids = [api_id for api_id in support_api_ids if api_id not in anchor_ids]
        if not filtered_support_ids:
            return []

        entries = await self._load_entries(filtered_support_ids)
        if not entries:
            return []

        score_floor = min((anchor.score for anchor in anchors), default=0.5)
        results: list[ApiCatalogSearchResult] = []
        for offset, entry in enumerate(entries, start=1):
            # support API 不应抢走锚点排序；这里给它们一个低于最弱锚点的保守分数，只保留“可参与规划”的资格。
            support_score = max(score_floor - 0.05 * offset, 0.01)
            results.append(ApiCatalogSearchResult(entry=entry, score=support_score))
        return results

    async def _load_entries(self, api_ids: list[str]) -> list[ApiCatalogEntry]:
        """按需加载 support API 的完整目录记录。"""

        if self._entry_loader is not None:
            return await self._entry_loader(api_ids)
        return await self.get_many_by_ids(api_ids)


def _build_subgraph_cache_lookup_key(
    *,
    anchor_api_ids: list[str],
    max_hops: int,
    support_limit: int,
    related_domains: list[str],
) -> str:
    """构造子图缓存查找 key。

    功能：
        Stage 2 子图并不只由锚点决定，还会受 hop、域约束和 support_limit 影响。这里把这些护栏
        全部编进摘要 key，避免不同查询视图互相串缓存。
    """

    payload = {
        "anchor_api_ids": sorted(set(anchor_api_ids)),
        "max_hops": max_hops,
        "support_limit": support_limit,
        "related_domains": sorted(set(related_domains)),
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"subgraph:{digest}"


def _merge_candidate_results(
    anchors: list[ApiCatalogSearchResult],
    support_results: list[ApiCatalogSearchResult],
) -> list[ApiCatalogSearchResult]:
    """合并锚点与 support API，保持锚点优先级。"""

    merged: list[ApiCatalogSearchResult] = []
    seen_api_ids: set[str] = set()
    for result in [*anchors, *support_results]:
        api_id = result.entry.id
        if api_id in seen_api_ids:
            continue
        seen_api_ids.add(api_id)
        merged.append(result)
    return merged
