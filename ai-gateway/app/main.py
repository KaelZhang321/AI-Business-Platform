import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import bi, chat, knowledge, query
from app.api.routes.api_query import router as api_query_router
from app.core.config import settings
from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas import HealthResponse
from app.services.identity_vault import IdentityVault
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

# 全局服务连接状态，lifespan 写入，health_check 读取
_service_status: dict[str, str] = {}
_identity_vault = IdentityVault()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 启动时：LangSmith 初始化 ─────────────────────────
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        logger.info("LangSmith tracing 已启用, project=%s", settings.langsmith_project)

    # ── 启动时：轻量级连接验证 ──────────────────────────
    logger.info("AI网关启动中 — 验证外部服务连接 ...")

    # 1) Milvus
    try:
        from pymilvus import connections, utility

        connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)
        has = utility.has_collection(settings.milvus_collection)
        _service_status["milvus"] = "ok" if has else "collection_missing"
        logger.info("Milvus 连接成功, collection '%s' 存在: %s", settings.milvus_collection, has)
    except Exception as exc:
        _service_status["milvus"] = f"error: {exc}"
        logger.warning("Milvus 连接失败: %s", exc)

    # 2) Elasticsearch
    es_client = None
    try:
        from elasticsearch import AsyncElasticsearch

        es_client = AsyncElasticsearch(
            settings.elasticsearch_url,
            basic_auth=(settings.elasticsearch_username, settings.elasticsearch_password),
        )
        exists = await es_client.indices.exists(index=settings.elasticsearch_index)
        _service_status["elasticsearch"] = "ok" if exists else "index_missing"
        logger.info("Elasticsearch 连接成功, index '%s' 存在: %s", settings.elasticsearch_index, exists)
    except Exception as exc:
        _service_status["elasticsearch"] = f"error: {exc}"
        logger.warning("Elasticsearch 连接失败: %s", exc)

    # 3) Ollama (LLM) — 轻量 ping
    ollama_client = httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=5)
    try:
        resp = await ollama_client.get("/api/tags")
        if resp.status_code == 200:
            _service_status["ollama"] = "ok"
            logger.info("Ollama 连接成功 (%s)", settings.ollama_base_url)
        else:
            _service_status["ollama"] = f"http_{resp.status_code}"
            logger.warning("Ollama 响应异常: HTTP %s", resp.status_code)
    except Exception as exc:
        _service_status["ollama"] = f"error: {exc}"
        logger.warning("Ollama 连接失败: %s", exc)

    logger.info("AI网关启动完成 — 服务状态: %s", _service_status)

    # 将共享服务实例挂载到 app.state，供 route 层按需获取
    app.state.rag_service = RAGService()

    # ── 启动缓存失效监听器（S5-6 + S5-11 语义缓存联动）────
    cache_task = None
    try:
        from app.services.cache_invalidation import (
            set_semantic_cache_service,
            start_cache_invalidation_listener,
        )
        from app.services.semantic_cache import SemanticCacheService

        if settings.semantic_cache_enabled:
            semantic_cache = SemanticCacheService()
            set_semantic_cache_service(semantic_cache)
            logger.info("语义缓存服务已初始化 (threshold=%.2f, ttl=%dh)",
                        settings.semantic_cache_similarity_threshold,
                        settings.semantic_cache_ttl_hours)

        cache_task = asyncio.create_task(start_cache_invalidation_listener())
        logger.info("缓存失效监听器已启动")
    except Exception as exc:
        logger.warning("缓存失效监听器启动失败: %s", exc)

    yield

    # ── 关闭时：释放资源 ────────────────────────────────
    logger.info("AI网关关闭中 — 释放资源 ...")

    # 缓存失效监听器
    if cache_task and not cache_task.done():
        cache_task.cancel()
        logger.info("缓存失效监听器已取消")

    # ChatWorkflow httpx 客户端
    try:
        from app.api.routes.chat import workflow as chat_workflow
        await chat_workflow.close()
        logger.info("ChatWorkflow HTTP 客户端已关闭")
    except Exception as exc:
        logger.warning("关闭 ChatWorkflow 失败: %s", exc)

    # RAGService（Neo4j / ES / ClickHouse）
    try:
        await app.state.rag_service.close()
    except Exception as exc:
        logger.warning("关闭 RAGService 失败: %s", exc)

    # Elasticsearch
    if es_client:
        try:
            await es_client.close()
            logger.info("Elasticsearch 客户端已关闭")
        except Exception as exc:
            logger.warning("关闭 Elasticsearch 客户端失败: %s", exc)

    # Milvus
    try:
        from pymilvus import connections

        connections.disconnect(alias="default")
        logger.info("Milvus 连接已断开")
    except Exception as exc:
        logger.warning("断开 Milvus 连接失败: %s", exc)

    # Ollama httpx client
    try:
        await ollama_client.aclose()
        logger.info("Ollama HTTP 客户端已关闭")
    except Exception as exc:
        logger.warning("关闭 Ollama HTTP 客户端失败: %s", exc)

    # Meeting BI aiomysql 连接池
    try:
        from app.bi.meeting_bi.db.async_session import close_meeting_pool

        await close_meeting_pool()
    except Exception as exc:
        logger.warning("关闭 Meeting BI 连接池失败: %s", exc)

    logger.info("AI网关已关闭")


app = FastAPI(
    title="AI业务中台 - AI网关",
    description="企业级AI网关服务，提供对话、知识检索、Text2SQL等能力",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def identity_vault_middleware(request: Request, call_next):
    if settings.identity_vault_enabled:
        identity = _identity_vault.extract_from_request(request)
        request.state.identity = identity
        request.state.user_id = identity.user_id if identity else None
    else:
        request.state.identity = None
        request.state.user_id = None
    return await call_next(request)


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    status = _error_code_to_http_status(exc.error_code)
    return JSONResponse(
        status_code=status,
        content={"code": exc.code, "message": exc.detail, "data": None},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"code": ErrorCode.BAD_REQUEST.code, "message": str(exc), "data": None},
    )


def _error_code_to_http_status(ec: ErrorCode) -> int:
    if ec.code < 2000:
        return 400
    if ec.code < 3000:
        return 401
    return 500

app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["知识库"])
app.include_router(query.router, prefix="/api/v1", tags=["数据查询"])
app.include_router(bi.router, prefix="/api/v1")
app.include_router(api_query_router, prefix="/api/v1")

# MCP Server 路由
from app.mcp_server.server import mcp_server  # noqa: E402

app.mount("/mcp", mcp_server.http_app())


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    return HealthResponse(
        status="ok" if all(v == "ok" for v in _service_status.values()) else "degraded",
        version="0.1.0",
        services=_service_status or {"milvus": "unchecked", "elasticsearch": "unchecked", "ollama": "unchecked"},
    )


# ── S4-5: Prometheus /metrics 端点 ─────────────────────────
from prometheus_client import (  # noqa: E402
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.responses import Response  # noqa: E402

REQUEST_COUNT = Counter("ai_gateway_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("ai_gateway_request_latency_seconds", "Request latency", ["endpoint"])


@app.middleware("http")
async def prometheus_middleware(request, call_next):
    import time

    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    endpoint = request.url.path
    REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(elapsed)
    return response


@app.get("/metrics", tags=["系统"])
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
