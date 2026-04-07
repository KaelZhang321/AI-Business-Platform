"""
API Catalog — Milvus 向量入库器

将业务接口注册表 embedding 后写入 Milvus `api_catalog` collection。

命令行使用::

    python -m app.services.api_catalog.indexer

编程接口::

    from app.services.api_catalog.indexer import ApiCatalogIndexer
    indexer = ApiCatalogIndexer()
    await indexer.index_all()          # 全量入库
    await indexer.index_entry(entry)   # 单条入库
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from typing import TYPE_CHECKING

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.core.config import settings
from app.core.model_source import resolve_model_source
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_catalog.schema import ApiCatalogEntry

if TYPE_CHECKING:
    from FlagEmbedding import BGEM3FlagModel

logger = logging.getLogger(__name__)

# Milvus collection 名称（独立于知识库 collection，避免污染）
API_CATALOG_COLLECTION = "api_catalog"

# BGE-M3 dense vector 维度
EMBEDDING_DIM = 1024

# 这里故意使用一个极短的稳定文本做 warmup，而不是空字符串。
# 原因不是“求语义准确”，而是强制触发底层 embedding runtime 的首次真实 encode，
# 让它把线程池 / native runtime / 可能的子进程初始化都消耗在 Milvus gRPC 建连之前。
_EMBEDDING_WARMUP_TEXT = "api catalog warmup"


def _get_collection_schema() -> CollectionSchema:
    """定义 `api_catalog` 的 Milvus schema。

    功能：
        同时保留向量检索字段和少量标量护栏，让第二阶段可以做 Hybrid Search。
        复杂结构改用 Milvus 原生 JSON 字段，避免网关长期维护一层“JSON 字符串协议”。
    """
    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            max_length=128,
            is_primary=True,
            description="接口注册表主键，对齐 ui_api_endpoints.id，用于增量更新和精确命中。",
        ),
        FieldSchema(
            name="description",
            dtype=DataType.VARCHAR,
            max_length=1024,
            description="给 embedding 使用的人类可读语义串，通常拼接域、标签、接口名和摘要。",
        ),
        FieldSchema(
            name="domain",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="业务域隔离带，如 crm / iam / erp，供第二阶段分层召回做标量过滤。",
        ),
        FieldSchema(
            name="env",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="环境标识，如 dev / test / prod，避免跨环境召回污染线上请求。",
        ),
        FieldSchema(
            name="status",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="接口状态护栏，仅允许 active 等可用接口参与召回。",
        ),
        FieldSchema(
            name="tag_name",
            dtype=DataType.VARCHAR,
            max_length=128,
            description="更稳定的一级业务标签，辅助细粒度过滤和 Prompt 语义压缩。",
        ),
        FieldSchema(
            name="method",
            dtype=DataType.VARCHAR,
            max_length=16,
            description="HTTP 方法，用于在规划和执行阶段硬拦截非只读接口。",
        ),
        FieldSchema(
            name="path",
            dtype=DataType.VARCHAR,
            max_length=512,
            description="真实接口路径，是第三阶段白名单校验和第四阶段执行的物理锚点。",
        ),
        FieldSchema(
            name="auth_required",
            dtype=DataType.BOOL,
            description="标记调用该接口是否需要透传用户凭证，避免匿名误调受保护接口。",
        ),
        FieldSchema(
            name="ui_hint",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="渲染倾向提示，如 table / detail / form，帮助第五阶段快速选组件原语。",
        ),
        FieldSchema(
            name="example_queries",
            dtype=DataType.JSON,
            description="少量高质量示例问法，给召回和 Prompt 解释层提供辅助语义样本。",
        ),
        FieldSchema(
            name="tags",
            dtype=DataType.JSON,
            description="接口关联的标签集合，保留多标签信息供后续治理和调试使用。",
        ),
        FieldSchema(
            name="business_intents",
            dtype=DataType.JSON,
            description="该接口可服务的业务意图集合，帮助 Router 和 Renderer 统一业务域语义。",
        ),
        FieldSchema(
            name="api_schema",
            dtype=DataType.JSON,
            description="给 LLM 看的接口说明书，包含请求参数、返回结构和样例等信息。",
        ),
        FieldSchema(
            name="response_data_path",
            dtype=DataType.VARCHAR,
            max_length=256,
            description="执行后从响应体中抽取主数据的路径，避免每次都靠渲染层猜测数据落点。",
        ),
        FieldSchema(
            name="field_labels",
            dtype=DataType.JSON,
            description="字段显示名映射，用于把底层英文字段翻译成前端可读标题。",
        ),
        FieldSchema(
            name="executor_config",
            dtype=DataType.JSON,
            description="第四阶段执行凭证，如 base_url、headers、鉴权配置等物理调用参数。",
        ),
        FieldSchema(
            name="security_rules",
            dtype=DataType.JSON,
            description="安全规则元数据，如只读限制、行级过滤提示、审计标记等执法手册。",
        ),
        FieldSchema(
            name="detail_hint",
            dtype=DataType.JSON,
            description="详情页渲染提示，供 list-detail 场景决定是否命中固定模板或详情快路。",
        ),
        FieldSchema(
            name="pagination_hint",
            dtype=DataType.JSON,
            description="分页刷新契约，约束下一页数据如何回填到既有 JSON Spec 的目标节点。",
        ),
        FieldSchema(
            name="template_hint",
            dtype=DataType.JSON,
            description="模板匹配提示，标记该接口是否适合走预设 ui_page_templates 快速渲染。",
        ),
        # 向量字段
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=EMBEDDING_DIM,
            description="接口语义向量，是第一、二阶段语义召回和跨域分层检索的核心索引字段。",
        ),
    ]
    return CollectionSchema(
        fields=fields,
        description="Business API RAG catalog",
        enable_dynamic_field=True,
    )


def _field_signature(field: FieldSchema) -> tuple[str, int, tuple[tuple[str, object], ...]]:
    """抽取字段签名，用于识别类型级别的 schema 漂移。"""
    return field.name, int(field.dtype), tuple(sorted((field.params or {}).items()))


def _expected_schema_signature() -> set[tuple[str, int, tuple[tuple[str, object], ...]]]:
    """返回当前版本 schema 的字段签名集合。"""
    return {_field_signature(field) for field in _get_collection_schema().fields}


def _matches_expected_schema(collection: Collection) -> bool:
    """判断现有 collection 是否与当前代码版本的 schema 完全一致。"""
    actual_signature = {_field_signature(field) for field in collection.schema.fields}
    return actual_signature == _expected_schema_signature() and bool(collection.schema.enable_dynamic_field)


class ApiCatalogIndexer:
    """将 API 目录写入 Milvus 向量库。"""

    def __init__(self) -> None:
        self._embedder: BGEM3FlagModel | None = None
        self._collection: Collection | None = None
        self._embedder_warmed_up = False

    # ── 懒加载 ──────────────────────────────────────────────────

    def _get_embedder(self) -> BGEM3FlagModel:
        """懒加载 embedding 模型。

        功能：
            索引器通常跑在离线运维环境里，最怕运行到一半才因为外网不可达去拉 HuggingFace。
            这里优先命中本地模型目录，让“离线全量重建索引”成为稳定能力，而不是碰运气依赖外网。
        """
        if self._embedder is None:
            logger.info("Importing FlagEmbedding package")
            flag_embedding = importlib.import_module("FlagEmbedding")
            model_cls = getattr(flag_embedding, "BGEM3FlagModel")
            model_source = resolve_model_source(
                model_name=settings.embedding_model_name,
                local_model_path=settings.embedding_model_path,
            )
            if model_source.source_kind == "local_path":
                logger.info("Loading embedding model from local path: %s", model_source.source)
            elif model_source.configured_path:
                logger.warning(
                    "Configured EMBEDDING_MODEL_PATH is unavailable, fallback to EMBEDDING_MODEL_NAME: path=%s model=%s",
                    model_source.configured_path,
                    settings.embedding_model_name,
                )
            else:
                logger.info("Loading embedding model by name: %s", model_source.source)
            self._embedder = model_cls(model_source.source, use_fp16=True)
            logger.info("Embedding model loaded: %s", model_source.source)
        return self._embedder

    async def _ensure_embedder_warmed_up(self) -> BGEM3FlagModel:
        """在 Milvus 建连前完成一次真实 embedding warmup。

        功能：
            某些 embedding 后端不会在构造模型对象时完成全部 native 初始化，而是把线程池、
            gRPC 相关 runtime 或底层 fork-sensitive 资源延迟到第一次 `encode()` 才创建。
            如果这一步发生在 Milvus 已经建立 gRPC 连接之后，就容易出现
            “Other threads are currently calling into gRPC, skipping fork() handlers” 这类噪声告警。

            因此这里把一次最小化的真实 encode 前置到任何 Milvus 建连之前，主动烧掉首次初始化成本，
            让后续索引阶段只剩“稳定的向量计算 + 稳定的 Milvus 写入”。

        Returns:
            已完成 warmup 的 embedding 模型实例。

        Raises:
            透传底层模型加载或 encode 异常，避免在 warmup 失败后继续建立 Milvus 连接并制造半初始化状态。
        """
        embedder = self._get_embedder()
        if self._embedder_warmed_up:
            return embedder

        logger.info("Running embedding warmup encode before connecting to Milvus")
        await asyncio.to_thread(lambda: embedder.encode([_EMBEDDING_WARMUP_TEXT])["dense_vecs"][0])
        self._embedder_warmed_up = True
        logger.info("Embedding warmup finished")
        return embedder

    def _get_collection(self) -> Collection:
        """获取 Milvus collection，并在 schema 漂移时自动重建。"""
        if self._collection is None:
            logger.info(
                "Connecting to Milvus host=%s port=%s timeout=%ss",
                settings.milvus_host,
                settings.milvus_port,
                settings.api_catalog_milvus_connect_timeout_seconds,
            )
            connections.connect(
                alias="default",
                host=settings.milvus_host,
                port=settings.milvus_port,
                timeout=settings.api_catalog_milvus_connect_timeout_seconds,
            )
            if not utility.has_collection(API_CATALOG_COLLECTION):
                logger.info("Creating Milvus collection: %s", API_CATALOG_COLLECTION)
                col = _create_collection()
            else:
                col = Collection(name=API_CATALOG_COLLECTION)
                # 目录 schema 影响检索过滤、LLM 上下文和执行配置，类型不一致时宁可显式重建。
                if not _matches_expected_schema(col):
                    logger.info("Recreating Milvus collection %s due to schema drift", API_CATALOG_COLLECTION)
                    col.release()
                    utility.drop_collection(API_CATALOG_COLLECTION)
                    col = _create_collection()
                else:
                    col.load()
            self._collection = col
            logger.info("Milvus collection ready: %s", API_CATALOG_COLLECTION)
        return self._collection

    # ── 公共 API ────────────────────────────────────────────────

    async def index_all(self) -> dict[str, int]:
        """从业务 MySQL 注册表全量入库。

        Returns:
            {"indexed": N, "skipped": M}
        """
        logger.info("Starting API Catalog indexing job")
        source = ApiCatalogRegistrySource()
        try:
            logger.info("Loading API registry entries from business MySQL")
            entries = await source.load_entries()
        finally:
            await source.close()
        logger.info("Loaded %d API entries from business MySQL registry", len(entries))

        # 先完成一次真实 encode，再去建立 Milvus gRPC 连接，尽量规避底层 runtime 在多线程场景下
        # 把首次初始化延后到 collection 建连之后触发。
        await self._ensure_embedder_warmed_up()
        self._get_collection()
        logger.info("Indexer dependencies ready, processing %d API entries", len(entries))

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
        logger.debug("Indexing API entry started: id=%s method=%s path=%s", entry.id, entry.method, entry.path)
        # 单条入库也必须遵守同一初始化顺序，否则 direct 调用 index_entry() 时仍会把首次 encode
        # 拖到 Milvus 建连之后，warmup 的治理价值就被绕开了。
        embedder = await self._ensure_embedder_warmed_up()
        collection = self._get_collection()

        # Embedding 是 CPU 密集型操作，放到线程池里避免卡住事件循环。
        embed_text = entry.embed_text
        embedding: list[float] = await asyncio.to_thread(
            lambda: embedder.encode([embed_text])["dense_vecs"][0].tolist()
        )

        # 先删后插，维持“同一个 api_id 在 Milvus 中只有一条有效记录”的语义。
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
            [entry.example_queries],
            [entry.tags],
            [entry.business_intents],
            [entry.api_schema],
            [entry.response_data_path],
            [entry.field_labels],
            [entry.executor_config],
            [entry.security_rules],
            [entry.detail_hint.model_dump()],
            [entry.pagination_hint.model_dump()],
            [entry.template_hint.model_dump()],
            [embedding],
        ]
        collection.insert(data)
        collection.flush()
        logger.debug("Indexing API entry finished: id=%s method=%s path=%s", entry.id, entry.method, entry.path)
        return True

def _create_collection() -> Collection:
    """创建并加载 `api_catalog` collection。"""
    collection = Collection(name=API_CATALOG_COLLECTION, schema=_get_collection_schema())
    # 向量检索切到 HNSW + COSINE，和设计稿保持一致，也能避免后续在相似度阈值上来回换算。
    collection.create_index(
        field_name="embedding",
        index_params={
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200},
        },
    )
    for field_name in ("domain", "env", "status", "tag_name"):
        collection.create_index(field_name=field_name, index_params={"index_type": "INVERTED"})
    collection.load()
    return collection


# ── CLI 入口 ────────────────────────────────────────────────────────────────

def _configure_cli_logging() -> None:
    """给直接 `python -m ...indexer` 的场景补齐最小日志配置。"""
    logging.basicConfig(
        level=logging.INFO if settings.app_debug else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        force=True,
    )


if __name__ == "__main__":
    async def main():
        _configure_cli_logging()
        logger.info("API Catalog indexer CLI started")
        indexer = ApiCatalogIndexer()
        result = await indexer.index_all()
        print(f"Done: {result}")

    asyncio.run(main())
