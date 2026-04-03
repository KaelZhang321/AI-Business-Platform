"""
API Catalog — 语义检索器

给定用户自然语言查询，在 Milvus `api_catalog` collection 中
找到最匹配的业务接口列表（Top-K）。

使用方式::

    from app.services.api_catalog.retriever import ApiCatalogRetriever

    retriever = ApiCatalogRetriever()
    results = await retriever.search("查询我名下的所有客户信息", top_k=3)
    for r in results:
        print(r.score, r.entry.id, r.entry.path)
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


class ApiCatalogRetriever:
    """从 Milvus api_catalog collection 检索最匹配的业务接口。"""

    def __init__(self) -> None:
        self._embedder: BGEM3FlagModel | None = None
        self._collection: Collection | None = None

    # ── 懒加载 ─────────────────────────────────────────────────

    def _get_embedder(self) -> BGEM3FlagModel:
        if self._embedder is None:
            self._embedder = BGEM3FlagModel(settings.embedding_model_name, use_fp16=True)
        return self._embedder

    def _get_collection(self) -> Collection:
        if self._collection is None:
            connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)
            self._collection = Collection(name=API_CATALOG_COLLECTION)
            self._collection.load()
        return self._collection

    # ── 公共 API ────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float = 0.3,
        filters: ApiCatalogSearchFilters | dict[str, list[str]] | None = None,
    ) -> list[ApiCatalogSearchResult]:
        """
        对用户自然语言查询做语义检索，返回 Top-K 候选接口。

        Args:
            query: 用户输入，如"查询我名下的客户"
            top_k: 返回候选数量（建议 3，传给 LLM Router 做二次选择）
            score_threshold: 最低相似度阈值，低于此分数的结果过滤掉

        Returns:
            List[ApiCatalogSearchResult]: 按相似度降序排列
        """
        embedder = self._get_embedder()
        query_emb: list[float] = await asyncio.to_thread(
            lambda: embedder.encode([query])["dense_vecs"][0].tolist()
        )

        collection = self._get_collection()
        output_fields = [
            "id", "description", "domain", "env", "status", "tag_name",
            "method", "path", "auth_required", "ui_hint",
            "example_queries_json", "tags_json", "business_intents_json",
            "param_schema_json", "response_data_path", "field_labels_json",
            "executor_config_json", "security_rules_json",
            "detail_hint_json", "pagination_hint_json", "template_hint_json",
        ]
        expr = _build_filter_expr(filters)

        try:
            search_kwargs = {
                "data": [query_emb],
                "anns_field": "embedding",
                "param": {"metric_type": "IP", "params": {"nprobe": 16}},
                "limit": top_k + 2,
                "output_fields": output_fields,
            }
            if expr:
                search_kwargs["expr"] = expr
            raw_results = collection.search(**search_kwargs)
        except Exception as exc:
            logger.warning("Milvus api_catalog search failed: %s", exc)
            return []

        results: list[ApiCatalogSearchResult] = []
        for hit in raw_results[0]:
            score = float(hit.distance)
            if score < score_threshold:
                continue

            fields = {f: hit.entity.get(f) for f in output_fields}
            entry = _build_entry_from_fields(fields)
            results.append(ApiCatalogSearchResult(entry=entry, score=score))

            if len(results) >= top_k:
                break

        logger.debug(
            "API catalog search '%s' → %d results (top score: %.3f)",
            query[:50],
            len(results),
            results[0].score if results else 0.0,
        )
        return results

    async def get_by_id(self, api_id: str) -> ApiCatalogEntry | None:
        """按 id 直接获取接口记录（用于二次调用确认）。"""
        collection = self._get_collection()
        output_fields = [
            "id", "description", "domain", "env", "status", "tag_name",
            "method", "path", "auth_required", "ui_hint",
            "example_queries_json", "tags_json", "business_intents_json",
            "param_schema_json", "response_data_path", "field_labels_json",
            "executor_config_json", "security_rules_json",
            "detail_hint_json", "pagination_hint_json", "template_hint_json",
        ]
        try:
            results = collection.query(
                expr=f'id == "{api_id}"',
                output_fields=output_fields,
                limit=1,
            )
        except Exception as exc:
            logger.warning("api_catalog query by id failed: %s", exc)
            return None

        if not results:
            return None
        return _build_entry_from_fields(results[0])


def _build_entry_from_fields(fields: dict) -> ApiCatalogEntry:
    """从 Milvus 返回的原始字段构建 ApiCatalogEntry。"""
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
        example_queries=_safe_json_loads(fields.get("example_queries_json"), []),
        tags=_safe_json_loads(fields.get("tags_json"), []),
        business_intents=_safe_json_loads(fields.get("business_intents_json"), ["query_business_data"]),
        param_schema=ParamSchema(**_safe_json_loads(fields.get("param_schema_json"), {})),
        response_data_path=fields.get("response_data_path", "data"),
        field_labels=_safe_json_loads(fields.get("field_labels_json"), {}),
        executor_config=_safe_json_loads(fields.get("executor_config_json"), {}),
        security_rules=_safe_json_loads(fields.get("security_rules_json"), {}),
        detail_hint=ApiCatalogDetailHint(**_safe_json_loads(fields.get("detail_hint_json"), {})),
        pagination_hint=ApiCatalogPaginationHint(**_safe_json_loads(fields.get("pagination_hint_json"), {})),
        template_hint=ApiCatalogTemplateHint(**_safe_json_loads(fields.get("template_hint_json"), {})),
    )


def _safe_json_loads(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _build_filter_expr(filters: ApiCatalogSearchFilters | dict[str, list[str]] | None) -> str | None:
    if filters is None:
        return None
    if isinstance(filters, dict):
        normalized = ApiCatalogSearchFilters(
            domains=list(filters.get("domains", [])),
            envs=list(filters.get("envs", [])),
            statuses=list(filters.get("statuses", [])),
            tag_names=list(filters.get("tag_names", [])),
        )
    else:
        normalized = filters

    expressions: list[str] = []
    expressions.extend(_build_in_expr("domain", normalized.domains))
    expressions.extend(_build_in_expr("env", normalized.envs))
    expressions.extend(_build_in_expr("status", normalized.statuses))
    expressions.extend(_build_in_expr("tag_name", normalized.tag_names))
    return " and ".join(expressions) if expressions else None


def _build_in_expr(field: str, values: list[str]) -> list[str]:
    filtered = [value for value in values if value]
    if not filtered:
        return []
    quoted = ", ".join(f'"{value}"' for value in filtered)
    return [f"{field} in [{quoted}]"]
