import asyncio
import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import bi, chat, knowledge, query
from app.api.routes.api_query import router as api_query_router
from app.api.routes.catalog_governance import router as catalog_governance_router
from app.api.routes.health_quadrant import router as health_quadrant_router
from app.api.routes.report_intent import router as report_intent_router
from app.api.routes.smart_meal import (
    get_smart_meal_package_recommend_service,
    get_smart_meal_risk_service,
    router as smart_meal_router,
)
from app.api.routes.transcript_extract import router as transcript_extract_router
from app.core.config import settings
from app.core.resources import AppResources
from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas import HealthResponse
from app.services.api_catalog.business_intents import get_business_intent_catalog_service
from app.services.identity_vault import IdentityVault

logger = logging.getLogger(__name__)

_APP_LOG_FILE_PATH = Path("app/logs/app.log")
_APP_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"
_APP_LOG_MAX_BYTES = 10 * 1024 * 1024
_APP_LOG_BACKUP_COUNT = 5
_ROOT_STREAM_HANDLER_NAME = "ai_gateway.stdout"
_ROOT_FILE_HANDLER_NAME = "ai_gateway.file"
_UVICORN_FILE_HANDLER_NAME = "ai_gateway.uvicorn.file"
_UVICORN_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.access")


def _logger_has_named_handler(target_logger: logging.Logger, handler_name: str) -> bool:
    """判断目标 logger 是否已经挂载指定名称的 handler。

    功能：
        `uvicorn --reload` 会重复导入应用模块。日志配置如果不做幂等保护，最直观的故障
        就是同一条日志被打印两遍、三遍。这里用 handler 名称做稳定指纹，避免每次热重载
        都把文件/终端输出器再挂一层。

    Args:
        target_logger: 需要检查的 logger。
        handler_name: 预期的 handler 名称。

    Returns:
        若已存在同名 handler，则返回 `True`。
    """
    return any(handler.get_name() == handler_name for handler in target_logger.handlers)


def _build_stream_handler() -> logging.Handler:
    """构造标准输出日志 handler。

    功能：
        本地开发与容器场景都依赖 stdout/stderr 被宿主机采集，因此终端输出不能因为
        “补文件日志”而被意外替换。这里显式绑定 `sys.stdout`，保持开发者和容器编排层
        的既有观测入口不变。
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_ROOT_STREAM_HANDLER_NAME)
    handler.setFormatter(logging.Formatter(_APP_LOG_FORMAT))
    return handler


def _build_file_handler(handler_name: str) -> RotatingFileHandler:
    """构造滚动文件日志 handler。

    功能：
        网关日志既要稳定落盘，方便排查跨请求链路，又不能因为单文件无限增长把容器磁盘
        慢慢吃满。这里选择按大小滚动，是为了在高频访问日志场景下保持简单可控的上限。

    Args:
        handler_name: 当前 handler 的唯一名称。

    Returns:
        已绑定统一 formatter 的 `RotatingFileHandler`。
    """
    handler = RotatingFileHandler(
        _APP_LOG_FILE_PATH,
        maxBytes=_APP_LOG_MAX_BYTES,
        backupCount=_APP_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.set_name(handler_name)
    handler.setFormatter(logging.Formatter(_APP_LOG_FORMAT))
    return handler


def _configure_application_logging() -> Path:
    """配置 ai-gateway 的双通道日志输出。

    功能：
        当前网关默认只把日志打到终端，不会在仓库内保留稳定文件。为了让联调、回放和
        容器运行时都能在固定位置找到日志，这里统一把应用日志收口为：

        1. 终端继续输出，保持现有开发体验与 Docker stdout 采集链路不变
        2. 额外落盘到 `app/logs/app.log`
        3. 对 `uvicorn.access` / `uvicorn.error` 这类默认不向 root 冒泡的 logger
           单独补文件 handler，确保访问日志也能进入同一份文件

    Returns:
        实际生效的日志文件路径，便于启动阶段写入确认日志。

    Edge Cases:
        - `uvicorn --reload` 多次导入模块时，不会重复挂载同名 handler
        - 日志目录不存在时会自动创建
    """
    _APP_LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)

    # 终端输出原本就存在于多数 uvicorn 启动场景；只有在缺失时才补，避免重复打印。
    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in root_logger.handlers
    )
    if not has_stream_handler and not _logger_has_named_handler(root_logger, _ROOT_STREAM_HANDLER_NAME):
        root_logger.addHandler(_build_stream_handler())

    if not _logger_has_named_handler(root_logger, _ROOT_FILE_HANDLER_NAME):
        root_logger.addHandler(_build_file_handler(_ROOT_FILE_HANDLER_NAME))

    # uvicorn 的访问日志通常不向 root 冒泡；如果不单独补文件 handler，app.log 会缺失
    # 最关键的请求入口事实，排查“请求到了没、状态码是多少”会断档。
    for logger_name in _UVICORN_LOGGER_NAMES:
        uvicorn_logger = logging.getLogger(logger_name)
        if not uvicorn_logger.propagate and not _logger_has_named_handler(uvicorn_logger, _UVICORN_FILE_HANDLER_NAME):
            uvicorn_logger.addHandler(_build_file_handler(_UVICORN_FILE_HANDLER_NAME))

    return _APP_LOG_FILE_PATH


# 全局服务连接状态，lifespan 写入，health_check 读取
_service_status: dict[str, str] = {}
_identity_vault = IdentityVault()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_file_path = _configure_application_logging()
    logger.info("AI网关日志双写已启用, file=%s", log_file_path)

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

    # # 3) Ollama (LLM) — 轻量 ping
    # ollama_client = httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=5)
    # try:
    #     resp = await ollama_client.get("/api/tags")
    #     if resp.status_code == 200:
    #         _service_status["ollama"] = "ok"
    #         logger.info("Ollama 连接成功 (%s)", settings.ollama_base_url)
    #     else:
    #         _service_status["ollama"] = f"http_{resp.status_code}"
    #         logger.warning("Ollama 响应异常: HTTP %s", resp.status_code)
    # except Exception as exc:
    #     _service_status["ollama"] = f"error: {exc}"
    #     logger.warning("Ollama 连接失败: %s", exc)

    logger.info("AI网关启动完成 — 服务状态: %s", _service_status)

    # 将共享资源容器挂载到 app.state，供 route 层按需获取。
    app.state.resources = AppResources()
    await app.state.resources.start()
    app.state.rag_service = app.state.resources.rag_service
    await get_business_intent_catalog_service().warmup()
    # 健康四象限依赖三套数据库。启动期预热连接池可降低首个请求的冷启动时延。
    try:
        await app.state.resources.health_quadrant_service.warmup()
        logger.info("HealthQuadrantService 连接池预热完成")
    except Exception as exc:
        logger.warning("HealthQuadrantService 连接池预热失败: %s", exc)

    # 智能订餐风险识别服务预热连接池，降低首请求延迟。
    smart_meal_risk_service = get_smart_meal_risk_service()
    try:
        await smart_meal_risk_service.warmup()
        logger.info("SmartMealRiskService 连接池预热完成")
    except Exception as exc:
        logger.warning("SmartMealRiskService 连接池预热失败: %s", exc)

    # 智能订餐套餐推荐服务预热连接池，避免首个推荐请求触发建池抖动。
    smart_meal_package_recommend_service = get_smart_meal_package_recommend_service()
    try:
        await smart_meal_package_recommend_service.warmup()
        logger.info("SmartMealPackageRecommendService 连接池预热完成")
    except Exception as exc:
        logger.warning("SmartMealPackageRecommendService 连接池预热失败: %s", exc)

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
            logger.info(
                "语义缓存服务已初始化 (threshold=%.2f, ttl=%dh)",
                settings.semantic_cache_similarity_threshold,
                settings.semantic_cache_ttl_hours,
            )

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

    # AppResources 持有共享业务库连接池，必须先关闭上层服务，再统一释放底层 pool。
    resources = getattr(app.state, "resources", None)
    if isinstance(resources, AppResources):
        try:
            await resources.close()
            logger.info("AppResources 已关闭")
        except Exception as exc:
            logger.warning("关闭 AppResources 失败: %s", exc)

    # 智能订餐风险识别服务资源
    try:
        await get_smart_meal_risk_service().close()
        logger.info("SmartMealRiskService 已关闭")
    except Exception as exc:
        logger.warning("关闭 SmartMealRiskService 失败: %s", exc)

    # 智能订餐套餐推荐服务资源
    try:
        await get_smart_meal_package_recommend_service().close()
        logger.info("SmartMealPackageRecommendService 已关闭")
    except Exception as exc:
        logger.warning("关闭 SmartMealPackageRecommendService 失败: %s", exc)

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
    # try:
    #     await ollama_client.aclose()
    #     logger.info("Ollama HTTP 客户端已关闭")
    # except Exception as exc:
    #     logger.warning("关闭 Ollama HTTP 客户端失败: %s", exc)

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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def options_fallback_middleware(request: Request, call_next):
    """兜底处理非标准裸 OPTIONS，避免前端误调导致 405。

    功能：
        浏览器标准预检（携带 `Access-Control-Request-Method`）应继续交给
        `CORSMiddleware` 处理；仅当调用方发送裸 OPTIONS 且目标为 `/api/` 路径时，
        由网关直接回 200，避免把“方法不允许”暴露给前端联调流程。
    """

    if request.method != "OPTIONS":
        return await call_next(request)
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    if request.headers.get("access-control-request-method"):
        return await call_next(request)

    allow_headers = request.headers.get("access-control-request-headers", "content-type,authorization,ctoken,deviceid")
    origin = request.headers.get("origin")
    headers = {
        "Access-Control-Allow-Origin": origin if origin else "*",
        "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": allow_headers,
        "Access-Control-Max-Age": "600",
    }
    if origin:
        headers["Vary"] = "Origin"
    return Response(status_code=200, headers=headers)


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
app.include_router(catalog_governance_router, prefix="/api/v1")
app.include_router(health_quadrant_router, prefix="/api/v1")
app.include_router(report_intent_router, prefix="/api/v1")
app.include_router(smart_meal_router, prefix="/api/v1")
app.include_router(transcript_extract_router, prefix="/api/v1")

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
