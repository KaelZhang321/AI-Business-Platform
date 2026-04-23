"""`/api-query` HTTP 入口。

功能：
    wave 4 之后，这个文件只保留真正属于 route 层的职责：

    - 解析请求头与链路标识
    - 提取 request-scoped `user_context`
    - 装配 workflow 单例依赖
    - 调用 `ApiQueryWorkflow.run(...)`

    旧版手写编排和响应拼装 helper 已全部移出生产路径，避免后续维护者再次把 route
    当作 orchestration 主体。
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.schemas import (
    ApiCatalogIndexJobResponse,
    ApiQueryDetailRequestRuntime,
    ApiQueryDetailRuntime,
    ApiQueryDetailSourceRuntime,
    ApiQueryFormRuntime,
    ApiQueryListFiltersRuntime,
    ApiQueryListPaginationRuntime,
    ApiQueryListQueryContextRuntime,
    ApiQueryListRuntime,
    ApiQueryRequest,
    ApiQueryResponse,
    ApiQueryRuntimeMetadataResponse,
    ApiQueryUIRuntime,
)
from app.core.config import settings
from app.services.api_catalog.business_intents import get_business_intent_catalog_service
from app.services.api_catalog.dag_planner import ApiDagPlanner
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.hybrid_retriever import ApiCatalogHybridRetriever
from app.services.api_catalog.index_job_service import (
    ApiCatalogIndexJobService,
    ApiCatalogIndexJobStartError,
)
from app.services.api_catalog.param_extractor import ApiParamExtractor
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_catalog.retriever import ApiCatalogRetriever
from app.services.api_query_llm_service import ApiQueryLLMService
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_workflow import ApiQueryWorkflow
from app.services.dynamic_ui_service import DynamicUIService
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.workflows.graph_events import build_workflow_observability_fields, format_workflow_observability_log
from app.services.workflows.types import WorkflowRunContext, WorkflowTraceContext

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-query", tags=["API Query"])

_retriever: ApiCatalogRetriever | None = None
_extractor: ApiParamExtractor | None = None
_executor: ApiExecutor | None = None
_planner: ApiDagPlanner | None = None
_dynamic_ui: DynamicUIService | None = None
_ui_catalog: UICatalogService | None = None
_snapshot_service: UISnapshotService | None = None
_registry_source: ApiCatalogRegistrySource | None = None
_api_query_llm: ApiQueryLLMService | None = None
_workflow: ApiQueryWorkflow | None = None
_catalog_index_job_service: ApiCatalogIndexJobService | None = None
_bearer = HTTPBearer(auto_error=False)


def _get_services() -> tuple[ApiCatalogRetriever, ApiParamExtractor, ApiExecutor, DynamicUIService, UISnapshotService]:
    """获取 `/api-query` 所需的进程级单例依赖。"""

    global _retriever, _extractor, _executor, _dynamic_ui, _snapshot_service
    if _retriever is None:
        # 本期开关：关闭图谱时直接走纯向量召回，避免进入 Neo4j 相关分支。
        if settings.api_catalog_graph_enabled or settings.api_catalog_graph_validation_enabled:
            _retriever = ApiCatalogHybridRetriever()
            logger.info(
                "api_query retriever mode=hybrid graph_enabled=%s graph_validation_enabled=%s",
                settings.api_catalog_graph_enabled,
                settings.api_catalog_graph_validation_enabled,
            )
        else:
            _retriever = ApiCatalogRetriever()
            logger.info(
                "api_query retriever mode=plain graph_enabled=%s graph_validation_enabled=%s",
                settings.api_catalog_graph_enabled,
                settings.api_catalog_graph_validation_enabled,
            )
    if _extractor is None:
        _extractor = ApiParamExtractor(llm_service=_get_api_query_llm_service())
    if _executor is None:
        _executor = ApiExecutor()
    if _dynamic_ui is None:
        _dynamic_ui = DynamicUIService(
            catalog_service=_get_ui_catalog_service(),
            llm_service=_get_api_query_llm_service(),
        )
    if _snapshot_service is None:
        _snapshot_service = UISnapshotService()
    return _retriever, _extractor, _executor, _dynamic_ui, _snapshot_service


def _get_api_query_llm_service() -> ApiQueryLLMService:
    """获取 `/api-query` 共享的 LLM 单例。"""

    global _api_query_llm
    if _api_query_llm is None:
        _api_query_llm = ApiQueryLLMService()
    return _api_query_llm


def _get_ui_catalog_service() -> UICatalogService:
    """获取 UI 目录单例。"""

    global _ui_catalog
    if _ui_catalog is None:
        _ui_catalog = UICatalogService()
    return _ui_catalog


def _get_planner() -> ApiDagPlanner:
    """获取第三阶段 Planner 单例。"""

    global _planner
    if _planner is None:
        _planner = ApiDagPlanner(llm_service=_get_api_query_llm_service())
    return _planner


def _get_registry_source() -> ApiCatalogRegistrySource:
    """获取治理注册表访问单例。"""

    global _registry_source
    if _registry_source is None:
        _registry_source = ApiCatalogRegistrySource()
    return _registry_source


def _get_response_builder() -> ApiQueryResponseBuilder:
    """获取响应收口器。

    功能：
        这里继续保持“按次装配、不额外缓存”的策略，保证测试 monkeypatch 与热重载场景
        拿到的永远是当前依赖视角。
    """

    _, _, _, dynamic_ui, snapshot_service = _get_services()
    return ApiQueryResponseBuilder(
        dynamic_ui=dynamic_ui,
        snapshot_service=snapshot_service,
        ui_catalog_service=_get_ui_catalog_service(),
        registry_source=_get_registry_source(),
    )


def _get_workflow() -> ApiQueryWorkflow:
    """获取 `/api-query` 外层工作流单例。"""

    global _workflow
    if _workflow is None:
        _workflow = ApiQueryWorkflow(
            services_getter=lambda: _get_services(),
            planner_getter=lambda: _get_planner(),
            response_builder_getter=lambda: _get_response_builder(),
            registry_source_getter=lambda: _get_registry_source(),
            allowed_business_intent_codes_getter=lambda: get_business_intent_catalog_service().get_allowed_codes(),
        )
    return _workflow


def _get_catalog_index_job_service() -> ApiCatalogIndexJobService:
    """获取 API Catalog 重建任务服务单例。

    功能：
        该服务维护的是“当前 API 进程视角下的重建任务句柄”。把它做成进程级单例，
        是为了让 `/catalog/index` 的触发接口和状态查询接口共享同一份任务表，而不是
        每次请求都重新实例化后把任务状态丢掉。
    """

    global _catalog_index_job_service
    if _catalog_index_job_service is None:
        _catalog_index_job_service = ApiCatalogIndexJobService()
    return _catalog_index_job_service


@router.post("", response_model=ApiQueryResponse, summary="业务接口查询（自然语言模式）")
async def api_query(
    request_body: ApiQueryRequest,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ApiQueryResponse:
    """调用 `/api-query` 外层工作流。

    功能：
        route 层只负责收敛一次请求的链路身份与观测字段，然后把真正的业务推进委托给
        `ApiQueryWorkflow`。这样可以避免后续有人在 HTTP 入口继续堆编排逻辑，破坏
        “路由只做适配、工作流负责决策”的边界。

    Args:
        request_body: `/api-query` 标准请求体（自然语言输入）。
        request: FastAPI 原始请求对象，用于读取 trace/header 和 request-scoped 用户事实。
        credentials: 透过 `HTTPBearer` 解析出的 Authorization 凭证；缺失时允许匿名读链继续。

    Returns:
        由外层工作流统一折叠后的 `ApiQueryResponse`。

    Edge Cases:
        - `X-User-Id`、`Authorization`、trace 头的最终口径都必须在 route 层一次性确定，避免后续节点各自再猜
        - 即使请求最终会走降级分支，route 也必须先补齐观测字段，保证链路日志可串联
        - route 不直接吞掉 workflow 异常，避免把真正的契约错误伪装成成功响应
    """

    # 身份与链路字段必须在入口处冻结，后续 workflow 和执行图只消费这份标准事实。
    trace_id = _resolve_trace_id(request)
    interaction_id = _resolve_interaction_id(request)
    conversation_id = _resolve_conversation_id(request_body)
    user_context = _extract_user_context(request)
    user_token = f"Bearer {credentials.credentials}" if credentials else None

    # route 只记录“收到请求并准备分发”的统一事件；真正的阶段推进由 workflow 内部继续细分。
    logger.info(
        "%s",
        format_workflow_observability_log(
            "api_query route dispatch",
            observability_fields=build_workflow_observability_fields(
                run_context=WorkflowRunContext(
                    workflow_name="api_query_workflow",
                    trace_context=WorkflowTraceContext(
                        trace_id=trace_id,
                        interaction_id=interaction_id,
                        conversation_id=conversation_id,
                    ),
                    phase="http_adapter",
                ),
                node="dispatch",
                execution_status=None,
            ),
            payload={"query_length": len(request_body.query)},
        ),
    )
    return await _get_workflow().run(
        request_body,
        trace_id=trace_id,
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        user_context=user_context,
        user_token=user_token,
    )


@router.get("/runtime-metadata", response_model=ApiQueryRuntimeMetadataResponse, summary="获取 api_query 运行时元数据")
async def get_runtime_metadata() -> ApiQueryRuntimeMetadataResponse:
    """返回前端运行时所需的 UI 目录与模板场景。

    功能：
        该接口只暴露“平台级固定元数据”，例如组件目录、动作目录与模板场景；它故意不携带
        任何请求级上下文，避免前端误把这里返回的数据当成某次查询的真实执行契约。

    Returns:
        固定的 `ApiQueryRuntimeMetadataResponse`，用于前端初始化组件能力认知。

    Edge Cases:
        - 运行时元数据中的 route 只是静态能力声明，不能替代真实查询响应里的动态调用元数据
        - mutation form 在这里不暴露占位 URL，避免前端把无上下文地址误当成可直接提交入口
        - 目录服务会先 warmup，确保首个前端请求不会因为惰性加载拿到不完整动作集
    """

    catalog_service = _get_ui_catalog_service()
    await catalog_service.warmup()
    return ApiQueryRuntimeMetadataResponse(
        ui_runtime=ApiQueryUIRuntime(
            components=catalog_service.get_component_codes(intent="query"),
            ui_actions=catalog_service.build_runtime_actions(),
            list=ApiQueryListRuntime(
                enabled=False,
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                param_source="queryParams",
                pagination=ApiQueryListPaginationRuntime(
                    enabled=False,
                    page_param="pageNum",
                    page_size_param="pageSize",
                ),
                filters=ApiQueryListFiltersRuntime(enabled=False),
                query_context=ApiQueryListQueryContextRuntime(
                    enabled=False,
                    page_param="pageNum",
                    page_size_param="pageSize",
                ),
            ),
            detail=ApiQueryDetailRuntime(
                enabled=False,
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                request=ApiQueryDetailRequestRuntime(param_source="queryParams"),
                source=ApiQueryDetailSourceRuntime(),
            ),
            form=ApiQueryFormRuntime(
                enabled=False,
                # runtime-metadata 不携带具体 mutation 接口上下文，因此不暴露占位 URL。
                route_url=None,
                ui_action="remoteMutation",
            ),
        ),
        template_scenarios=catalog_service.get_template_scenarios(),
    )


@router.post(
    "/catalog/index",
    response_model=ApiCatalogIndexJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="异步触发 API Catalog 重建（管理端）",
)
async def rebuild_catalog_index() -> ApiCatalogIndexJobResponse:
    """异步触发 API Catalog 重建任务。

    功能：
        管理端需要的是“发起一次重建并拿到任务句柄”，而不是把整个索引过程塞进一次 HTTP
        请求里同步等待。这里改成后台子进程触发后，route 立刻返回 202，避免重建索引阻塞
        在线 API worker。

    Returns:
        当前重建任务快照；若已经存在运行中的任务，则返回同一任务并标记复用。

    Raises:
        HTTPException: 当后台子进程无法启动时抛出 500。
    """

    try:
        return await _get_catalog_index_job_service().start_rebuild()
    except ApiCatalogIndexJobStartError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "/catalog/index/{job_id}",
    response_model=ApiCatalogIndexJobResponse,
    summary="查询 API Catalog 重建任务状态（管理端）",
)
async def get_catalog_index_job(job_id: str) -> ApiCatalogIndexJobResponse:
    """读取指定重建任务的状态快照。

    功能：
        非阻塞重建意味着前端或运维脚本必须有一条正式的状态查询链路，否则 POST 触发之后
        就无法知道任务是否真正完成。这里返回的是任务事实快照，而不是重新触发任何索引逻辑。

    Args:
        job_id: 触发重建时返回的任务 ID。

    Returns:
        当前任务状态快照。

    Raises:
        HTTPException: 当任务不存在时返回 404。
    """

    job_snapshot = _get_catalog_index_job_service().get_job(job_id)
    if job_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到 API Catalog 重建任务: {job_id}",
        )
    return job_snapshot


def _extract_user_context(request: Request) -> dict[str, Any]:
    """从请求上下文提取用户事实。"""

    user_context: dict[str, Any] = {}
    identity = getattr(request.state, "identity", None)
    if identity is not None and hasattr(identity, "to_request_context"):
        for key, value in identity.to_request_context().items():
            if value not in (None, "", [], {}):
                user_context[key] = value
    elif hasattr(request.state, "user_id"):
        user_context["userId"] = request.state.user_id
    return user_context


def _resolve_trace_id(request: Request) -> str:
    """优先复用外部链路 ID，缺失时由网关生成。"""

    return request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id") or uuid4().hex


def _resolve_interaction_id(request: Request) -> str | None:
    """读取连续交互 ID。"""

    interaction_id = (request.headers.get("X-Interaction-Id") or "").strip()
    return interaction_id or None


def _resolve_conversation_id(request_body: ApiQueryRequest) -> str | None:
    """读取请求体中的会话 ID。"""

    conversation_id = (request_body.conversation_id or "").strip()
    return conversation_id or None
