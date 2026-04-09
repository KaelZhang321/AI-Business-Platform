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

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.schemas import (
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
from app.services.api_catalog.business_intents import get_business_intent_catalog_service
from app.services.api_catalog.dag_planner import ApiDagPlanner
from app.services.api_catalog.executor import ApiExecutor
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
_bearer = HTTPBearer(auto_error=False)


def _get_services() -> tuple[ApiCatalogRetriever, ApiParamExtractor, ApiExecutor, DynamicUIService, UISnapshotService]:
    """获取 `/api-query` 所需的进程级单例依赖。"""

    global _retriever, _extractor, _executor, _dynamic_ui, _snapshot_service
    if _retriever is None:
        _retriever = ApiCatalogRetriever()
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


@router.post("", response_model=ApiQueryResponse, summary="业务接口查询（支持自然语言与直达模式）")
async def api_query(
    request_body: ApiQueryRequest,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ApiQueryResponse:
    """调用 `/api-query` 外层工作流。"""

    trace_id = _resolve_trace_id(request)
    interaction_id = _resolve_interaction_id(request)
    conversation_id = _resolve_conversation_id(request_body)
    user_context = _extract_user_context(request)
    user_token = f"Bearer {credentials.credentials}" if credentials else None

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
            payload={"mode": request_body.mode.value},
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
    """返回前端运行时所需的 UI 目录与模板场景。"""

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
                route_url="/api/v1/api-query",
                ui_action="remoteMutation",
            ),
        ),
        template_scenarios=catalog_service.get_template_scenarios(),
    )


@router.post("/catalog/index", summary="重建 API Catalog 向量索引（管理端）")
async def rebuild_catalog_index() -> dict[str, Any]:
    """从治理元数据重建 API Catalog 索引。"""

    from app.services.api_catalog.indexer import ApiCatalogIndexer

    indexer = ApiCatalogIndexer()
    return await indexer.index_all()


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
