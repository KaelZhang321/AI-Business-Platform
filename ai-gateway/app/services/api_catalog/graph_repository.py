"""Neo4j 访问 seam。

功能：
    统一封装 GraphRAG 对图数据库的读写访问，固定住两个最关键的边界：

    1. Stage 2 读取的是“字段级子图摘要”，而不是裸 Cypher 结果。
    2. 图同步必须按单 API 子图原子替换，不能把半成品事实暴露给在线流量。

返回值约束：
    - `fetch_subgraph()` 始终返回 `ApiCatalogSubgraphResult`
    - `sync_api_subgraph()` 始终返回 `GraphSyncImpactResult`
    - 任何底层 Neo4j 故障都要折叠成降级结果或统一异常，不能把 driver 细节泄漏到 workflow
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncManagedTransaction

from app.core.config import reveal_secret, settings
from app.services.api_catalog.graph_models import (
    ApiCatalogSubgraphResult,
    GraphFieldPath,
    GraphSyncImpactResult,
    NormalizedFieldBinding,
)
from app.services.api_catalog.schema import ApiCatalogEntry

logger = logging.getLogger(__name__)

_ALLOWED_GRAPH_ROLES = ["identifier", "locator", "bridge"]
_SUBGRAPH_ROW_FACTOR = 8

_COLLECT_IMPACTED_API_IDS_CYPHER = """
MATCH (api:ApiEndpoint {api_id: $api_id})
OPTIONAL MATCH (api)-[:CONSUMES|PRODUCES]->(:FieldSemantic)<-[:CONSUMES|PRODUCES]-(related:ApiEndpoint)
WHERE related.api_id <> api.api_id
WITH api, collect(DISTINCT related.api_id) AS related_api_ids
OPTIONAL MATCH (api)-[:COMPANION]-(companion:ApiEndpoint)
WHERE companion.api_id <> api.api_id
RETURN related_api_ids + collect(DISTINCT companion.api_id) AS impacted_api_ids
"""

_UPSERT_API_ENDPOINT_CYPHER = """
MERGE (api:ApiEndpoint {api_id: $api_id})
SET api.path = $path,
    api.method = $method,
    api.domain = $domain,
    api.env = $env,
    api.operation_safety = $operation_safety,
    api.requires_confirmation = $requires_confirmation,
    api.status = $status,
    api.tag_name = $tag_name,
    api.description = $description,
    api.response_data_path = $response_data_path,
    api.ui_hint = $ui_hint,
    api.auth_required = $auth_required,
    api.tags = $tags,
    api.business_intents = $business_intents,
    api.sync_run_id = $sync_run_id,
    api.metadata_version = $metadata_version,
    api.updated_at = datetime()
"""

_DELETE_FACT_EDGES_CYPHER = """
MATCH (api:ApiEndpoint {api_id: $api_id})-[r:CONSUMES|PRODUCES]->(:FieldSemantic)
DELETE r
"""

_UPSERT_FIELD_NODES_CYPHER = """
UNWIND $field_nodes AS field_node
MERGE (field:FieldSemantic {field_key: field_node.field_key})
SET field.entity = field_node.entity,
    field.canonical_name = field_node.canonical_name,
    field.label = field_node.label,
    field.field_type = field_node.field_type,
    field.value_type = field_node.value_type,
    field.description = field_node.description,
    field.display_domain_code = field_node.display_domain_code,
    field.display_domain_label = field_node.display_domain_label,
    field.display_section_code = field_node.display_section_code,
    field.display_section_label = field_node.display_section_label,
    field.category = field_node.category,
    field.business_domain = field_node.business_domain,
    field.graph_role = field_node.graph_role,
    field.is_identifier = field_node.is_identifier,
    field.is_graph_enabled = field_node.is_graph_enabled,
    field.confidence = field_node.confidence,
    field.updated_at = datetime()
"""

_UPSERT_CONSUMES_CYPHER = """
UNWIND $request_edges AS edge
MATCH (api:ApiEndpoint {api_id: $api_id})
MATCH (field:FieldSemantic {field_key: edge.semantic_key})
MERGE (api)-[r:CONSUMES]->(field)
SET r.location = edge.location,
    r.field_name = edge.field_name,
    r.json_path = edge.json_path,
    r.required = edge.required,
    r.array_mode = edge.array_mode,
    r.source = edge.source,
    r.name_source = edge.name_source,
    r.type_source = edge.type_source,
    r.description_source = edge.description_source,
    r.raw_field_type = edge.raw_field_type,
    r.raw_description = edge.raw_description,
    r.normalized_field_type = edge.normalized_field_type,
    r.normalized_value_type = edge.normalized_value_type,
    r.normalized_description = edge.normalized_description,
    r.confidence = edge.confidence,
    r.sync_run_id = edge.sync_run_id,
    r.updated_at = datetime()
"""

_UPSERT_PRODUCES_CYPHER = """
UNWIND $response_edges AS edge
MATCH (api:ApiEndpoint {api_id: $api_id})
MATCH (field:FieldSemantic {field_key: edge.semantic_key})
MERGE (api)-[r:PRODUCES]->(field)
SET r.location = edge.location,
    r.field_name = edge.field_name,
    r.json_path = edge.json_path,
    r.required = edge.required,
    r.array_mode = edge.array_mode,
    r.source = edge.source,
    r.name_source = edge.name_source,
    r.type_source = edge.type_source,
    r.description_source = edge.description_source,
    r.raw_field_type = edge.raw_field_type,
    r.raw_description = edge.raw_description,
    r.normalized_field_type = edge.normalized_field_type,
    r.normalized_value_type = edge.normalized_value_type,
    r.normalized_description = edge.normalized_description,
    r.confidence = edge.confidence,
    r.sync_run_id = edge.sync_run_id,
    r.updated_at = datetime()
"""

_DELETE_COMPANIONS_CYPHER = """
MATCH (from_api:ApiEndpoint)-[r:COMPANION]-(to_api:ApiEndpoint)
WHERE from_api.api_id IN $impacted_api_ids OR to_api.api_id IN $impacted_api_ids
DELETE r
"""

_REBUILD_COMPANIONS_CYPHER = """
UNWIND $impacted_api_ids AS impacted_api_id
MATCH (consumer:ApiEndpoint {api_id: impacted_api_id})-[consume:CONSUMES]->(field:FieldSemantic)<-[produce:PRODUCES]-(producer:ApiEndpoint)
WHERE consumer.api_id <> producer.api_id
  AND coalesce(field.is_graph_enabled, true) = true
  AND coalesce(field.graph_role, "none") IN $allowed_graph_roles
WITH consumer, producer, field,
     coalesce(field.is_identifier, false) AS is_identifier,
     toFloat(coalesce(consume.confidence, 1.0) + coalesce(produce.confidence, 1.0)) / 2.0 AS edge_confidence
ORDER BY consumer.api_id, producer.api_id, is_identifier DESC, edge_confidence DESC, field.field_key ASC
WITH consumer, producer, collect({
    field_key: field.field_key,
    is_identifier: is_identifier,
    confidence: edge_confidence
}) AS shared_fields
WITH consumer, producer, shared_fields, head(shared_fields) AS primary_field
MERGE (consumer)-[r:COMPANION]->(producer)
SET r.reason = "shared_field_dependency",
    r.primary_field = primary_field.field_key,
    r.shared_field_count = size(shared_fields),
    r.hop_count = 1,
    r.score = toFloat(size(shared_fields)) + CASE WHEN coalesce(primary_field.is_identifier, false) THEN 1.0 ELSE 0.0 END,
    r.updated_at = datetime()
"""

_RAW_SUBGRAPH_CYPHER = """
UNWIND $anchor_api_ids AS anchor_api_id
MATCH (anchor:ApiEndpoint {api_id: anchor_api_id})-[consume:CONSUMES]->(field:FieldSemantic)<-[produce:PRODUCES]-(producer:ApiEndpoint)
WHERE anchor.api_id <> producer.api_id
  AND ($related_domain_count = 0 OR producer.domain IN $related_domains)
  AND coalesce(field.is_graph_enabled, true) = true
  AND coalesce(field.graph_role, "none") IN $allowed_graph_roles
  AND size([(field)<-[:PRODUCES]-() | 1]) <= $field_degree_cutoff
  AND size([(field)<-[:CONSUMES]-() | 1]) <= $field_degree_cutoff
RETURN anchor.api_id AS consumer_api_id,
       producer.api_id AS producer_api_id,
       field.field_key AS semantic_key,
       produce.json_path AS source_extract_path,
       consume.json_path AS target_inject_path,
       toFloat(coalesce(consume.confidence, 1.0) + coalesce(produce.confidence, 1.0)) / 2.0 AS confidence,
       coalesce(field.is_identifier, false) AS is_identifier,
       coalesce(produce.array_mode, false) AS source_array_mode,
       coalesce(consume.array_mode, false) AS target_array_mode
LIMIT $row_limit
"""


def _build_companion_subgraph_cypher(max_hops: int) -> str:
    """构造带 hop 上限的 Stage 2 主查询。

    功能：
        Neo4j 目前不支持把可变长度路径上界直接安全地作为普通参数传入，因此这里用
        受配置护栏保护的整数插值生成查询模板。真正的业务变量仍通过参数绑定传入，
        避免把在线查询退化成字符串拼接。
    """

    safe_hops = max(1, min(max_hops, 3))
    return f"""
UNWIND $anchor_api_ids AS anchor_api_id
MATCH (anchor:ApiEndpoint {{api_id: anchor_api_id}})
MATCH (anchor)-[:COMPANION*1..{safe_hops}]->(producer:ApiEndpoint)
WHERE anchor.api_id <> producer.api_id
  AND ($related_domain_count = 0 OR producer.domain IN $related_domains)
WITH DISTINCT anchor, producer
MATCH (anchor)-[consume:CONSUMES]->(field:FieldSemantic)<-[produce:PRODUCES]-(producer)
WHERE coalesce(field.is_graph_enabled, true) = true
  AND coalesce(field.graph_role, "none") IN $allowed_graph_roles
  AND size([(field)<-[:PRODUCES]-() | 1]) <= $field_degree_cutoff
  AND size([(field)<-[:CONSUMES]-() | 1]) <= $field_degree_cutoff
RETURN anchor.api_id AS consumer_api_id,
       producer.api_id AS producer_api_id,
       field.field_key AS semantic_key,
       produce.json_path AS source_extract_path,
       consume.json_path AS target_inject_path,
       toFloat(coalesce(consume.confidence, 1.0) + coalesce(produce.confidence, 1.0)) / 2.0 AS confidence,
       coalesce(field.is_identifier, false) AS is_identifier,
       coalesce(produce.array_mode, false) AS source_array_mode,
       coalesce(consume.array_mode, false) AS target_array_mode
LIMIT $row_limit
"""


class GraphRepositoryError(RuntimeError):
    """图仓储统一异常基类。"""


class GraphRepository:
    """GraphRAG 仓储接口。

    功能：
        对上游 service 暴露稳定方法集合，避免 workflow / retriever / graph sync 直接依赖 Neo4j driver。
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
        entry: ApiCatalogEntry,
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
        用 Neo4j 的 ACID 写事务保证“单 API 子图替换”要么全部成功、要么全部回滚，
        同时把 Stage 2 的 `COMPANION` 剪枝和主事实回捞统一封装在仓储层，避免上层继续拼 Cypher。
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
        self._password = password or reveal_secret(settings.neo4j_password)
        self._enabled = settings.api_catalog_graph_enabled if enabled is None else enabled
        self._driver: AsyncDriver | None = None

    def _get_driver(self) -> AsyncDriver:
        """懒加载 Neo4j driver。

        功能：
            GraphRAG 允许灰度启用；只有图能力真的打开时才建立连接，避免“配置先发、图库未就绪”
            的过渡状态把整个网关拖死。
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
        """提取字段级候选子图。

        功能：
            Stage 2 主路径先用 `COMPANION` 做范围剪枝，再在同一条查询里回捞真实字段路径；
            只有当剪枝边不足时，才回退到 `CONSUMES -> Field <- PRODUCES` 原始遍历。
        """

        anchor_list = [api_id for api_id in anchor_api_ids if api_id]
        if not anchor_list:
            return ApiCatalogSubgraphResult()
        if not self._enabled:
            return ApiCatalogSubgraphResult(
                anchor_api_ids=anchor_list,
                graph_degraded=True,
                degraded_reason="graph_disabled",
            )

        try:
            async with self._get_driver().session() as session:
                return await session.execute_read(
                    self._fetch_subgraph_tx,
                    anchor_list,
                    max_hops,
                    support_limit,
                    related_domains or [],
                    field_degree_cutoff or settings.api_catalog_graph_field_degree_cutoff,
                )
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
        entry: ApiCatalogEntry,
        bindings: list[NormalizedFieldBinding],
        sync_run_id: str,
        metadata_version: str | None = None,
    ) -> GraphSyncImpactResult:
        """按单 API 子图原子替换主事实与伴生边。

        功能：
            这里不做“慢慢 MERGE 再修修补补”，而是依赖 Neo4j 写事务把单个 API 的
            主事实边、Stale Edge 清理和 `COMPANION` 重建折叠成一次提交，杜绝半图暴露。
        """

        if not self._enabled:
            return GraphSyncImpactResult(
                api_id=entry.id,
                impacted_api_ids=[entry.id],
                sync_run_id=sync_run_id,
                metadata_version=metadata_version,
            )

        try:
            async with self._get_driver().session() as session:
                return await session.execute_write(
                    self._sync_api_subgraph_tx,
                    entry,
                    bindings,
                    sync_run_id,
                    metadata_version,
                )
        except Exception as exc:  # pragma: no cover - 依赖外部图数据库
            raise GraphRepositoryError(f"graph sync failed for api_id={entry.id}: {exc}") from exc

    async def close(self) -> None:
        """关闭 Neo4j driver。"""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def _fetch_subgraph_tx(
        self,
        tx: AsyncManagedTransaction,
        anchor_api_ids: list[str],
        max_hops: int,
        support_limit: int,
        related_domains: list[str],
        field_degree_cutoff: int,
    ) -> ApiCatalogSubgraphResult:
        """在同一读事务内完成主路径查询与兜底查询。"""

        params = {
            "anchor_api_ids": anchor_api_ids,
            "related_domains": related_domains,
            "related_domain_count": len(related_domains),
            "field_degree_cutoff": field_degree_cutoff,
            "allowed_graph_roles": _ALLOWED_GRAPH_ROLES,
            # 一条 support API 可能对应多个共享字段；这里适当放大行数上限，避免过早截断字段路径。
            "row_limit": max(support_limit, 1) * _SUBGRAPH_ROW_FACTOR,
        }
        companion_result = await self._run_subgraph_query(
            tx,
            query=_build_companion_subgraph_cypher(max_hops=max_hops),
            params=params,
            anchor_api_ids=anchor_api_ids,
            support_limit=support_limit,
        )
        if companion_result.support_api_ids:
            return companion_result

        return await self._run_subgraph_query(
            tx,
            query=_RAW_SUBGRAPH_CYPHER,
            params=params,
            anchor_api_ids=anchor_api_ids,
            support_limit=support_limit,
        )

    async def _run_subgraph_query(
        self,
        tx: AsyncManagedTransaction,
        *,
        query: str,
        params: dict[str, Any],
        anchor_api_ids: list[str],
        support_limit: int,
    ) -> ApiCatalogSubgraphResult:
        """执行一次子图查询并折叠成稳定结构。"""

        result = await tx.run(query, **params)
        rows = [record async for record in result]
        return _build_subgraph_result(anchor_api_ids=anchor_api_ids, rows=rows, support_limit=support_limit)

    async def _sync_api_subgraph_tx(
        self,
        tx: AsyncManagedTransaction,
        entry: ApiCatalogEntry,
        bindings: list[NormalizedFieldBinding],
        sync_run_id: str,
        metadata_version: str | None,
    ) -> GraphSyncImpactResult:
        """在单个写事务内完成 API 子图替换。

        功能：
            写事务内部要先记住“旧世界影响了谁”，再落下“新世界事实”，最后重建 `COMPANION`。
            这样即使某个字段被删掉，旧邻居也会被纳入 `impacted_api_ids`，缓存能被精准驱逐。
        """

        impacted_before = await self._collect_impacted_api_ids(tx, entry.id)
        await self._upsert_api_endpoint(tx, entry, sync_run_id=sync_run_id, metadata_version=metadata_version)
        await self._replace_main_fact_edges(tx, entry.id, bindings, sync_run_id=sync_run_id)
        impacted_after = await self._collect_impacted_api_ids(tx, entry.id)

        impacted_api_ids = sorted({entry.id, *impacted_before, *impacted_after})
        await self._delete_companion_edges(tx, impacted_api_ids)
        await self._rebuild_companion_edges(tx, impacted_api_ids)

        return GraphSyncImpactResult(
            api_id=entry.id,
            impacted_api_ids=impacted_api_ids,
            sync_run_id=sync_run_id,
            metadata_version=metadata_version,
        )

    async def _collect_impacted_api_ids(self, tx: AsyncManagedTransaction, api_id: str) -> list[str]:
        """收集单个 API 当前已经牵动到的邻居接口。

        功能：
            这里要同时扫主事实边和历史 `COMPANION`，原因是 API 本轮可能是在“删字段”。
            如果只看新事实，旧依赖方就会从影响面里消失，导致 stale cache 无法被精准清理。
        """

        result = await tx.run(_COLLECT_IMPACTED_API_IDS_CYPHER, api_id=api_id)
        record = await result.single()
        if record is None:
            return []
        impacted_ids = record.get("impacted_api_ids") or []
        return sorted({str(impacted_id) for impacted_id in impacted_ids if impacted_id and impacted_id != api_id})

    async def _upsert_api_endpoint(
        self,
        tx: AsyncManagedTransaction,
        entry: ApiCatalogEntry,
        *,
        sync_run_id: str,
        metadata_version: str | None,
    ) -> None:
        """Upsert `ApiEndpoint` 节点。"""

        payload = {
            "api_id": entry.id,
            "path": entry.path,
            "method": entry.method,
            "domain": entry.domain,
            "env": entry.env,
            "operation_safety": entry.operation_safety,
            "requires_confirmation": entry.requires_confirmation,
            "status": entry.status,
            "tag_name": entry.tag_name,
            "description": entry.description,
            "response_data_path": entry.response_data_path,
            "ui_hint": entry.ui_hint,
            "auth_required": entry.auth_required,
            "tags": entry.tags,
            "business_intents": entry.business_intents,
            "sync_run_id": sync_run_id,
            "metadata_version": metadata_version,
        }
        await tx.run(_UPSERT_API_ENDPOINT_CYPHER, **payload)

    async def _replace_main_fact_edges(
        self,
        tx: AsyncManagedTransaction,
        api_id: str,
        bindings: list[NormalizedFieldBinding],
        *,
        sync_run_id: str,
    ) -> None:
        """替换单个 API 的 `CONSUMES / PRODUCES` 主事实边。

        功能：
            事务内先删再建并不会对外暴露中间态，因此这里优先选择更直观的“整组替换”写法，
            降低 Stale Edge 残留的风险，而不是为了保留历史边去做复杂的逐条 diff。
        """

        await tx.run(_DELETE_FACT_EDGES_CYPHER, api_id=api_id)

        field_nodes = _build_field_node_payloads(bindings)
        if field_nodes:
            await tx.run(_UPSERT_FIELD_NODES_CYPHER, field_nodes=field_nodes)

        request_edges = _build_edge_payloads(bindings, direction="request", sync_run_id=sync_run_id)
        if request_edges:
            await tx.run(_UPSERT_CONSUMES_CYPHER, api_id=api_id, request_edges=request_edges)

        response_edges = _build_edge_payloads(bindings, direction="response", sync_run_id=sync_run_id)
        if response_edges:
            await tx.run(_UPSERT_PRODUCES_CYPHER, api_id=api_id, response_edges=response_edges)

    async def _delete_companion_edges(self, tx: AsyncManagedTransaction, impacted_api_ids: list[str]) -> None:
        """删除受影响范围内的旧 `COMPANION`。"""

        if not impacted_api_ids:
            return
        await tx.run(_DELETE_COMPANIONS_CYPHER, impacted_api_ids=impacted_api_ids)

    async def _rebuild_companion_edges(self, tx: AsyncManagedTransaction, impacted_api_ids: list[str]) -> None:
        """基于最新主事实重建 `COMPANION` 摘要边。"""

        if not impacted_api_ids:
            return
        await tx.run(
            _REBUILD_COMPANIONS_CYPHER,
            impacted_api_ids=impacted_api_ids,
            allowed_graph_roles=_ALLOWED_GRAPH_ROLES,
        )


def _build_subgraph_result(
    *,
    anchor_api_ids: list[str],
    rows: list[Any],
    support_limit: int,
) -> ApiCatalogSubgraphResult:
    """把 Neo4j 原始查询结果折叠成稳定的 Stage 2 子图结构。

    功能：
        在线层真正关心的是“锚点带出了哪些 support API，以及每条路径要从哪里取值再注入哪里”。
        这里故意不透出 Neo4j 原始 record，避免上层再去解释数据库细节。
    """

    support_api_ids: list[str] = []
    accepted_support_ids: set[str] = set()
    field_paths: list[GraphFieldPath] = []

    for row in rows:
        producer_api_id = str(row.get("producer_api_id") or "")
        if not producer_api_id:
            continue

        if producer_api_id not in accepted_support_ids:
            if len(accepted_support_ids) >= support_limit:
                continue
            accepted_support_ids.add(producer_api_id)
            support_api_ids.append(producer_api_id)

        field_paths.append(
            GraphFieldPath(
                consumer_api_id=str(row.get("consumer_api_id") or ""),
                producer_api_id=producer_api_id,
                semantic_key=str(row.get("semantic_key") or ""),
                source_extract_path=str(row.get("source_extract_path") or ""),
                target_inject_path=str(row.get("target_inject_path") or ""),
                confidence=float(row.get("confidence") or 1.0),
                is_identifier=bool(row.get("is_identifier") or False),
                source_array_mode=bool(row.get("source_array_mode") or False),
                target_array_mode=bool(row.get("target_array_mode") or False),
            )
        )

    return ApiCatalogSubgraphResult(
        anchor_api_ids=anchor_api_ids,
        support_api_ids=support_api_ids,
        field_paths=field_paths,
    )


def _build_field_node_payloads(bindings: list[NormalizedFieldBinding]) -> list[dict[str, Any]]:
    """把字段绑定聚合成 `FieldSemantic` 节点载荷。

    功能：
        同一个 `semantic_key` 可能在请求和响应两侧各出现一次。节点级属性应取“最可信的标准画像”，
        而不是机械复制某一条边上的 raw 信息。
    """

    field_nodes: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        entity_code, canonical_name = _split_semantic_key(
            semantic_key=binding.semantic_key,
            entity_code=binding.entity_code,
            canonical_name=binding.canonical_name,
        )
        payload = {
            "field_key": binding.semantic_key,
            "entity": entity_code,
            "canonical_name": canonical_name,
            "label": binding.normalized_label or binding.raw_field_name,
            "field_type": binding.normalized_field_type,
            "value_type": binding.normalized_value_type,
            "description": binding.normalized_description,
            "display_domain_code": binding.display_domain_code,
            "display_domain_label": binding.display_domain_label,
            "display_section_code": binding.display_section_code,
            "display_section_label": binding.display_section_label,
            "category": binding.category,
            "business_domain": binding.business_domain,
            "graph_role": binding.graph_role,
            "is_identifier": binding.is_identifier,
            "is_graph_enabled": binding.is_graph_enabled,
            "confidence": binding.confidence,
        }
        current = field_nodes.get(binding.semantic_key)
        if current is None or float(payload["confidence"]) > float(current["confidence"]):
            field_nodes[binding.semantic_key] = payload
    return [field_nodes[field_key] for field_key in sorted(field_nodes)]


def _build_edge_payloads(
    bindings: list[NormalizedFieldBinding],
    *,
    direction: str,
    sync_run_id: str,
) -> list[dict[str, Any]]:
    """把字段绑定转换为 `CONSUMES / PRODUCES` 边载荷。"""

    payloads: list[dict[str, Any]] = []
    for binding in bindings:
        if binding.direction != direction:
            continue
        payloads.append(
            {
                "semantic_key": binding.semantic_key,
                "location": binding.location,
                "field_name": binding.raw_field_name,
                "json_path": binding.json_path,
                "required": binding.required,
                "array_mode": binding.array_mode,
                "source": binding.source,
                "name_source": binding.name_source,
                "type_source": binding.type_source,
                "description_source": binding.description_source,
                "raw_field_type": binding.raw_field_type,
                "raw_description": binding.raw_description,
                "normalized_field_type": binding.normalized_field_type,
                "normalized_value_type": binding.normalized_value_type,
                "normalized_description": binding.normalized_description,
                "confidence": binding.confidence,
                "sync_run_id": sync_run_id,
            }
        )
    return payloads


def _split_semantic_key(
    *,
    semantic_key: str,
    entity_code: str | None,
    canonical_name: str | None,
) -> tuple[str | None, str | None]:
    """优先使用治理字典给出的实体与规范名，缺失时再从 `semantic_key` 回退解析。"""

    if entity_code or canonical_name:
        return entity_code, canonical_name
    if "." not in semantic_key:
        return None, semantic_key or None
    entity, name = semantic_key.split(".", 1)
    return entity or None, name or None
