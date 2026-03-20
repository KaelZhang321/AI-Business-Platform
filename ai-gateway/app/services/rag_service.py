from __future__ import annotations

import asyncio
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
        self._neo4j_driver = None
        self._embedding_model: BGEM3FlagModel | None = None
        self._reranker: FlagReranker | None = None
        self._clickhouse_engine: AsyncEngine | None = None

    # --- lazy clients -------------------------------------------------
    def _milvus(self) -> Collection:
        if self._milvus_collection is None:
            connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)
            self._milvus_collection = Collection(settings.milvus_collection)
        return self._milvus_collection

    def _es_client(self) -> AsyncElasticsearch:
        if self._es is None:
            self._es = AsyncElasticsearch(settings.elasticsearch_url)
        return self._es

    def _neo4j_driver(self):
        if self._neo4j_driver is None:
            self._neo4j_driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._neo4j_driver

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
    async def search(self, query: str, top_k: int = 5, doc_types: list[str] | None = None) -> list[KnowledgeResult]:
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

        merged = self._fuse_results(
            vector_results,
            keyword_results,
            graph_results,
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
        driver = self._neo4j_driver()
        cypher = """
        CALL db.index.fulltext.queryNodes('knowledge_index', $query)
        YIELD node, score
        RETURN node.doc_id AS doc_id, node.title AS title, node.summary AS content,
               node.type AS doc_type, node.metadata AS metadata, score
        LIMIT 20
        """
        records: list[KnowledgeResult] = []
        async with driver.session() as session:
            result = await session.run(cypher, query=query)
            async for record in result:
                records.append(
                    KnowledgeResult(
                        doc_id=record["doc_id"],
                        title=record["title"],
                        content=record["content"],
                        score=float(record["score"]),
                        doc_type=record["doc_type"] or "graph",
                        metadata=record.get("metadata") or {},
                    )
                )
        return records

    # --- fusion & rerank ----------------------------------------------
    def _fuse_results(
        self,
        vector_results: list[KnowledgeResult],
        keyword_results: list[KnowledgeResult],
        graph_results: list[KnowledgeResult],
    ) -> list[KnowledgeResult]:
        score_map: dict[str, KnowledgeResult] = {}
        fused_scores: dict[str, float] = {}

        def update(results: list[KnowledgeResult], weight: float):
            for rank, doc in enumerate(results):
                doc_id = doc.doc_id
                if doc_id not in score_map:
                    score_map[doc_id] = doc
                fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + weight / (rank + 1)

        update(vector_results, settings.rag_vector_weight)
        update(keyword_results, settings.rag_keyword_weight)
        update(graph_results, settings.rag_graph_weight)

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
        engine = self._clickhouse()
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
        async with engine.begin() as conn:
            await conn.execute(stmt, payload)
*** End File
