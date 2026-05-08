from __future__ import annotations

import asyncio

import pytest

import app.services.api_catalog.hybrid_retriever as hybrid_module
from app.core.config import settings
from app.services.api_catalog.graph_models import ApiCatalogSubgraphResult, GraphCacheHitResult, GraphFieldPath
from app.services.api_catalog.graph_repository import Neo4jGraphRepository
from app.services.api_catalog.hybrid_retriever import (
    ApiCatalogHybridRetriever,
    _build_subgraph_cache_lookup_key,
)
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult


class _FakeReadTransaction:
    pass


class _FakeReadSession:
    def __init__(self, repository: "_SequencedSubgraphRepository") -> None:
        self._repository = repository

    async def __aenter__(self) -> "_FakeReadSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def execute_read(self, func, *args):
        return await func(_FakeReadTransaction(), *args)


class _FakeReadDriver:
    def __init__(self, repository: "_SequencedSubgraphRepository") -> None:
        self._repository = repository

    def session(self, *args, **kwargs) -> _FakeReadSession:
        return _FakeReadSession(self._repository)

    async def verify_connectivity(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _SequencedSubgraphRepository(Neo4jGraphRepository):
    def __init__(self, results: list[ApiCatalogSubgraphResult]) -> None:
        super().__init__(enabled=True)
        self.results = list(results)
        self.query_order: list[str] = []
        self._driver = _FakeReadDriver(self)

    async def _run_subgraph_query(self, tx, *, query, params, anchor_api_ids, support_limit) -> ApiCatalogSubgraphResult:
        self.query_order.append("companion" if "COMPANION" in query else "raw")
        return self.results.pop(0)


class _FakeGraphCache:
    def __init__(self) -> None:
        self.subgraphs: dict[str, ApiCatalogSubgraphResult] = {}
        self.indexed_api_ids: dict[str, list[str]] = {}
        self.lock_held: set[str] = set()
        self.set_calls = 0

    async def get_subgraph(self, key: str) -> GraphCacheHitResult:
        subgraph = self.subgraphs.get(key)
        return GraphCacheHitResult(key=key, hit=subgraph is not None, subgraph=subgraph)

    async def set_subgraph(
        self,
        key: str,
        subgraph: ApiCatalogSubgraphResult,
        *,
        ttl_seconds: int | None = None,
        index_api_ids: list[str] | None = None,
    ) -> None:
        self.set_calls += 1
        self.subgraphs[key] = subgraph
        self.indexed_api_ids[key] = index_api_ids or []

    async def acquire_singleflight(self, key: str) -> bool:
        if key in self.lock_held:
            return False
        self.lock_held.add(key)
        return True

    async def release_singleflight(self, key: str) -> None:
        self.lock_held.discard(key)


class _RecordingGraphRepository:
    def __init__(self, subgraph: ApiCatalogSubgraphResult) -> None:
        self.subgraph = subgraph
        self.calls: list[dict] = []

    async def fetch_subgraph(
        self,
        *,
        anchor_api_ids,
        max_hops,
        support_limit,
        related_domains=None,
        field_degree_cutoff=None,
    ) -> ApiCatalogSubgraphResult:
        self.calls.append(
            {
                "anchor_api_ids": list(anchor_api_ids),
                "max_hops": max_hops,
                "support_limit": support_limit,
                "related_domains": list(related_domains or []),
                "field_degree_cutoff": field_degree_cutoff,
            }
        )
        return self.subgraph


class _BlockingGraphRepository(_RecordingGraphRepository):
    def __init__(self, subgraph: ApiCatalogSubgraphResult) -> None:
        super().__init__(subgraph)
        self.started = asyncio.Event()
        self.unblock = asyncio.Event()

    async def fetch_subgraph(self, **kwargs) -> ApiCatalogSubgraphResult:
        self.started.set()
        await self.unblock.wait()
        return await super().fetch_subgraph(**kwargs)


def _make_entry(api_id: str) -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id=api_id,
        description=f"查询 {api_id}",
        domain="iam",
        method="GET",
        path=f"/system/{api_id}",
        operation_safety="query",
    )


def _make_anchor_results() -> list[ApiCatalogSearchResult]:
    return [
        ApiCatalogSearchResult(entry=_make_entry("role_delete_v1"), score=0.95),
        ApiCatalogSearchResult(entry=_make_entry("role_detail_v1"), score=0.91),
    ]


def _make_subgraph() -> ApiCatalogSubgraphResult:
    return ApiCatalogSubgraphResult(
        anchor_api_ids=["role_delete_v1"],
        support_api_ids=["role_list_v1"],
        field_paths=[
            GraphFieldPath(
                consumer_api_id="role_delete_v1",
                producer_api_id="role_list_v1",
                semantic_key="Role.id",
                source_extract_path="data.records[].roleId",
                target_inject_path="body.roleId",
            )
        ],
    )


async def _anchor_searcher(*args, **kwargs) -> list[ApiCatalogSearchResult]:
    return _make_anchor_results()


async def _entry_loader(api_ids: list[str]) -> list[ApiCatalogEntry]:
    return [_make_entry(api_id) for api_id in api_ids]


class TestGraphRepositoryFetchSubgraph:
    @pytest.mark.asyncio
    async def test_falls_back_to_raw_traversal_when_companion_result_is_empty(self) -> None:
        repository = _SequencedSubgraphRepository(
            [
                ApiCatalogSubgraphResult(anchor_api_ids=["role_delete_v1"]),
                _make_subgraph(),
            ]
        )

        result = await repository.fetch_subgraph(
            anchor_api_ids=["role_delete_v1"],
            max_hops=1,
            support_limit=4,
            related_domains=["iam"],
            field_degree_cutoff=10,
        )

        assert result.support_api_ids == ["role_list_v1"]
        assert repository.query_order == ["companion", "raw"]

    @pytest.mark.asyncio
    async def test_stops_after_companion_hit(self) -> None:
        repository = _SequencedSubgraphRepository([_make_subgraph()])

        result = await repository.fetch_subgraph(
            anchor_api_ids=["role_delete_v1"],
            max_hops=1,
            support_limit=4,
            related_domains=["iam"],
            field_degree_cutoff=10,
        )

        assert result.support_api_ids == ["role_list_v1"]
        assert repository.query_order == ["companion"]


class TestHybridRetriever:
    @pytest.mark.asyncio
    async def test_uses_cached_subgraph_before_hitting_graph_repository(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "api_catalog_graph_enabled", True)
        cache = _FakeGraphCache()
        subgraph = _make_subgraph()
        cache_key = _build_subgraph_cache_lookup_key(
            anchor_api_ids=["role_delete_v1", "role_detail_v1"],
            max_hops=settings.api_catalog_graph_expand_hops,
            support_limit=settings.api_catalog_graph_support_limit,
            related_domains=["iam"],
        )
        cache.subgraphs[cache_key] = subgraph
        graph_repository = _RecordingGraphRepository(subgraph)
        retriever = ApiCatalogHybridRetriever(
            graph_repository=graph_repository,
            graph_cache=cache,
            anchor_searcher=_anchor_searcher,
            entry_loader=_entry_loader,
        )

        result = await retriever.search_subgraph_stratified("删除角色", domains=["iam"], trace_id="trace-cache-hit")

        assert graph_repository.calls == []
        assert [candidate.entry.id for candidate in result.candidates] == [
            "role_delete_v1",
            "role_detail_v1",
            "role_list_v1",
        ]
        assert retriever.get_subgraph_result("trace-cache-hit") == subgraph

    @pytest.mark.asyncio
    async def test_passes_domain_and_supernode_guardrails_and_caches_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "api_catalog_graph_enabled", True)
        monkeypatch.setattr(settings, "api_catalog_graph_related_domain_enabled", True)
        monkeypatch.setattr(settings, "api_catalog_graph_field_degree_cutoff", 7)
        cache = _FakeGraphCache()
        subgraph = _make_subgraph()
        graph_repository = _RecordingGraphRepository(subgraph)
        retriever = ApiCatalogHybridRetriever(
            graph_repository=graph_repository,
            graph_cache=cache,
            anchor_searcher=_anchor_searcher,
            entry_loader=_entry_loader,
        )

        result = await retriever.search_subgraph_stratified("删除角色", domains=["iam", "org"])

        assert result.subgraph.support_api_ids == ["role_list_v1"]
        assert graph_repository.calls[0]["related_domains"] == ["iam", "org"]
        assert graph_repository.calls[0]["field_degree_cutoff"] == 7
        assert cache.set_calls == 1
        cached_index_api_ids = next(iter(cache.indexed_api_ids.values()))
        assert sorted(cached_index_api_ids) == ["role_delete_v1", "role_detail_v1", "role_list_v1"]

    @pytest.mark.asyncio
    async def test_singleflight_prevents_concurrent_graph_fetch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "api_catalog_graph_enabled", True)
        monkeypatch.setattr(hybrid_module, "_SINGLEFLIGHT_WAIT_ATTEMPTS", 50)
        monkeypatch.setattr(hybrid_module, "_SINGLEFLIGHT_POLL_INTERVAL_SECONDS", 0.002)
        cache = _FakeGraphCache()
        graph_repository = _BlockingGraphRepository(_make_subgraph())
        retriever = ApiCatalogHybridRetriever(
            graph_repository=graph_repository,
            graph_cache=cache,
            anchor_searcher=_anchor_searcher,
            entry_loader=_entry_loader,
        )

        first_task = asyncio.create_task(retriever.search_subgraph_stratified("删除角色", domains=["iam"]))
        await graph_repository.started.wait()
        second_task = asyncio.create_task(retriever.search_subgraph_stratified("删除角色", domains=["iam"]))
        await asyncio.sleep(0.01)
        graph_repository.unblock.set()

        first_result, second_result = await asyncio.gather(first_task, second_task)

        assert len(graph_repository.calls) == 1
        assert cache.set_calls == 1
        assert first_result.subgraph.support_api_ids == ["role_list_v1"]
        assert second_result.subgraph.support_api_ids == ["role_list_v1"]
