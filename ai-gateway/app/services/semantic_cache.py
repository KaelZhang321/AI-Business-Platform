"""
语义缓存服务 — 基于 Milvus 向量相似度的 RAG 结果缓存。

流程：
1. 用户问题 → Embedding → 在 semantic_cache Collection 中检索
2. 相似度 > threshold → 命中，直接返回缓存的 answer + sources
3. 未命中 → 走正常 RAG+LLM 流程 → 回写缓存
4. 知识库更新时通过 cache.invalidation 队列触发全量/分类失效
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    utility,
)

from app.core.config import settings
from app.core.model_source import resolve_model_source

logger = logging.getLogger(__name__)


@dataclass
class CacheHit:
    """语义缓存命中结果。"""

    answer: str
    sources: list[dict]
    ui_spec: dict | None
    similarity: float


class SemanticCacheService:
    """Milvus 向量语义缓存。"""

    COLLECTION_NAME = "semantic_cache"
    EMBEDDING_DIM = 1024  # BGE-M3 默认维度

    def __init__(self) -> None:
        self._collection: Collection | None = None
        self._embedding_model = None

    def _ensure_collection(self) -> Collection:
        """确保 semantic_cache Collection 存在，不存在则创建。"""
        if self._collection is not None:
            return self._collection

        # 复用 RAGService 已建立的连接（lifespan 中已 connect）
        if not utility.has_collection(self.COLLECTION_NAME):
            schema = CollectionSchema(
                fields=[
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
                    FieldSchema(name="question_hash", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=2000),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.EMBEDDING_DIM),
                    FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="sources_json", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="ui_spec_json", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="kb_version", dtype=DataType.INT64),
                    FieldSchema(name="created_at", dtype=DataType.INT64),
                ],
                description="语义缓存：存储 RAG 问答对的向量索引",
            )
            collection = Collection(name=self.COLLECTION_NAME, schema=schema)
            collection.create_index(
                field_name="embedding",
                index_params={"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 128}},
            )
            logger.info("Milvus collection '%s' 创建成功", self.COLLECTION_NAME)
        else:
            collection = Collection(name=self.COLLECTION_NAME)

        collection.load()
        self._collection = collection
        return collection

    def _get_embedder(self):
        """复用 BGE-M3 Embedding 模型（懒加载）。

        功能：
            语义缓存和主检索链路必须使用同一份模型来源，否则缓存向量与查询向量分布漂移后，
            命中率会无缘无故下降。这里统一走本地目录优先，保证离线部署下的向量空间稳定。
        """
        if self._embedding_model is None:
            from flagembedding import BGEM3FlagModel

            model_source = resolve_model_source(
                model_name=settings.embedding_model_name,
                local_model_path=settings.embedding_model_path,
            )
            if model_source.source_kind == "local_path":
                logger.info("Loading semantic cache embedding model from local path: %s", model_source.source)
            elif model_source.configured_path:
                logger.warning(
                    "Configured EMBEDDING_MODEL_PATH is unavailable, fallback to EMBEDDING_MODEL_NAME: path=%s model=%s",
                    model_source.configured_path,
                    settings.embedding_model_name,
                )
            self._embedding_model = BGEM3FlagModel(model_source.source, use_fp16=True)
        return self._embedding_model

    def _embed(self, text: str) -> list[float]:
        """生成文本向量。"""
        embedder = self._get_embedder()
        result = embedder.encode([text])
        # BGE-M3 encode 返回 dict 或 ndarray，取 dense_vecs
        if isinstance(result, dict):
            return result["dense_vecs"][0].tolist()
        return result[0].tolist()

    @staticmethod
    def _question_hash(question: str) -> str:
        return hashlib.sha256(question.strip().lower().encode()).hexdigest()[:32]

    async def lookup(self, question: str) -> CacheHit | None:
        """
        在语义缓存中查找相似问题。

        返回 CacheHit（命中）或 None（未命中）。
        """
        if not settings.semantic_cache_enabled:
            return None

        try:
            collection = self._ensure_collection()
            query_emb = self._embed(question)

            results = collection.search(
                data=[query_emb],
                anns_field="embedding",
                param={"metric_type": "IP", "params": {"nprobe": 10}},
                limit=1,
                output_fields=["answer", "sources_json", "ui_spec_json", "kb_version", "created_at"],
            )

            if not results or not results[0]:
                return None

            hit = results[0][0]
            similarity = float(hit.distance)

            if similarity < settings.semantic_cache_similarity_threshold:
                logger.debug("语义缓存未命中: similarity=%.4f < threshold=%.2f", similarity, settings.semantic_cache_similarity_threshold)
                return None

            # TTL 检查
            field_data = hit.entity.get("_row_data", {})
            created_at = field_data.get("created_at", 0)
            ttl_seconds = settings.semantic_cache_ttl_hours * 3600
            if created_at > 0 and (time.time() - created_at) > ttl_seconds:
                logger.debug("语义缓存过期: age=%ds > ttl=%ds", int(time.time() - created_at), ttl_seconds)
                return None

            answer = field_data.get("answer", "")
            sources_raw = field_data.get("sources_json", "[]")
            ui_spec_raw = field_data.get("ui_spec_json", "")

            sources = json.loads(sources_raw) if sources_raw else []
            ui_spec = json.loads(ui_spec_raw) if ui_spec_raw else None

            logger.info("语义缓存命中: similarity=%.4f, question='%s'", similarity, question[:50])
            return CacheHit(answer=answer, sources=sources, ui_spec=ui_spec, similarity=similarity)

        except Exception as exc:
            logger.warning("语义缓存查找失败: %s", exc)
            return None

    async def store(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        ui_spec: dict | None = None,
        kb_version: int = 0,
    ) -> None:
        """将问答对写入语义缓存。"""
        if not settings.semantic_cache_enabled:
            return

        try:
            collection = self._ensure_collection()
            query_emb = self._embed(question)
            q_hash = self._question_hash(question)
            now = int(time.time())
            cache_id = f"sc_{q_hash}_{now}"

            # 删除同一问题的旧缓存（基于 question_hash）
            try:
                collection.delete(expr=f'question_hash == "{q_hash}"')
            except Exception:
                pass

            # 容量管理：超过上限时删除最旧条目
            if collection.num_entities >= settings.semantic_cache_max_size:
                self._evict_oldest(collection)

            sources_json = json.dumps(sources, ensure_ascii=False)[:65000]
            ui_spec_json = json.dumps(ui_spec, ensure_ascii=False)[:65000] if ui_spec else ""

            collection.insert([
                [cache_id],
                [q_hash],
                [question[:2000]],
                [query_emb],
                [answer[:65000]],
                [sources_json],
                [ui_spec_json],
                [kb_version],
                [now],
            ])
            collection.flush()
            logger.info("语义缓存已写入: question='%s'", question[:50])

        except Exception as exc:
            logger.warning("语义缓存写入失败: %s", exc)

    def invalidate(self, kb_version: int | None = None) -> int:
        """
        清除语义缓存。

        kb_version 指定则仅清除该版本，否则清除全部。
        返回清除的条目数（近似值）。
        """
        try:
            collection = self._ensure_collection()
            before = collection.num_entities

            if kb_version is not None:
                collection.delete(expr=f"kb_version == {kb_version}")
            else:
                # 全量清除：drop + recreate
                collection.drop()
                self._collection = None
                self._ensure_collection()

            after = self._collection.num_entities if self._collection else 0
            cleared = max(before - after, 0)
            logger.info("语义缓存已失效: cleared=%d, kb_version=%s", cleared, kb_version)
            return cleared

        except Exception as exc:
            logger.warning("语义缓存失效操作失败: %s", exc)
            return 0

    @staticmethod
    def _evict_oldest(collection: Collection, batch: int = 100) -> None:
        """删除最旧的 batch 条缓存。"""
        try:
            results = collection.query(
                expr="created_at > 0",
                output_fields=["id", "created_at"],
                limit=batch,
            )
            if results:
                results.sort(key=lambda r: r.get("created_at", 0))
                ids = [r["id"] for r in results[:batch]]
                if ids:
                    id_list = ", ".join(f'"{i}"' for i in ids)
                    collection.delete(expr=f"id in [{id_list}]")
        except Exception as exc:
            logger.debug("语义缓存淘汰失败: %s", exc)
