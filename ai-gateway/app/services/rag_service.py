from __future__ import annotations

import asyncio
import logging

from elasticsearch import AsyncElasticsearch
from flagembedding import BGEM3FlagModel, FlagReranker
from neo4j import AsyncGraphDatabase
from pymilvus import Collection, connections
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings
from app.models.schemas import KnowledgeResult


class RAGService:
    """GraphRAG检索服务：Milvus + Elasticsearch + Neo4j + BGE-Reranker."""

    def __init__(self):
        self._milvus_collection: Collection | None = None
        self._es: AsyncElasticsearch | None = None
        self._neo4j = None
        self._embedding_model: BGEM3FlagModel | None = None
        self._reranker: FlagReranker | None = None
        self._clickhouse_engine: AsyncEngine | None = None
        self._logger = logging.getLogger(__name__)

    # --- lazy clients -------------------------------------------------
    def _milvus(self) -> Collection:
        if self._milvus_collection is None:
            connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)
            self._milvus_collection = Collection(settings.milvus_collection)
        return self._milvus_collection

    def _es_client(self) -> AsyncElasticsearch:
        if self._es is None:
            self._es = AsyncElasticsearch(
                settings.elasticsearch_url,
                basic_auth=(settings.elasticsearch_username, settings.elasticsearch_password),
            )
        return self._es

    def _neo4j_client(self):
        if self._neo4j is None:
            self._neo4j = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._neo4j

    def _embedder(self) -> BGEM3FlagModel:
        if self._embedding_model is None:
            self._embedding_model = BGEM3FlagModel(settings.embedding_model_name, use_fp16=True)
        return self._embedding_model

    def _reranker_model(self) -> FlagReranker:
        if self._reranker is None:
            self._reranker = FlagReranker(settings.reranker_model_name, use_fp16=True)
        return self._reranker

    def _clickhouse(self) -> AsyncEngine:
        if self._clickhouse_engine is None:
            self._clickhouse_engine = create_async_engine(settings.clickhouse_url, pool_pre_ping=True, echo=False)
        return self._clickhouse_engine

    # --- public API ---------------------------------------------------
    # 意图自适应权重配比
    _INTENT_WEIGHTS: dict[str, tuple[float, float, float]] = {
        # (向量, 关键词, 图谱)
        "FACTUAL": (0.3, 0.5, 0.2),       # 事实性问题：侧重关键词精确匹配
        "RELATIONAL": (0.2, 0.2, 0.6),    # 关系性问题：侧重图谱实体关系
        "REASONING": (0.5, 0.2, 0.3),     # 推理性问题：侧重语义向量
    }

    async def search(
        self, query: str, top_k: int = 5, doc_types: list[str] | None = None, query_type: str | None = None,
    ) -> list[KnowledgeResult]:
        """并行执行向量、关键词、图谱检索并融合排序，并记录指标。"""
        vector_task = asyncio.create_task(self._vector_search(query, doc_types))
        keyword_task = asyncio.create_task(self._keyword_search(query, doc_types))
        graph_task = asyncio.create_task(self._graph_search(query))

        vector_results, keyword_results, graph_results = await asyncio.gather(
            vector_task,
            keyword_task,
            graph_task,
            return_exceptions=False,
        )

        # 意图自适应权重选择
        weights = self._INTENT_WEIGHTS.get(query_type or "", None)

        merged = self._fuse_results(
            vector_results,
            keyword_results,
            graph_results,
            weights=weights,
        )
        reranked = await self._rerank(query, merged, top_k=top_k)
        await self._record_metrics(query, vector_results, keyword_results, graph_results, reranked)
        return reranked

    # --- search backends ----------------------------------------------
    async def _vector_search(self, query: str, doc_types: list[str] | None) -> list[KnowledgeResult]:
        embedder = self._embedder()
        query_emb = embedder.encode([query])[0]
        collection = self._milvus()
        results = collection.search(
            data=[query_emb],
            anns_field=settings.milvus_vector_field,
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=settings.milvus_search_limit,
            output_fields=settings.milvus_output_fields,
            expr=self._build_doc_type_expr(doc_types),
        )
        hits: list[KnowledgeResult] = []
        for hit in results[0]:
            field_data = hit.entity.get("_row_data", {})
            hits.append(
                KnowledgeResult(
                    doc_id=field_data.get("doc_id", str(hit.id)),
                    title=field_data.get("title", ""),
                    content=field_data.get("content", ""),
                    score=float(hit.distance),
                    doc_type=field_data.get("doc_type", "unknown"),
                    metadata=field_data.get("metadata", {}),
                )
            )
        return hits

    async def _keyword_search(self, query: str, doc_types: list[str] | None) -> list[KnowledgeResult]:
        es = self._es_client()
        must = [{"multi_match": {"query": query, "fields": ["title^2", "content"]}}]
        if doc_types:
            must.append({"terms": {"doc_type": doc_types}})
        response = await es.search(
            index=settings.elasticsearch_index,
            query={"bool": {"must": must}},
            size=settings.milvus_search_limit,
        )
        hits: list[KnowledgeResult] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            hits.append(
                KnowledgeResult(
                    doc_id=hit.get("_id"),
                    title=source.get("title", ""),
                    content=source.get("content", ""),
                    score=float(hit.get("_score", 0.0)),
                    doc_type=source.get("doc_type", "unknown"),
                    metadata=source.get("metadata", {}),
                )
            )
        return hits

    async def _graph_search(self, query: str) -> list[KnowledgeResult]:
        driver = self._neo4j_client()
        records: list[KnowledgeResult] = []

        # 1) 全文索引检索（通用知识）
        fulltext_cypher = """
        CALL db.index.fulltext.queryNodes('knowledge_index', $query)
        YIELD node, score
        RETURN labels(node)[0] AS label, node.name AS title, node.description AS content, score
        LIMIT 10
        """
        # 2) 实体关系查询（医疗图谱：疾病→症状/药物/检查）
        relation_cypher = """
        MATCH (n)
        WHERE any(lbl IN labels(n) WHERE lbl IN ['Disease','Medicine','Symptom','Examination'])
          AND toLower(n.name) CONTAINS toLower($query)
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN n.name AS entity, labels(n)[0] AS entity_type,
               type(r) AS rel, m.name AS related, labels(m)[0] AS related_type,
               r.reason AS reason, r.severity AS severity
        LIMIT 20
        """
        try:
            async with driver.session() as session:
                # 全文检索
                result = await session.run(fulltext_cypher, query=query)
                async for rec in result:
                    records.append(KnowledgeResult(
                        doc_id=f"graph:{rec['label']}:{rec['title']}",
                        title=rec["title"] or "",
                        content=rec["content"] or "",
                        score=float(rec["score"]),
                        doc_type="graph",
                        metadata={"source": "fulltext"},
                    ))

                # 实体关系
                result2 = await session.run(relation_cypher, query=query)
                seen = set()
                async for rec in result2:
                    entity = rec["entity"]
                    rel = rec["rel"]
                    related = rec["related"]
                    if not rel or not related:
                        continue
                    key = f"{entity}-{rel}-{related}"
                    if key in seen:
                        continue
                    seen.add(key)
                    reason = rec.get("reason") or ""
                    content = f"{entity} —[{rel}]→ {related}"
                    if reason:
                        content += f"（{reason}）"
                    records.append(KnowledgeResult(
                        doc_id=f"graph:rel:{key}",
                        title=f"{entity} → {related}",
                        content=content,
                        score=0.8,
                        doc_type="graph",
                        metadata={"relation": rel, "severity": rec.get("severity") or ""},
                    ))
        except Exception as exc:
            self._logger.warning("Graph search failed: %s", exc)

        return records

    # --- fusion & rerank ----------------------------------------------
    def _fuse_results(
        self,
        vector_results: list[KnowledgeResult],
        keyword_results: list[KnowledgeResult],
        graph_results: list[KnowledgeResult],
        weights: tuple[float, float, float] | None = None,
    ) -> list[KnowledgeResult]:
        w_vec, w_kw, w_graph = weights or (
            settings.rag_vector_weight, settings.rag_keyword_weight, settings.rag_graph_weight,
        )
        score_map: dict[str, KnowledgeResult] = {}
        fused_scores: dict[str, float] = {}

        def update(results: list[KnowledgeResult], weight: float):
            for rank, doc in enumerate(results):
                doc_id = doc.doc_id
                if doc_id not in score_map:
                    score_map[doc_id] = doc
                fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + weight / (rank + 1)

        update(vector_results, w_vec)
        update(keyword_results, w_kw)
        update(graph_results, w_graph)

        merged = sorted(score_map.items(), key=lambda item: fused_scores[item[0]], reverse=True)
        return [doc for _, doc in merged]

    async def _rerank(self, query: str, results: list[KnowledgeResult], top_k: int) -> list[KnowledgeResult]:
        reranker = self._reranker_model()
        pairs = [[query, doc.content] for doc in results[: settings.rag_rerank_limit]]
        if not pairs:
            return []
        scores = reranker.compute_score(pairs)
        reranked = list(zip(results[: settings.rag_rerank_limit], scores))
        reranked.sort(key=lambda item: item[1], reverse=True)
        final = []
        for doc, score in reranked[:top_k]:
            final.append(
                KnowledgeResult(
                    doc_id=doc.doc_id,
                    title=doc.title,
                    content=doc.content,
                    score=float(score),
                    doc_type=doc.doc_type,
                    metadata={**doc.metadata, "rerank_score": float(score)},
                )
            )
        return final

    @staticmethod
    def _build_doc_type_expr(doc_types: list[str] | None) -> str | None:
        if not doc_types:
            return None
        quoted = ",".join(f"'{doc_type}'" for doc_type in doc_types)
        return f"doc_type in [{quoted}]"

    async def _record_metrics(
        self,
        query: str,
        vector_results: list[KnowledgeResult],
        keyword_results: list[KnowledgeResult],
        graph_results: list[KnowledgeResult],
        reranked: list[KnowledgeResult],
    ) -> None:
        payload = {
            "query": query,
            "vector_hit": len(vector_results),
            "keyword_hit": len(keyword_results),
            "graph_hit": len(graph_results),
            "final_count": len(reranked),
            "top_ids": [doc.doc_id for doc in reranked],
        }
        stmt = text(
            f"INSERT INTO {settings.clickhouse_rag_table} (query, vector_hit, keyword_hit, graph_hit, final_count, top_ids) "
            "VALUES (:query, :vector_hit, :keyword_hit, :graph_hit, :final_count, :top_ids)"
        )
        try:
            engine = self._clickhouse()
            async with engine.begin() as conn:
                await conn.execute(stmt, payload)
        except Exception as exc:  # pragma: no cover - telemetry failures shouldn't break user flow
            self._logger.warning("Failed to record RAG metrics: %s", exc)

    async def close(self) -> None:
        """释放所有外部连接资源，由 FastAPI lifespan 在关闭时调用。"""
        if self._es:
            await self._es.close()
            self._logger.info("RAGService: Elasticsearch 客户端已关闭")
        if self._neo4j:
            await self._neo4j.close()
            self._logger.info("RAGService: Neo4j 驱动已关闭")
        if self._clickhouse_engine:
            await self._clickhouse_engine.dispose()
            self._logger.info("RAGService: ClickHouse 引擎已释放")
