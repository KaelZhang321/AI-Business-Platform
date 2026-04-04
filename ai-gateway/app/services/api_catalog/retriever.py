"""
API Catalog — 语义检索器

职责：
1. 单域语义检索
2. 多域分层召回（Scatter-Gather）
3. 统一的标量过滤拼装

设计动机：
- 第二阶段已经先拿到了 `query_domains`，这里必须尊重该结果做分层召回
- 多域并发检索的目标不是“找全世界最像的 5 个接口”，而是“让每个目标域都至少带回自己的核心候选”
"""

from __future__ import annotations

import asyncio
import json
import logging

from FlagEmbedding import BGEM3FlagModel
from pymilvus import Collection, connections

from app.core.config import settings
from app.services.api_catalog.indexer import API_CATALOG_COLLECTION
from app.services.api_catalog.schema import (
    ApiCatalogDetailHint,
    ApiCatalogEntry,
    ApiCatalogPaginationHint,
    ApiCatalogSearchFilters,
    ApiCatalogSearchResult,
    ApiCatalogTemplateHint,
    ParamSchema,
)

logger = logging.getLogger(__name__)

_OUTPUT_FIELDS = [
    "id",
    "description",
    "domain",
    "env",
    "status",
    "tag_name",
    "method",
    "path",
    "auth_required",
    "ui_hint",
    "example_queries",
    "tags",
    "business_intents",
    "api_schema",
    "response_data_path",
    "field_labels",
    "executor_config",
    "security_rules",
    "detail_hint",
    "pagination_hint",
    "template_hint",
]
_LEGACY_OUTPUT_FIELDS = [
    "id",
    "description",
    "domain",
    "env",
    "status",
    "tag_name",
    "method",
    "path",
    "auth_required",
    "ui_hint",
    "example_queries_json",
    "tags_json",
    "business_intents_json",
    "param_schema_json",
    "response_data_path",
    "field_labels_json",
    "executor_config_json",
    "security_rules_json",
    "detail_hint_json",
    "pagination_hint_json",
    "template_hint_json",
]


class ApiCatalogRetriever:
    """从 Milvus `api_catalog` collection 检索最匹配的业务接口。"""

    def __init__(self) -> None:
        self._embedder: BGEM3FlagModel | None = None
        self._collection: Collection | None = None

    def _get_embedder(self) -> BGEM3FlagModel:
        """懒加载查询向量模型。"""
        if self._embedder is None:
            self._embedder = BGEM3FlagModel(settings.embedding_model_name, use_fp16=True)
        return self._embedder

    def _get_collection(self) -> Collection:
        """获取并加载 `api_catalog` collection。"""
        if self._collection is None:
            connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)
            self._collection = Collection(name=API_CATALOG_COLLECTION)
            self._collection.load()
        return self._collection

    def _get_output_fields(self) -> list[str]:
        """根据 collection 实际 schema 选择输出字段集合。

        设计意图：
            新版本使用原生 JSON 字段，但线上在重建索引前可能仍保留旧 schema。
            这里做一次读兼容，让发布顺序可以是“先发代码，后重建索引”。
        """
        field_names = {field.name for field in self._get_collection().schema.fields}
        if "api_schema" in field_names:
            return _OUTPUT_FIELDS
        return _LEGACY_OUTPUT_FIELDS

    def _get_search_param(self) -> dict[str, object]:
        """根据 collection 版本选择向量检索参数。"""
        field_names = {field.name for field in self._get_collection().schema.fields}
        if "api_schema" in field_names:
            return {"metric_type": "COSINE", "params": {"ef": 64}}
        return {"metric_type": "IP", "params": {"nprobe": 16}}

    async def search(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float | None = None,
        filters: ApiCatalogSearchFilters | dict[str, list[str]] | None = None,
        trace_id: str | None = None,
    ) -> list[ApiCatalogSearchResult]:
        """执行一次普通语义检索。"""
        query_emb = await self._encode_query(query)
        return await self._search_with_embedding(
            query=query,
            query_emb=query_emb,
            top_k=top_k,
            score_threshold=score_threshold or settings.api_query_score_threshold,
            filters=filters,
            trace_id=trace_id,
        )

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
        """按业务域并发执行分层召回。

        Args:
            query: 用户自然语言请求。
            domains: 轻量路由阶段识别出的业务域顺序列表。
            top_k: 单域场景返回的候选数。
            per_domain_top_k: 多域时每个域保底返回的候选数。
            score_threshold: 相似度阈值；为空时使用全局默认值。
            filters: 额外的标量过滤条件，例如 `status=active`。

        Returns:
            去重后的候选接口列表；多域时按输入 domain 顺序聚合。

        Edge Cases:
            - 某个 domain 超时不会拖死整条链路，只会局部丢失该域候选
            - 如果所有 domain 都失败或为空，返回空列表交给 route 层决定是否降级
        """
        normalized_domains = _dedupe_domains(domains)
        if not normalized_domains:
            return []

        threshold = score_threshold or settings.api_query_score_threshold
        logger.info(
            "stage2 stratified retrieval trace_id=%s domains=%s threshold=%.3f filters=%s top_k=%s per_domain_top_k=%s",
            trace_id or "-",
            normalized_domains,
            threshold,
            _summarize_filters(filters),
            top_k,
            per_domain_top_k,
        )
        if len(normalized_domains) == 1:
            merged_filters = _merge_filters(filters, domains=normalized_domains)
            return await self.search(
                query,
                top_k=max(1, top_k),
                score_threshold=threshold,
                filters=merged_filters,
                trace_id=trace_id,
            )

        query_emb = await self._encode_query(query)
        each_top_k = max(1, per_domain_top_k or settings.api_query_retrieval_per_domain_top_k)
        base_filters = _normalize_filters(filters)
        tasks = [
            self._search_domain_with_timeout(
                query=query,
                query_emb=query_emb,
                domain=domain,
                top_k=each_top_k,
                score_threshold=threshold,
                base_filters=base_filters,
                trace_id=trace_id,
            )
            for domain in normalized_domains
        ]
        gathered_results = await asyncio.gather(*tasks, return_exceptions=True)
        domain_results = _coerce_domain_results(normalized_domains, gathered_results)
        return _merge_stratified_results(normalized_domains, domain_results)

    async def get_by_id(self, api_id: str) -> ApiCatalogEntry | None:
        """按 id 直接获取接口记录。"""
        collection = self._get_collection()
        try:
            results = collection.query(
                expr=f'id == "{api_id}"',
                output_fields=self._get_output_fields(),
                limit=1,
            )
        except Exception as exc:
            logger.warning("api_catalog query by id failed: %s", exc)
            return None

        if not results:
            return None
        return _build_entry_from_fields(results[0])

    async def _encode_query(self, query: str) -> list[float]:
        """统一管理 query embedding，避免多域召回时重复编码。"""
        embedder = self._get_embedder()
        return await asyncio.to_thread(lambda: embedder.encode([query])["dense_vecs"][0].tolist())

    async def _search_domain_with_timeout(
        self,
        *,
        query: str,
        query_emb: list[float],
        domain: str,
        top_k: int,
        score_threshold: float,
        base_filters: ApiCatalogSearchFilters,
        trace_id: str | None = None,
    ) -> list[ApiCatalogSearchResult]:
        """为单个 domain 包一层硬超时，防止最慢域拖垮整体体验。"""
        filters = _merge_filters(base_filters, domains=[domain])
        try:
            return await asyncio.wait_for(
                self._search_with_embedding(
                    query=query,
                    query_emb=query_emb,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    filters=filters,
                    trace_id=trace_id,
                ),
                timeout=settings.api_query_retrieval_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "stage2 stratified retrieval timed out trace_id=%s domain=%s timeout_seconds=%s",
                trace_id or "-",
                domain,
                settings.api_query_retrieval_timeout_seconds,
            )
            return []

    async def _search_with_embedding(
        self,
        *,
        query: str,
        query_emb: list[float],
        top_k: int,
        score_threshold: float,
        filters: ApiCatalogSearchFilters | dict[str, list[str]] | None,
        trace_id: str | None = None,
    ) -> list[ApiCatalogSearchResult]:
        """用已生成好的 embedding 执行一次实际 Milvus 查询。"""
        collection = self._get_collection()
        expr = _build_filter_expr(filters)

        try:
            search_kwargs = {
                "data": [query_emb],
                "anns_field": "embedding",
                "param": self._get_search_param(),
                "limit": top_k + 2,
                "output_fields": self._get_output_fields(),
            }
            if expr:
                search_kwargs["expr"] = expr
            raw_results = await asyncio.to_thread(collection.search, **search_kwargs)
        except Exception as exc:
            logger.warning(
                "Milvus api_catalog search failed trace_id=%s expr=%s threshold=%.3f error=%s",
                trace_id or "-",
                expr,
                score_threshold,
                exc,
            )
            return []

        results: list[ApiCatalogSearchResult] = []
        for hit in raw_results[0]:
            score = float(hit.distance)
            # 相似度阈值是第二阶段的最后一道护栏，宁可少给候选，也不要把垃圾接口送进规划链路。
            if score < score_threshold:
                continue

            fields = {field: hit.entity.get(field) for field in _OUTPUT_FIELDS}
            results.append(ApiCatalogSearchResult(entry=_build_entry_from_fields(fields), score=score))
            if len(results) >= top_k:
                break

        logger.debug(
            "API catalog search trace_id=%s query=%s -> %d results (expr=%s, threshold=%.3f, top score=%.3f)",
            trace_id or "-",
            query[:50],
            len(results),
            expr,
            score_threshold,
            results[0].score if results else 0.0,
        )
        return results


def _build_entry_from_fields(fields: dict) -> ApiCatalogEntry:
    """从 Milvus 输出字段重建 `ApiCatalogEntry`。"""
    api_schema = _read_json_field(fields, "api_schema", "api_schema_json", {})
    response_data_path = fields.get("response_data_path") or api_schema.get("response_data_path") or "data"
    field_labels = _read_json_field(fields, "field_labels", "field_labels_json", api_schema.get("field_labels", {}))
    request_schema = api_schema.get("request", {})
    response_schema = api_schema.get("response_schema", {})
    sample_request = api_schema.get("sample_request", {})
    return ApiCatalogEntry(
        id=fields.get("id", ""),
        description=fields.get("description", ""),
        domain=fields.get("domain", "generic"),
        env=fields.get("env", "shared"),
        status=fields.get("status", "active"),
        tag_name=fields.get("tag_name") or None,
        method=fields.get("method", "GET"),
        path=fields.get("path", ""),
        auth_required=fields.get("auth_required", True),
        ui_hint=fields.get("ui_hint", "table"),
        example_queries=_read_json_field(fields, "example_queries", "example_queries_json", []),
        tags=_read_json_field(fields, "tags", "tags_json", []),
        business_intents=_read_json_field(fields, "business_intents", "business_intents_json", ["query_business_data"]),
        param_schema=ParamSchema(**(request_schema if isinstance(request_schema, dict) else {})),
        response_schema=response_schema if isinstance(response_schema, dict) else {},
        sample_request=sample_request if isinstance(sample_request, dict) else {},
        response_data_path=response_data_path,
        field_labels=field_labels if isinstance(field_labels, dict) else {},
        executor_config=_read_json_field(fields, "executor_config", "executor_config_json", {}),
        security_rules=_read_json_field(fields, "security_rules", "security_rules_json", {}),
        detail_hint=ApiCatalogDetailHint(**_read_json_field(fields, "detail_hint", "detail_hint_json", {})),
        pagination_hint=ApiCatalogPaginationHint(
            **_read_json_field(fields, "pagination_hint", "pagination_hint_json", {})
        ),
        template_hint=ApiCatalogTemplateHint(**_read_json_field(fields, "template_hint", "template_hint_json", {})),
    )


def _safe_json_loads(value, default):
    """安全反序列化 Milvus 中的 JSON 字段。"""
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _read_json_field(fields: dict, primary_name: str, legacy_name: str, default):
    """兼容读取新旧两代 schema 的 JSON 字段。"""
    if primary_name in fields:
        return _safe_json_loads(fields.get(primary_name), default)
    return _safe_json_loads(fields.get(legacy_name), default)


def _normalize_filters(
    filters: ApiCatalogSearchFilters | dict[str, list[str]] | None,
) -> ApiCatalogSearchFilters:
    """把 dict / model 两种过滤入参统一成模型对象。"""
    if filters is None:
        return ApiCatalogSearchFilters()
    if isinstance(filters, ApiCatalogSearchFilters):
        return filters
    return ApiCatalogSearchFilters(
        domains=list(filters.get("domains", [])),
        envs=list(filters.get("envs", [])),
        statuses=list(filters.get("statuses", [])),
        tag_names=list(filters.get("tag_names", [])),
    )


def _merge_filters(
    filters: ApiCatalogSearchFilters | dict[str, list[str]] | None,
    *,
    domains: list[str] | None = None,
    envs: list[str] | None = None,
    statuses: list[str] | None = None,
    tag_names: list[str] | None = None,
) -> ApiCatalogSearchFilters:
    """合并基础过滤条件与本次检索特有的标量过滤。"""
    normalized = _normalize_filters(filters)
    return ApiCatalogSearchFilters(
        domains=list(domains) if domains is not None else list(normalized.domains),
        envs=list(envs) if envs is not None else list(normalized.envs),
        statuses=list(statuses) if statuses is not None else list(normalized.statuses),
        tag_names=list(tag_names) if tag_names is not None else list(normalized.tag_names),
    )


def _build_filter_expr(filters: ApiCatalogSearchFilters | dict[str, list[str]] | None) -> str | None:
    """将标量过滤条件拼装成 Milvus 表达式。"""
    normalized = _normalize_filters(filters)
    expressions: list[str] = []
    expressions.extend(_build_in_expr("domain", normalized.domains))
    expressions.extend(_build_in_expr("env", normalized.envs))
    expressions.extend(_build_in_expr("status", normalized.statuses))
    expressions.extend(_build_in_expr("tag_name", normalized.tag_names))
    return " and ".join(expressions) if expressions else None


def _build_in_expr(field: str, values: list[str]) -> list[str]:
    """构造 `field in [...]` 形式的过滤表达式片段。"""
    filtered = [value for value in values if value]
    if not filtered:
        return []
    quoted = ", ".join(f'"{value}"' for value in filtered)
    return [f"{field} in [{quoted}]"]


def _dedupe_domains(domains: list[str]) -> list[str]:
    """保留路由顺序，并过滤掉 `unknown` 这类不可检索值。"""
    normalized: list[str] = []
    for domain in domains:
        value = (domain or "").strip()
        if not value or value == "unknown":
            continue
        if value not in normalized:
            normalized.append(value)
    return normalized


def _merge_stratified_results(
    domains: list[str],
    domain_results: list[list[ApiCatalogSearchResult]],
) -> list[ApiCatalogSearchResult]:
    """按 domain 顺序聚合召回结果，并对重复接口去重。"""
    merged: list[ApiCatalogSearchResult] = []
    seen_api_ids: set[str] = set()

    for domain, results in zip(domains, domain_results, strict=False):
        # 先在单域内按分数排序，再按 domain 顺序合并，保证“每个域至少带回代表候选”。
        sorted_results = sorted(results, key=lambda item: item.score, reverse=True)
        for result in sorted_results:
            if result.entry.id in seen_api_ids:
                continue
            seen_api_ids.add(result.entry.id)
            merged.append(result)

        if not results:
            logger.debug("API catalog stratified search returned no results for domain=%s", domain)

    return merged


def _coerce_domain_results(
    domains: list[str],
    gathered_results: list[list[ApiCatalogSearchResult] | Exception],
) -> list[list[ApiCatalogSearchResult]]:
    """将 `asyncio.gather` 结果收敛成稳定的 domain 结果列表。

    功能：
        设计文档要求第二阶段采用 Scatter-Gather 且单域失败不能拖垮整条链路。
        这里显式处理 `return_exceptions=True` 的结果，把异常域统一降级为空列表。

    Args:
        domains: 本轮检索的业务域顺序。
        gathered_results: `asyncio.gather` 返回的原始结果，可能混入异常对象。

    Returns:
        与 `domains` 顺序一一对应的结果列表；异常域会被替换为空列表。

    Edge Cases:
        - 未预期异常不会外抛到 route 层
        - 返回值不是 list 时同样视为异常退化，避免破坏后续聚合逻辑
    """
    normalized_results: list[list[ApiCatalogSearchResult]] = []

    for domain, result in zip(domains, gathered_results, strict=False):
        if isinstance(result, Exception):
            logger.warning("API catalog stratified search failed for domain=%s: %s", domain, result)
            normalized_results.append([])
            continue

        if not isinstance(result, list):
            logger.warning(
                "API catalog stratified search returned unexpected payload for domain=%s: %r",
                domain,
                result,
            )
            normalized_results.append([])
            continue

        normalized_results.append(result)

    return normalized_results


def _summarize_filters(
    filters: ApiCatalogSearchFilters | dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    """把过滤条件收敛为日志友好的轻量结构。"""
    normalized = _normalize_filters(filters)
    return {
        "domains": list(normalized.domains),
        "envs": list(normalized.envs),
        "statuses": list(normalized.statuses),
        "tag_names": list(normalized.tag_names),
    }
