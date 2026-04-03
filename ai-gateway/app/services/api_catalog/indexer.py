"""
API Catalog — Milvus 向量入库器

将 config/api_catalog.yaml 中的接口描述 embedding 后写入 Milvus `api_catalog` collection。

命令行使用::

    python -m app.services.api_catalog.indexer
    # 或指定配置文件路径
    python -m app.services.api_catalog.indexer --config /path/to/api_catalog.yaml

编程接口::

    from app.services.api_catalog.indexer import ApiCatalogIndexer
    indexer = ApiCatalogIndexer()
    await indexer.index_all()          # 全量入库
    await indexer.index_entry(entry)   # 单条入库
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import yaml
from FlagEmbedding import BGEM3FlagModel
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.core.config import settings
from app.services.api_catalog.schema import ApiCatalogEntry

logger = logging.getLogger(__name__)

# Milvus collection 名称（独立于知识库 collection，避免污染）
API_CATALOG_COLLECTION = "api_catalog"

# BGE-M3 dense vector 维度
EMBEDDING_DIM = 1024


def _get_collection_schema() -> CollectionSchema:
    """定义 api_catalog collection schema。"""
    fields = [
        FieldSchema(name="id",           dtype=DataType.VARCHAR,       max_length=128,  is_primary=True),
        FieldSchema(name="description",  dtype=DataType.VARCHAR,       max_length=1024),
        FieldSchema(name="domain",       dtype=DataType.VARCHAR,       max_length=64),
        FieldSchema(name="env",          dtype=DataType.VARCHAR,       max_length=64),
        FieldSchema(name="status",       dtype=DataType.VARCHAR,       max_length=32),
        FieldSchema(name="tag_name",     dtype=DataType.VARCHAR,       max_length=128),
        FieldSchema(name="method",       dtype=DataType.VARCHAR,       max_length=16),
        FieldSchema(name="path",         dtype=DataType.VARCHAR,       max_length=512),
        FieldSchema(name="auth_required",dtype=DataType.BOOL),
        FieldSchema(name="ui_hint",      dtype=DataType.VARCHAR,       max_length=32),
        # JSON 序列化存储复杂字段
        FieldSchema(name="example_queries_json", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="tags_json",            dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="business_intents_json",dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="param_schema_json",    dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="response_data_path",   dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="field_labels_json",    dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="executor_config_json", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="security_rules_json",  dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="detail_hint_json",     dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="pagination_hint_json", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="template_hint_json",   dtype=DataType.VARCHAR, max_length=2048),
        # 向量字段
        FieldSchema(name="embedding",    dtype=DataType.FLOAT_VECTOR,  dim=EMBEDDING_DIM),
    ]
    return CollectionSchema(fields=fields, description="Business API RAG catalog")


def _expected_field_names() -> set[str]:
    return {field.name for field in _get_collection_schema().fields}


class ApiCatalogIndexer:
    """将 API 目录写入 Milvus 向量库。"""

    def __init__(self) -> None:
        self._embedder: BGEM3FlagModel | None = None
        self._collection: Collection | None = None

    # ── 懒加载 ──────────────────────────────────────────────────

    def _get_embedder(self) -> BGEM3FlagModel:
        if self._embedder is None:
            logger.info("Loading embedding model: %s", settings.embedding_model_name)
            self._embedder = BGEM3FlagModel(settings.embedding_model_name, use_fp16=True)
        return self._embedder

    def _get_collection(self) -> Collection:
        if self._collection is None:
            connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)
            if not utility.has_collection(API_CATALOG_COLLECTION):
                logger.info("Creating Milvus collection: %s", API_CATALOG_COLLECTION)
                col = _create_collection()
            else:
                col = Collection(name=API_CATALOG_COLLECTION)
                actual_fields = {field.name for field in col.schema.fields}
                if actual_fields != _expected_field_names():
                    logger.info("Recreating Milvus collection %s due to schema drift", API_CATALOG_COLLECTION)
                    col.release()
                    utility.drop_collection(API_CATALOG_COLLECTION)
                    col = _create_collection()
                else:
                    col.load()
            self._collection = col
        return self._collection

    # ── 公共 API ────────────────────────────────────────────────

    async def index_all(self, config_path: str | None = None) -> dict[str, int]:
        """从 YAML 配置文件全量入库。

        Returns:
            {"indexed": N, "skipped": M}
        """
        path = Path(config_path or _default_config_path())
        if not path.exists():
            raise FileNotFoundError(f"api_catalog.yaml 不存在: {path}")

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        entries = [ApiCatalogEntry(**item) for item in raw.get("apis", [])]
        logger.info("Loaded %d API entries from %s", len(entries), path)

        results = await asyncio.gather(*[self.index_entry(e) for e in entries], return_exceptions=True)
        indexed = sum(1 for r in results if r is True)
        skipped = sum(1 for r in results if isinstance(r, Exception))
        if skipped:
            for entry, r in zip(entries, results):
                if isinstance(r, Exception):
                    logger.warning("Failed to index %s: %s", entry.id, r)

        logger.info("API Catalog indexed: %d OK, %d failed", indexed, skipped)
        return {"indexed": indexed, "skipped": skipped}

    async def index_entry(self, entry: ApiCatalogEntry) -> bool:
        """对单条 API 目录记录做 embedding 并写入 Milvus。"""
        embedder = self._get_embedder()
        collection = self._get_collection()

        # Embedding（在线程池中执行 CPU 密集型操作）
        embed_text = entry.embed_text
        embedding: list[float] = await asyncio.to_thread(
            lambda: embedder.encode([embed_text])["dense_vecs"][0].tolist()
        )

        # 先删除同 ID 的旧记录（upsert 语义）
        collection.delete(f'id in ["{entry.id}"]')

        # 准备插入数据
        data = [
            [entry.id],
            [entry.description],
            [entry.domain],
            [entry.env],
            [entry.status],
            [entry.tag_name or ""],
            [entry.method],
            [entry.path],
            [entry.auth_required],
            [entry.ui_hint],
            [json.dumps(entry.example_queries, ensure_ascii=False)],
            [json.dumps(entry.tags, ensure_ascii=False)],
            [json.dumps(entry.business_intents, ensure_ascii=False)],
            [json.dumps(entry.param_schema.model_dump(), ensure_ascii=False)],
            [entry.response_data_path],
            [json.dumps(entry.field_labels, ensure_ascii=False)],
            [json.dumps(entry.executor_config, ensure_ascii=False)],
            [json.dumps(entry.security_rules, ensure_ascii=False)],
            [json.dumps(entry.detail_hint.model_dump(), ensure_ascii=False)],
            [json.dumps(entry.pagination_hint.model_dump(), ensure_ascii=False)],
            [json.dumps(entry.template_hint.model_dump(), ensure_ascii=False)],
            [embedding],
        ]
        collection.insert(data)
        collection.flush()
        logger.debug("Indexed API entry: %s → %s %s", entry.id, entry.method, entry.path)
        return True


def _default_config_path() -> str:
    return str(Path(__file__).resolve().parents[4] / "config" / "api_catalog.yaml")


def _create_collection() -> Collection:
    collection = Collection(name=API_CATALOG_COLLECTION, schema=_get_collection_schema())
    collection.create_index(
        field_name="embedding",
        index_params={"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 128}},
    )
    collection.load()
    return collection


# ── CLI 入口 ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Index API catalog into Milvus")
    parser.add_argument("--config", default=None, help="Path to api_catalog.yaml")
    args = parser.parse_args()

    async def main():
        indexer = ApiCatalogIndexer()
        result = await indexer.index_all(args.config)
        print(f"Done: {result}")

    asyncio.run(main())
