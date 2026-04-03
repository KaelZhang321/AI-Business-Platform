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
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult, ParamSchema

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
            "id", "description", "method", "path", "auth_required", "ui_hint",
            "example_queries_json", "tags_json", "param_schema_json",
            "response_data_path", "field_labels_json",
        ]

        try:
            raw_results = collection.search(
                data=[query_emb],
                anns_field="embedding",
                param={"metric_type": "IP", "params": {"nprobe": 16}},
                limit=top_k + 2,  # 多取几条，过滤后保证 top_k
                output_fields=output_fields,
            )
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
            "id", "description", "method", "path", "auth_required", "ui_hint",
            "example_queries_json", "tags_json", "param_schema_json",
            "response_data_path", "field_labels_json",
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
        method=fields.get("method", "GET"),
        path=fields.get("path", ""),
        auth_required=fields.get("auth_required", True),
        ui_hint=fields.get("ui_hint", "table"),
        example_queries=_safe_json_loads(fields.get("example_queries_json"), []),
        tags=_safe_json_loads(fields.get("tags_json"), []),
        param_schema=ParamSchema(**_safe_json_loads(fields.get("param_schema_json"), {})),
        response_data_path=fields.get("response_data_path", "data"),
        field_labels=_safe_json_loads(fields.get("field_labels_json"), {}),
    )


def _safe_json_loads(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
