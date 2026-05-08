from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

import pytest

import app.services.api_catalog.indexer as indexer_module
from app.core.config import settings
from app.services.api_catalog.graph_models import (
    GraphCacheInvalidationRequest,
    GraphSyncImpactResult,
    NormalizedFieldBinding,
    SemanticGovernanceSnapshot,
)
from app.services.api_catalog.graph_repository import GraphRepositoryError, Neo4jGraphRepository
from app.services.api_catalog.graph_sync import ApiCatalogGraphSyncService
from app.services.api_catalog.schema import ApiCatalogEntry


@dataclass
class _InMemoryGraphStore:
    api_nodes: dict[str, dict] = field(default_factory=dict)
    field_nodes: dict[str, dict] = field(default_factory=dict)
    consumes: dict[str, list[dict]] = field(default_factory=dict)
    produces: dict[str, list[dict]] = field(default_factory=dict)
    companions: dict[tuple[str, str], dict] = field(default_factory=dict)

    def clone(self) -> "_InMemoryGraphStore":
        return deepcopy(self)

    def snapshot(self) -> dict[str, dict]:
        return {
            "api_nodes": deepcopy(self.api_nodes),
            "field_nodes": deepcopy(self.field_nodes),
            "consumes": deepcopy(self.consumes),
            "produces": deepcopy(self.produces),
            "companions": deepcopy(self.companions),
        }


class _FakeWriteTransaction:
    def __init__(self, store: _InMemoryGraphStore) -> None:
        self.store = store


class _FakeWriteSession:
    def __init__(self, repository: "_InMemoryTransactionalGraphRepository") -> None:
        self._repository = repository

    async def __aenter__(self) -> "_FakeWriteSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def execute_write(self, func, *args):
        working_store = self._repository.store.clone()
        tx = _FakeWriteTransaction(working_store)
        result = await func(tx, *args)
        self._repository.store = working_store
        return result


class _FakeWriteDriver:
    def __init__(self, repository: "_InMemoryTransactionalGraphRepository") -> None:
        self._repository = repository

    def session(self, *args, **kwargs) -> _FakeWriteSession:
        return _FakeWriteSession(self._repository)

    async def verify_connectivity(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _InMemoryTransactionalGraphRepository(Neo4jGraphRepository):
    def __init__(self, store: _InMemoryGraphStore | None = None) -> None:
        super().__init__(enabled=True)
        self.store = store or _InMemoryGraphStore()
        self.fail_stage: str | None = None
        self._driver = _FakeWriteDriver(self)

    async def _collect_impacted_api_ids(self, tx: _FakeWriteTransaction, api_id: str) -> list[str]:
        impacted_ids: set[str] = set()
        consumed_fields = {edge["semantic_key"] for edge in tx.store.consumes.get(api_id, [])}
        produced_fields = {edge["semantic_key"] for edge in tx.store.produces.get(api_id, [])}

        for other_api_id, edges in tx.store.produces.items():
            if other_api_id == api_id:
                continue
            if any(edge["semantic_key"] in consumed_fields for edge in edges):
                impacted_ids.add(other_api_id)

        for other_api_id, edges in tx.store.consumes.items():
            if other_api_id == api_id:
                continue
            if any(edge["semantic_key"] in produced_fields for edge in edges):
                impacted_ids.add(other_api_id)

        for consumer_api_id, producer_api_id in tx.store.companions:
            if consumer_api_id == api_id:
                impacted_ids.add(producer_api_id)
            if producer_api_id == api_id:
                impacted_ids.add(consumer_api_id)

        return sorted(impacted_ids)

    async def _upsert_api_endpoint(
        self,
        tx: _FakeWriteTransaction,
        entry: ApiCatalogEntry,
        *,
        sync_run_id: str,
        metadata_version: str | None,
    ) -> None:
        if self.fail_stage == "upsert_api_endpoint":
            raise RuntimeError("boom on api upsert")

        tx.store.api_nodes[entry.id] = {
            "api_id": entry.id,
            "path": entry.path,
            "method": entry.method,
            "domain": entry.domain,
            "operation_safety": entry.operation_safety,
            "requires_confirmation": entry.requires_confirmation,
            "sync_run_id": sync_run_id,
            "metadata_version": metadata_version,
        }

    async def _replace_main_fact_edges(
        self,
        tx: _FakeWriteTransaction,
        api_id: str,
        bindings: list[NormalizedFieldBinding],
        *,
        sync_run_id: str,
    ) -> None:
        tx.store.consumes.pop(api_id, None)
        tx.store.produces.pop(api_id, None)
        if self.fail_stage == "replace_main_fact_edges":
            raise RuntimeError("boom on fact replace")

        request_edges: list[dict] = []
        response_edges: list[dict] = []
        for binding in bindings:
            tx.store.field_nodes[binding.semantic_key] = {
                "field_key": binding.semantic_key,
                "display_domain_code": binding.display_domain_code,
                "display_section_code": binding.display_section_code,
                "graph_role": binding.graph_role,
                "is_identifier": binding.is_identifier,
                "is_graph_enabled": binding.is_graph_enabled,
            }
            edge = {"semantic_key": binding.semantic_key, "confidence": binding.confidence, "sync_run_id": sync_run_id}
            if binding.direction == "request":
                request_edges.append(edge)
            else:
                response_edges.append(edge)
        if request_edges:
            tx.store.consumes[api_id] = request_edges
        if response_edges:
            tx.store.produces[api_id] = response_edges

    async def _delete_companion_edges(self, tx: _FakeWriteTransaction, impacted_api_ids: list[str]) -> None:
        if self.fail_stage == "delete_companion_edges":
            raise RuntimeError("boom on companion delete")

        stale_pairs = [
            pair
            for pair in tx.store.companions
            if pair[0] in impacted_api_ids or pair[1] in impacted_api_ids
        ]
        for pair in stale_pairs:
            tx.store.companions.pop(pair, None)

    async def _rebuild_companion_edges(self, tx: _FakeWriteTransaction, impacted_api_ids: list[str]) -> None:
        if self.fail_stage == "rebuild_companion_edges":
            raise RuntimeError("boom on companion rebuild")

        for consumer_api_id in impacted_api_ids:
            consumer_edges = tx.store.consumes.get(consumer_api_id, [])
            if not consumer_edges:
                continue

            consumer_fields = {edge["semantic_key"]: edge for edge in consumer_edges}
            for producer_api_id, producer_edges in tx.store.produces.items():
                if producer_api_id == consumer_api_id:
                    continue

                shared_fields = []
                for producer_edge in producer_edges:
                    semantic_key = producer_edge["semantic_key"]
                    if semantic_key not in consumer_fields:
                        continue
                    field_node = tx.store.field_nodes.get(semantic_key, {})
                    shared_fields.append(
                        {
                            "field_key": semantic_key,
                            "is_identifier": bool(field_node.get("is_identifier")),
                            "confidence": float(consumer_fields[semantic_key]["confidence"] + producer_edge["confidence"]) / 2.0,
                        }
                    )

                if not shared_fields:
                    continue

                shared_fields.sort(
                    key=lambda item: (
                        not item["is_identifier"],
                        -item["confidence"],
                        item["field_key"],
                    )
                )
                primary_field = shared_fields[0]
                tx.store.companions[(consumer_api_id, producer_api_id)] = {
                    "primary_field": primary_field["field_key"],
                    "shared_field_count": len(shared_fields),
                    "score": float(len(shared_fields)) + (1.0 if primary_field["is_identifier"] else 0.0),
                }


class _FakeGraphCache:
    def __init__(self) -> None:
        self.requests: list[GraphCacheInvalidationRequest] = []

    async def invalidate(self, request: GraphCacheInvalidationRequest) -> int:
        self.requests.append(request)
        return len(request.impacted_api_ids)

    async def close(self) -> None:
        return None


class _FakeGraphSyncRepository:
    def __init__(self, events: list[str], result: GraphSyncImpactResult) -> None:
        self.events = events
        self.result = result

    async def sync_api_subgraph(self, *, entry, bindings, sync_run_id, metadata_version=None) -> GraphSyncImpactResult:
        self.events.append("repo")
        return self.result

    async def close(self) -> None:
        return None


class _FakeResolver:
    def __init__(self, bindings: list[NormalizedFieldBinding]) -> None:
        self.bindings = bindings
        self.load_calls = 0
        self.resolve_calls = 0

    async def load_governance_snapshot(self) -> SemanticGovernanceSnapshot:
        self.load_calls += 1
        return SemanticGovernanceSnapshot()

    def resolve_entry_bindings(
        self,
        entry: ApiCatalogEntry,
        *,
        governance_snapshot: SemanticGovernanceSnapshot,
    ) -> list[NormalizedFieldBinding]:
        self.resolve_calls += 1
        return self.bindings


class _FakeGraphSyncService:
    def __init__(self, result: GraphSyncImpactResult) -> None:
        self.result = result
        self.calls: list[tuple[str, list[NormalizedFieldBinding]]] = []

    async def sync_entry(self, entry: ApiCatalogEntry, bindings: list[NormalizedFieldBinding]) -> GraphSyncImpactResult:
        self.calls.append((entry.id, bindings))
        return self.result


def _make_entry(api_id: str, *, method: str = "POST") -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id=api_id,
        description="删除角色",
        domain="iam",
        method=method,
        path=f"/system/{api_id}",
        operation_safety="mutation" if method != "GET" else "query",
        requires_confirmation=method != "GET",
    )


def _make_binding(api_id: str, semantic_key: str, *, direction: str = "request") -> NormalizedFieldBinding:
    return NormalizedFieldBinding(
        api_id=api_id,
        direction=direction,
        location="body" if direction == "request" else "response",
        raw_field_name="roleId",
        raw_field_type="string",
        raw_description="角色主键",
        json_path="body.roleId" if direction == "request" else "data.records[].roleId",
        semantic_key=semantic_key,
        entity_code="Role",
        canonical_name="id",
        normalized_label="角色ID",
        normalized_field_type="text",
        normalized_value_type="string",
        normalized_description="角色主键",
        category="business",
        business_domain="iam",
        display_domain_code="role",
        display_domain_label="角色",
        display_section_code="basic",
        display_section_label="基本信息",
        required=True,
        confidence=0.98,
        graph_role="identifier",
        is_identifier=True,
        is_graph_enabled=True,
    )


class TestGraphRepositorySync:
    @pytest.mark.asyncio
    async def test_sync_replaces_stale_edges_and_rebuilds_companion_summary(self) -> None:
        store = _InMemoryGraphStore(
            api_nodes={"role_delete_v1": {"api_id": "role_delete_v1"}, "role_list_v1": {"api_id": "role_list_v1"}},
            field_nodes={"Role.legacy": {}, "Role.id": {"is_identifier": True}},
            consumes={"role_delete_v1": [{"semantic_key": "Role.legacy", "confidence": 1.0}]},
            produces={"role_list_v1": [{"semantic_key": "Role.id", "confidence": 1.0}]},
            companions={("role_delete_v1", "role_list_v1"): {"primary_field": "Role.legacy", "shared_field_count": 1}},
        )
        repository = _InMemoryTransactionalGraphRepository(store)

        result = await repository.sync_api_subgraph(
            entry=_make_entry("role_delete_v1"),
            bindings=[_make_binding("role_delete_v1", "Role.id")],
            sync_run_id="sync-role-delete",
            metadata_version="meta-v1",
        )

        assert result.impacted_api_ids == ["role_delete_v1", "role_list_v1"]
        assert repository.store.consumes["role_delete_v1"] == [
            {"semantic_key": "Role.id", "confidence": 0.98, "sync_run_id": "sync-role-delete"}
        ]
        assert repository.store.field_nodes["Role.id"]["display_domain_code"] == "role"
        assert repository.store.companions[("role_delete_v1", "role_list_v1")] == {
            "primary_field": "Role.id",
            "shared_field_count": 1,
            "score": 2.0,
        }

    @pytest.mark.asyncio
    async def test_sync_rolls_back_when_fact_replace_fails(self) -> None:
        store = _InMemoryGraphStore(
            api_nodes={"role_delete_v1": {"api_id": "role_delete_v1"}},
            consumes={"role_delete_v1": [{"semantic_key": "Role.legacy", "confidence": 1.0}]},
        )
        repository = _InMemoryTransactionalGraphRepository(store)
        repository.fail_stage = "replace_main_fact_edges"
        before_snapshot = repository.store.snapshot()

        with pytest.raises(GraphRepositoryError):
            await repository.sync_api_subgraph(
                entry=_make_entry("role_delete_v1"),
                bindings=[_make_binding("role_delete_v1", "Role.id")],
                sync_run_id="sync-role-delete",
            )

        assert repository.store.snapshot() == before_snapshot


class TestGraphSyncService:
    @pytest.mark.asyncio
    async def test_service_invalidates_cache_after_transaction_commit(self) -> None:
        events: list[str] = []
        repository = _FakeGraphSyncRepository(
            events,
            GraphSyncImpactResult(
                api_id="role_delete_v1",
                impacted_api_ids=["role_delete_v1", "role_list_v1"],
                sync_run_id="sync-role-delete",
            ),
        )
        cache = _FakeGraphCache()

        async def hook(result: GraphSyncImpactResult) -> None:
            events.append("hook")
            assert result.impacted_api_ids == ["role_delete_v1", "role_list_v1"]

        original_invalidate = cache.invalidate

        async def invalidate_with_event(request: GraphCacheInvalidationRequest) -> int:
            events.append("cache")
            return await original_invalidate(request)

        cache.invalidate = invalidate_with_event
        service = ApiCatalogGraphSyncService(
            graph_repository=repository,
            graph_cache=cache,
            post_commit_hook=hook,
            sync_run_id_factory=lambda: "sync-role-delete",
        )

        result = await service.sync_entry(_make_entry("role_delete_v1"), [_make_binding("role_delete_v1", "Role.id")])

        assert result.api_id == "role_delete_v1"
        assert events == ["repo", "cache", "hook"]
        assert cache.requests[0].impacted_api_ids == ["role_delete_v1", "role_list_v1"]


class TestIndexerGraphSyncIntegration:
    @pytest.mark.asyncio
    async def test_index_entry_calls_graph_sync_and_exposes_hook(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hook_results: list[GraphSyncImpactResult] = []
        resolver = _FakeResolver([_make_binding("role_delete_v1", "Role.id")])
        sync_service = _FakeGraphSyncService(
            GraphSyncImpactResult(
                api_id="role_delete_v1",
                impacted_api_ids=["role_delete_v1", "role_list_v1"],
                sync_run_id="sync-role-delete",
            )
        )

        class _FakeVector:
            def tolist(self) -> list[float]:
                return [0.1, 0.2]

        class _FakeEmbedder:
            def encode(self, texts: list[str]) -> dict[str, list[_FakeVector]]:
                return {"dense_vecs": [_FakeVector()]}

        class _FakeCollection:
            def delete(self, expr: str) -> None:
                return None

            def insert(self, data) -> None:
                return None

            def flush(self) -> None:
                return None

        async def hook(result: GraphSyncImpactResult) -> None:
            hook_results.append(result)

        monkeypatch.setattr(settings, "api_catalog_graph_enabled", True)
        indexer = indexer_module.ApiCatalogIndexer(
            field_resolver=resolver,
            graph_sync_service=sync_service,
            graph_sync_hook=hook,
        )
        monkeypatch.setattr(indexer, "_get_embedder", lambda: _FakeEmbedder())
        monkeypatch.setattr(indexer, "_get_collection", lambda: _FakeCollection())

        await indexer.index_entry(
            _make_entry("role_delete_v1"),
            governance_snapshot=SemanticGovernanceSnapshot(),
        )

        assert resolver.load_calls == 0
        assert resolver.resolve_calls == 1
        assert sync_service.calls[0][0] == "role_delete_v1"
        assert hook_results[0].impacted_api_ids == ["role_delete_v1", "role_list_v1"]
