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
import inspect
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import get_app_resource_container
from app.core.config import settings
from app.core.resources import AppResources
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
from app.services.api_catalog.index_job_service import (
    ApiCatalogIndexJobService,
    ApiCatalogIndexJobStartError,
)
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_workflow import ApiQueryWorkflow
from app.services.dynamic_ui_service import DynamicUIService
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.workflows.graph_events import build_workflow_observability_fields, format_workflow_observability_log
from app.services.workflows.types import WorkflowRunContext, WorkflowTraceContext

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-query", tags=["API Query"])

_catalog_index_job_service: ApiCatalogIndexJobService | None = None
_workflow: ApiQueryWorkflow | None = None
_api_query_llm = None
_retriever = None
_extractor = None
_executor = None
_planner = None
_dynamic_ui = None
_snapshot_service = None
_bearer = HTTPBearer(auto_error=False)


def _get_ui_catalog_service(resources: AppResources = Depends(get_app_resource_container)) -> UICatalogService:
    if _route_ui_catalog_service_override is not None:
        return _route_ui_catalog_service_override()
    if resources.ui_catalog_service is None:
        raise RuntimeError("UICatalogService 尚未初始化")
    return resources.ui_catalog_service


def _get_registry_source(resources: AppResources = Depends(get_app_resource_container)) -> ApiCatalogRegistrySource:
    if _route_registry_source_override is not None:
        return _route_registry_source_override()
    if resources.api_catalog_registry_source is None:
        raise RuntimeError("ApiCatalogRegistrySource 尚未初始化")
    return resources.api_catalog_registry_source


_route_services_override = None
_route_planner_override = None
_route_workflow_override = None
_route_ui_catalog_service_override = None
_route_registry_source_override = None


def _invoke_helper_with_optional_resources(helper, resources: AppResources | None = None):
    if resources is not None:
        try:
            return helper(resources)
        except TypeError:
            return helper()
    return helper()


def _get_api_query_llm_service(resources: AppResources | None = None):
    global _api_query_llm
    if resources is not None and getattr(resources, "api_query_llm_service", None) is not None:
        return resources.api_query_llm_service
    if _api_query_llm is None:
        from app.services.api_query_llm_service import ApiQueryLLMService

        _api_query_llm = ApiQueryLLMService()
    return _api_query_llm


def _get_services(resources: AppResources | None = None, ui_catalog_service: UICatalogService | None = None):
    global _retriever, _extractor, _executor, _dynamic_ui, _snapshot_service
    if _route_services_override is not None:
        return _route_services_override()
    if resources is not None:
        if resources.api_catalog_retriever is None or resources.api_param_extractor is None or resources.api_executor is None:
            raise RuntimeError("api-query services 尚未初始化")
        dynamic_ui = resources.dynamic_ui_service or DynamicUIService(catalog_service=ui_catalog_service or _get_ui_catalog_service(resources))
        snapshot_service = resources.ui_snapshot_service or UISnapshotService()
        return (resources.api_catalog_retriever, resources.api_param_extractor, resources.api_executor, dynamic_ui, snapshot_service)

    if _retriever is None:
        from app.services.api_catalog.hybrid_retriever import ApiCatalogHybridRetriever
        from app.services.api_catalog.retriever import ApiCatalogRetriever

        _retriever = ApiCatalogHybridRetriever() if settings.api_catalog_graph_enabled or settings.api_catalog_graph_validation_enabled else ApiCatalogRetriever()
    if _extractor is None:
        from app.services.api_catalog.param_extractor import ApiParamExtractor

        _extractor = ApiParamExtractor(llm_service=_get_api_query_llm_service())
    if _executor is None:
        from app.services.api_catalog.executor import ApiExecutor

        _executor = ApiExecutor()
    if _dynamic_ui is None:
        _dynamic_ui = DynamicUIService(catalog_service=ui_catalog_service or UICatalogService(), llm_service=_get_api_query_llm_service())
    if _snapshot_service is None:
        _snapshot_service = UISnapshotService()
    return (_retriever, _extractor, _executor, _dynamic_ui, _snapshot_service)


def _get_planner(resources: AppResources | None = None):
    global _planner
    if _route_planner_override is not None:
        return _route_planner_override()
    if resources is not None and getattr(resources, "api_dag_planner", None) is not None:
        return resources.api_dag_planner
    if _planner is None:
        from app.services.api_catalog.dag_planner import ApiDagPlanner

        _planner = ApiDagPlanner(llm_service=_get_api_query_llm_service(resources))
    return _planner


def _get_response_builder(resources: AppResources) -> ApiQueryResponseBuilder:
    dynamic_ui = resources.dynamic_ui_service or DynamicUIService(catalog_service=_get_ui_catalog_service(resources))
    snapshot_service = resources.ui_snapshot_service or UISnapshotService()
    return ApiQueryResponseBuilder(
        dynamic_ui=dynamic_ui,
        snapshot_service=snapshot_service,
        ui_catalog_service=_get_ui_catalog_service(resources),
        registry_source=_get_registry_source(resources),
    )


def _get_workflow(resources: AppResources = Depends(get_app_resource_container)) -> ApiQueryWorkflow:
    global _workflow
    if _route_workflow_override is not None:
        return _route_workflow_override()
    route_services_getter = globals().get("_get_services")
    route_planner_getter = globals().get("_get_planner")
    if callable(route_services_getter) and callable(route_planner_getter):
        return ApiQueryWorkflow(
            services_getter=lambda: _invoke_helper_with_optional_resources(route_services_getter, resources),
            planner_getter=lambda: _invoke_helper_with_optional_resources(route_planner_getter, resources),
            response_builder_getter=lambda: _get_response_builder(resources),
            registry_source_getter=lambda: _route_registry_source_override() if _route_registry_source_override is not None else _get_registry_source(resources),
            allowed_business_intent_codes_getter=lambda: (
                resources.business_intent_catalog_service.get_allowed_codes()
                if resources.business_intent_catalog_service is not None
                else {"none"}
            ),
            customer_profile_service=resources.customer_profile_service,
        )
    if resources.api_query_workflow is not None:
        return resources.api_query_workflow
    if _workflow is None:
        _workflow = ApiQueryWorkflow(
            services_getter=lambda: _get_services(resources),
            planner_getter=lambda: _get_planner(resources),
            response_builder_getter=lambda: _get_response_builder(resources),
            registry_source_getter=lambda: _get_registry_source(resources),
            allowed_business_intent_codes_getter=lambda: (
                resources.business_intent_catalog_service.get_allowed_codes()
                if resources.business_intent_catalog_service is not None
                else {"none"}
            ),
            customer_profile_service=resources.customer_profile_service,
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
    ui_catalog_service: UICatalogService = Depends(_get_ui_catalog_service),
    registry_source: ApiCatalogRegistrySource = Depends(_get_registry_source),
    workflow: ApiQueryWorkflow = Depends(_get_workflow),
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
    return await workflow.run(
        request_body,
        trace_id=trace_id,
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        user_context=user_context,
        user_token=user_token,
    )


@router.get("/runtime-metadata", response_model=ApiQueryRuntimeMetadataResponse, summary="获取 api_query 运行时元数据")
async def get_runtime_metadata(
    catalog_service: UICatalogService = Depends(_get_ui_catalog_service),
) -> ApiQueryRuntimeMetadataResponse:
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
