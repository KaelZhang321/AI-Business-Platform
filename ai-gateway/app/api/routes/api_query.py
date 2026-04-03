"""
API Query 路由

用户自然语言 → API Catalog 语义检索 → LLM 参数提取 → business-server 调用
→ 响应规范化 → DynamicUIService → json-render UI Spec

端点：
    POST /api/v1/api-query       非流式，返回完整 UI Spec
    POST /api/v1/api-catalog/index  重建 API Catalog 向量索引（管理端）
"""
from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.models.schemas import (
    ApiQueryBusinessIntent,
    ApiQueryContextStepResult,
    ApiQueryDetailRuntime,
    ApiQueryExecutionErrorDetail,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryPaginationRuntime,
    ApiQueryRequest,
    ApiQueryResponse,
    ApiQueryRoutingResult,
    ApiQueryTemplateRuntime,
    ApiQueryRuntimeMetadataResponse,
    ApiQueryUIAction,
    ApiQueryUIRuntime,
)
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchFilters
from app.services.api_catalog.param_extractor import ApiParamExtractor
from app.services.api_catalog.retriever import ApiCatalogRetriever
from app.services.dynamic_ui_service import DynamicUIService
from app.services.ui_snapshot_service import UISnapshotService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-query", tags=["API Query"])

# ── 单例（避免每次请求重建 embedding model）──────────────────────
_retriever: ApiCatalogRetriever | None = None
_extractor: ApiParamExtractor | None = None
_executor: ApiExecutor | None = None
_dynamic_ui: DynamicUIService | None = None
_snapshot_service: UISnapshotService | None = None
_bearer = HTTPBearer(auto_error=False)
_READ_ONLY_METHODS = {"GET"}
# 这里固定保留 5 条是为了给 Renderer 足够上下文，又避免把大结果集整包塞进生成链路导致注意力失焦。
_CONTEXT_ROW_LIMIT = 5
_DEFAULT_COMPONENT_TYPES = ["Card", "Metric", "Table", "List", "Form", "Tag", "Chart", "Notice"]
_UI_ACTION_DEFINITIONS = [
    {
        "code": "view_detail",
        "description": "查看当前结果详情",
        "enabled": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
            },
            "required": ["id"],
        },
    },
    {
        "code": "refresh",
        "description": "重新发起当前查询",
        "enabled": True,
        "params_schema": {"type": "object", "properties": {}},
    },
    {
        "code": "export",
        "description": "导出当前查询结果",
        "enabled": True,
        "params_schema": {"type": "object", "properties": {}},
    },
    {
        "code": "trigger_task",
        "description": "触发任务型操作",
        "enabled": True,
        "params_schema": {"type": "object", "properties": {}},
    },
    {
        "code": "remoteQuery",
        "description": "用于详情拉取或分页刷新的通用查询动作",
        "enabled": False,
        "params_schema": {
            "type": "object",
            "properties": {
                "api_id": {"type": "string"},
                "route_url": {"type": "string"},
                "params": {"type": "object"},
                "mutation_target": {"type": "string"},
            },
            "required": ["api_id"],
        },
    },
    {
        "code": "remoteMutation",
        "description": "用于确认式写入的通用动作，仅保留契约，不在 api_query 中执行",
        "enabled": False,
        "params_schema": {
            "type": "object",
            "properties": {
                "api_id": {"type": "string"},
                "payload": {"type": "object"},
                "snapshot_id": {"type": "string"},
            },
            "required": ["api_id", "payload"],
        },
    },
]
_TEMPLATE_SCENARIOS = [
    {
        "code": "list_detail_template",
        "description": "列表 + 详情页模板快路，命中模板时可直接落到固定详情 Spec。",
        "enabled": False,
    },
    {
        "code": "pagination_patch",
        "description": "分页场景的数据数组局部刷新契约。",
        "enabled": False,
    },
    {
        "code": "wysiwyg_audit",
        "description": "高危写场景的 UI 快照审计契约。",
        "enabled": False,
    },
]
_RUNTIME_ACTION_CODES = {item["code"] for item in _UI_ACTION_DEFINITIONS}
_ALLOWED_BUSINESS_INTENTS: dict[str, dict[str, str]] = {
    "none": {
        "name": "纯查询",
        "category": "read",
        "description": "当前请求仅包含读取诉求，不携带写前确认意图。",
    },
    "prepare_record_update": {
        "name": "准备修改业务数据",
        "category": "write",
        "description": "仅表达写意图，不在 api_query 中直接执行。",
    },
    "prepare_high_risk_change": {
        "name": "准备高风险变更",
        "category": "write",
        "description": "命中高风险写意图时，需要生成 UI 快照凭证。",
    },
}
_ROUTE_ALLOWED_BUSINESS_INTENT_CODES = set(_ALLOWED_BUSINESS_INTENTS)
_LEGACY_READ_BUSINESS_INTENT_CODES = {"none", "query_business_data", "query_detail_data"}


def _get_services() -> tuple[ApiCatalogRetriever, ApiParamExtractor, ApiExecutor, DynamicUIService, UISnapshotService]:
    """获取 `api_query` 所需的单例服务。"""
    global _retriever, _extractor, _executor, _dynamic_ui, _snapshot_service
    if _retriever is None:
        _retriever = ApiCatalogRetriever()
    if _extractor is None:
        _extractor = ApiParamExtractor()
    if _executor is None:
        _executor = ApiExecutor()
    if _dynamic_ui is None:
        _dynamic_ui = DynamicUIService()
    if _snapshot_service is None:
        _snapshot_service = UISnapshotService()
    return _retriever, _extractor, _executor, _dynamic_ui, _snapshot_service


# ── 请求 / 响应 Schema ───────────────────────────────────────────


# ── 主接口：自然语言 → 数据 + UI ────────────────────────────────

@router.post("", response_model=ApiQueryResponse, summary="自然语言业务接口查询")
async def api_query(
    request_body: ApiQueryRequest,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ApiQueryResponse:
    """
    用户自然语言输入 → 语义匹配业务接口 → 调用接口 → 返回 json-render UI Spec。

    流程：
    1. 轻量路由先提取 `query_domains + business_intents`
    2. 按业务域执行分层召回，避免全域 Top-K 偏科
    3. 在候选集内完成最终接口选择 + 参数提取
    4. 透传 Token 调用 business-server
    5. 响应规范化 → DynamicUIService → UI Spec
    """
    retriever, extractor, executor, dynamic_ui, snapshot_service = _get_services()
    trace_id = _resolve_trace_id(request)
    user_context = _extract_user_context(request)

    # 用户 token（透传给 business-server）
    user_token = f"Bearer {credentials.credentials}" if credentials else None

    # Step 1: 轻量路由先产出 query_domains + business_intents，避免后续直接做全域 Top-K。
    route_hint = await extractor.route_query(
        request_body.query,
        user_context,
        allowed_business_intents=_ROUTE_ALLOWED_BUSINESS_INTENT_CODES,
    )
    if route_hint.route_status != "ok":
        logger.info(
            "api_query[%s] stage2 route degraded code=%s query=%s",
            trace_id,
            route_hint.route_error_code,
            request_body.query[:100],
        )
        return await _build_stage2_degrade_response(
            dynamic_ui,
            trace_id=trace_id,
            query=request_body.query,
            title="未识别到可用业务域",
            message="抱歉，我没有完全理解您的意图，或系统中暂未开放相关查询能力，请尝试换种说法。",
            error_code=route_hint.route_error_code or "routing_failed",
            query_domains=route_hint.query_domains,
            business_intent_codes=route_hint.business_intents,
            reasoning=route_hint.reasoning,
        )

    # Step 2: 按 query_domains 做分层召回，避免多域场景被单一 domain 吞掉 Top-K。
    candidates = await retriever.search_stratified(
        request_body.query,
        domains=route_hint.query_domains,
        top_k=request_body.top_k,
        filters=ApiCatalogSearchFilters(statuses=["active"]),
    )
    if not candidates:
        logger.info(
            "api_query[%s] no candidates after stratified retrieval domains=%s query=%s",
            trace_id,
            route_hint.query_domains,
            request_body.query[:100],
        )
        return await _build_stage2_degrade_response(
            dynamic_ui,
            trace_id=trace_id,
            query=request_body.query,
            title="未找到匹配接口",
            message="当前问题没有召回到可执行的查询接口，请调整表达方式后重试。",
            error_code="no_catalog_match",
            query_domains=route_hint.query_domains,
            business_intent_codes=route_hint.business_intents,
            reasoning=route_hint.reasoning,
        )

    # Step 3: 在候选集中完成最终接口选择与参数提取。
    routing_result = await extractor.extract_routing_result(
        request_body.query,
        candidates,
        user_context,
        allowed_business_intents=_ROUTE_ALLOWED_BUSINESS_INTENT_CODES,
        routing_hints=route_hint,
    )
    if routing_result.route_status != "ok":
        logger.info(
            "api_query[%s] route-and-extract degraded code=%s query=%s",
            trace_id,
            routing_result.route_error_code,
            request_body.query[:100],
        )
        return await _build_stage2_degrade_response(
            dynamic_ui,
            trace_id=trace_id,
            query=request_body.query,
            title="无法确定查询接口",
            message="我找到了相关业务域，但还无法稳定确定具体接口，请补充更明确的查询条件后重试。",
            error_code=routing_result.route_error_code or "route_and_extract_failed",
            query_domains=routing_result.query_domains or route_hint.query_domains,
            business_intent_codes=routing_result.business_intents or route_hint.business_intents,
            reasoning=routing_result.reasoning or route_hint.reasoning,
        )

    selected_entry = _find_selected_entry(candidates, routing_result)
    if selected_entry is None:
        logger.info("api_query[%s] extractor could not choose endpoint", trace_id)
        return await _build_stage2_degrade_response(
            dynamic_ui,
            trace_id=trace_id,
            query=request_body.query,
            title="无法确定查询接口",
            message="当前输入关联了多个候选接口，但仍缺少足够信息来确定最终查询目标。",
            error_code="selected_api_unresolved",
            query_domains=routing_result.query_domains or route_hint.query_domains,
            business_intent_codes=routing_result.business_intents or route_hint.business_intents,
            reasoning=routing_result.reasoning or route_hint.reasoning,
        )

    _ensure_read_only_entry(selected_entry, trace_id)
    params = dict(routing_result.params)
    query_domains = routing_result.query_domains or route_hint.query_domains or [selected_entry.domain]
    business_intents = _build_business_intents(
        routing_result.business_intents or route_hint.business_intents
    )

    # Step 3: 调用 business-server
    missing_required_params = _find_missing_required_params(selected_entry, params)
    if missing_required_params:
        execution_result = _build_skipped_execution_result(
            trace_id=trace_id,
            missing_required_params=missing_required_params,
        )
    else:
        execution_result = await executor.call(selected_entry, params, user_token, trace_id=trace_id)
    context_pool = _build_context_pool(selected_entry, execution_result)

    # Step 4: 生成 UI Spec
    base_runtime = _build_ui_runtime(selected_entry, execution_result, params=params)
    data_for_ui = _normalize_data_for_ui(execution_result)
    ui_spec = await dynamic_ui.generate_ui_spec(
        intent="query",
        data=data_for_ui,
        context={
            "question": request_body.query,
            "user_query": request_body.query,
            "title": selected_entry.description,
            "total": execution_result.total,
            "api_id": selected_entry.id,
            "error": execution_result.error,
            "empty_message": "未查到符合条件的数据，请调整筛选条件后重试。",
            "skip_message": _build_skip_message(execution_result),
            "context_pool": {
                step_id: step.model_dump(exclude_none=True)
                for step_id, step in context_pool.items()
            },
            "business_intents": [intent.model_dump() for intent in business_intents],
        },
        status=execution_result.status,
        runtime=base_runtime,
    )
    ui_runtime = _finalize_ui_runtime(base_runtime, ui_spec)
    ui_runtime = _maybe_attach_snapshot(
        snapshot_service,
        trace_id=trace_id,
        business_intents=business_intents,
        ui_spec=ui_spec,
        ui_runtime=ui_runtime,
        metadata={
            "api_id": selected_entry.id,
            "api_path": selected_entry.path,
            "query_domains": query_domains,
        },
    )

    return ApiQueryResponse(
        trace_id=trace_id,
        query_domains=query_domains,
        execution_status=execution_result.status,
        api_id=selected_entry.id,
        api_path=selected_entry.path,
        params=params,
        business_intents=business_intents,
        context_pool=context_pool,
        ui_runtime=ui_runtime,
        ui_spec=ui_spec,
        data_count=_count_execution_rows(execution_result),
        total=execution_result.total,
        error=execution_result.error,
    )


@router.get("/runtime-metadata", response_model=ApiQueryRuntimeMetadataResponse, summary="获取 api_query 运行时元数据")
async def get_runtime_metadata() -> ApiQueryRuntimeMetadataResponse:
    """返回 api_query 对外暴露的业务意图 / UI 运行时契约。"""
    return ApiQueryRuntimeMetadataResponse(
        ui_runtime=ApiQueryUIRuntime(
            components=_DEFAULT_COMPONENT_TYPES,
            ui_actions=_build_runtime_actions(),
            detail=ApiQueryDetailRuntime(
                enabled=False,
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                fallback_mode="dynamic_ui",
            ),
            pagination=ApiQueryPaginationRuntime(
                enabled=False,
                page_param="pageNum",
                page_size_param="pageSize",
                ui_action="remoteQuery",
            ),
            template=ApiQueryTemplateRuntime(
                enabled=False,
                ui_action="remoteQuery",
                render_mode="dynamic_ui",
                fallback_mode="dynamic_ui",
            ),
        ),
        template_scenarios=_TEMPLATE_SCENARIOS,
    )


# ── 管理端：重建向量索引 ──────────────────────────────────────────

class IndexRequest(BaseModel):
    config_path: str | None = None


@router.post("/catalog/index", summary="重建 API Catalog 向量索引（管理端）")
async def rebuild_catalog_index(body: IndexRequest | None = None) -> dict[str, Any]:
    """从 config/api_catalog.yaml 重新入库所有接口到 Milvus。"""
    from app.services.api_catalog.indexer import ApiCatalogIndexer
    indexer = ApiCatalogIndexer()
    config_path = body.config_path if body else None
    result = await indexer.index_all(config_path)
    return result


# ── 辅助函数 ─────────────────────────────────────────────────────

def _extract_user_context(request: Request) -> dict[str, Any]:
    """从请求中提取可自动填充的上下文（如 user_id）。

    业务接口通常需要 userId 等参数，从 JWT 解码后注入，
    避免用户每次都要手动说"我的 ID 是 xxx"。
    """
    ctx: dict[str, Any] = {}
    identity = getattr(request.state, "identity", None)
    if identity is not None and hasattr(identity, "to_request_context"):
        for key, value in identity.to_request_context().items():
            if value not in (None, "", [], {}):
                ctx[key] = value
    elif hasattr(request.state, "user_id"):
        ctx["userId"] = request.state.user_id
    return ctx


def _resolve_trace_id(request: Request) -> str:
    """优先复用外部 Trace ID，缺失时由网关生成。"""
    header_trace_id = request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id")
    return header_trace_id or uuid4().hex


def _ensure_read_only_entry(entry: ApiCatalogEntry, trace_id: str) -> None:
    """强制拦截非只读接口。

    功能：
        `api_query` 当前阶段只允许 Read，不允许任何真实 Mutation 进入执行器。
    """
    if entry.method in _READ_ONLY_METHODS:
        return
    logger.warning(
        "api_query[%s] blocked non-read endpoint id=%s method=%s path=%s",
        trace_id,
        entry.id,
        entry.method,
        entry.path,
    )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"[{trace_id}] api_query 仅支持只读接口，当前命中 {entry.method} {entry.path}",
    )


def _build_business_intents(intent_codes: list[str]) -> list[ApiQueryBusinessIntent]:
    """将业务意图编码转换为对外响应对象。"""
    codes = _normalize_business_intent_codes(intent_codes)
    return [
        ApiQueryBusinessIntent(
            code=code,
            name=_ALLOWED_BUSINESS_INTENTS[code]["name"],
            category=_ALLOWED_BUSINESS_INTENTS[code]["category"],
            description=_ALLOWED_BUSINESS_INTENTS[code]["description"],
        )
        for code in dict.fromkeys(codes)
    ]


def _normalize_business_intent_codes(intent_codes: list[str]) -> list[str]:
    """把历史读意图与空结果统一折叠成 `none`。

    功能：
        文档层已经把第二阶段语义收敛为“写意图 or none”，这里负责兼容旧 catalog
        中残留的 `query_business_data` / `query_detail_data` 等只读编码。
    """
    write_codes = [
        code
        for code in intent_codes
        if code in _ALLOWED_BUSINESS_INTENTS and code not in _LEGACY_READ_BUSINESS_INTENT_CODES
    ]
    return list(dict.fromkeys(write_codes)) or ["none"]


def _build_runtime_actions(action_codes: set[str] | None = None) -> list[ApiQueryUIAction]:
    """按当前运行时启用状态构造 UI 动作定义。"""
    actions: list[ApiQueryUIAction] = []
    for definition in _UI_ACTION_DEFINITIONS:
        if action_codes is not None and definition["code"] not in action_codes:
            continue
        payload = dict(definition)
        if action_codes is not None:
            payload["enabled"] = definition["code"] in action_codes
        actions.append(ApiQueryUIAction(**payload))
    return actions


def _build_ui_runtime(
    entry: ApiCatalogEntry,
    execution_result: ApiQueryExecutionResult,
    *,
    params: dict[str, Any],
) -> ApiQueryUIRuntime:
    """根据接口元数据和执行结果推导前端运行时契约。

    功能：
        把详情、分页、模板、审计等能力从“隐藏实现细节”提升为显式运行时元数据，
        供前端决定如何做二次交互。
    """
    rows = _normalize_rows(execution_result.data)
    action_codes = {"refresh", "export"}
    components = ["Card", "Table"]

    detail_hint = entry.detail_hint
    identifier_field = detail_hint.identifier_field or _infer_identifier_field(rows)
    detail_enabled = (
        execution_result.status == ApiQueryExecutionStatus.SUCCESS
        and bool(identifier_field)
        and (detail_hint.enabled or identifier_field is not None)
    )
    pagination_hint = entry.pagination_hint
    pagination_enabled = (
        execution_result.status in {ApiQueryExecutionStatus.SUCCESS, ApiQueryExecutionStatus.EMPTY}
        and (pagination_hint.enabled or execution_result.total > len(rows))
        and (execution_result.total > 0 or bool(rows))
    )
    template_hint = entry.template_hint

    if detail_enabled or pagination_enabled or template_hint.enabled:
        action_codes.add("remoteQuery")
    if detail_enabled:
        action_codes.add("view_detail")

    return ApiQueryUIRuntime(
        components=components,
        ui_actions=_build_runtime_actions(action_codes),
        detail=ApiQueryDetailRuntime(
            enabled=detail_enabled,
            api_id=(detail_hint.api_id or entry.id) if detail_enabled else None,
            route_url="/api/v1/api-query",
            identifier_field=identifier_field,
            query_param=detail_hint.query_param or identifier_field,
            ui_action=detail_hint.ui_action if detail_enabled else None,
            template_code=detail_hint.template_code,
            fallback_mode=detail_hint.fallback_mode if detail_enabled else None,
        ),
        pagination=ApiQueryPaginationRuntime(
            enabled=pagination_enabled,
            api_id=pagination_hint.api_id or entry.id,
            total=execution_result.total,
            page_size=_infer_page_size(params, len(rows)),
            current_page=_infer_current_page(params),
            page_param=pagination_hint.page_param if pagination_enabled else None,
            page_size_param=pagination_hint.page_size_param if pagination_enabled else None,
            ui_action=pagination_hint.ui_action if pagination_enabled else None,
            mutation_target=pagination_hint.mutation_target if pagination_enabled else None,
        ),
        template=ApiQueryTemplateRuntime(
            enabled=template_hint.enabled,
            template_code=template_hint.template_code,
            ui_action="remoteQuery" if template_hint.enabled else None,
            render_mode=template_hint.render_mode if template_hint.enabled else None,
            fallback_mode=template_hint.fallback_mode if template_hint.enabled else None,
        ),
    )


def _finalize_ui_runtime(
    base_runtime: ApiQueryUIRuntime,
    ui_spec: dict[str, Any] | None,
) -> ApiQueryUIRuntime:
    """用最终生成的 UI Spec 回填组件与动作清单。"""
    action_codes = {action.code for action in base_runtime.ui_actions}
    action_codes.update(_collect_action_types(ui_spec))
    components = _collect_component_types(ui_spec) or base_runtime.components
    return base_runtime.model_copy(
        update={
            "components": components,
            "ui_actions": _build_runtime_actions(action_codes),
        }
    )


def _collect_component_types(node: Any) -> list[str]:
    """递归收集 UI Spec 中出现的组件类型。"""
    component_types: set[str] = set()

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            node_type = current.get("type")
            if isinstance(node_type, str) and any(key in current for key in ("props", "children")):
                component_types.add(node_type)
            for value in current.values():
                walk(value)
        elif isinstance(current, list):
            for item in current:
                walk(item)

    walk(node)
    return sorted(component_types)


def _collect_action_types(node: Any) -> set[str]:
    """递归收集 UI Spec 中出现的动作类型。"""
    action_types: set[str] = set()

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            action_type = current.get("type")
            action_name = current.get("action")
            if isinstance(action_type, str) and action_type in _RUNTIME_ACTION_CODES:
                action_types.add(action_type)
            if isinstance(action_name, str) and action_name in _RUNTIME_ACTION_CODES:
                action_types.add(action_name)
            for value in current.values():
                walk(value)
        elif isinstance(current, list):
            for item in current:
                walk(item)

    walk(node)
    return action_types


def _infer_identifier_field(rows: list[dict[str, Any]]) -> str | None:
    """从结果集字段中推测可用于详情跳转的主键列。"""
    if not rows or not isinstance(rows[0], dict):
        return None

    keys = list(rows[0].keys())
    exact_matches = ("id", "code", "uuid")
    for exact in exact_matches:
        for key in keys:
            if key.lower() == exact:
                return key

    for key in keys:
        normalized = key.lower()
        if normalized.endswith("_id") or normalized.endswith("id"):
            return key
    return None


def _infer_page_size(params: dict[str, Any], row_count: int) -> int | None:
    """从查询参数中推断当前页大小。"""
    for key in ("pageSize", "page_size", "size", "limit"):
        value = params.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return row_count or None


def _infer_current_page(params: dict[str, Any]) -> int | None:
    """从查询参数中推断当前页码。"""
    for key in ("page", "pageNum", "page_no", "pageIndex", "current"):
        value = params.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def _find_selected_entry(
    candidates: list[Any],
    routing_result: ApiQueryRoutingResult,
) -> ApiCatalogEntry | None:
    """根据路由结果从候选集中找出最终命中接口。"""
    return next(
        (candidate.entry for candidate in candidates if candidate.entry.id == routing_result.selected_api_id),
        None,
    )


def _normalize_rows(data: list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
    """把单对象或空值统一折叠成列表形态。"""
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _normalize_data_for_ui(execution_result: ApiQueryExecutionResult) -> list[dict[str, Any]]:
    """将执行结果转换成适合 UI 渲染的行列表。"""
    data, _ = _shape_context_data(execution_result.data)
    return _normalize_rows(data)


def _count_execution_rows(execution_result: ApiQueryExecutionResult) -> int:
    """统计当前执行结果包含的记录数。"""
    if execution_result.data is None:
        return 0
    if isinstance(execution_result.data, list):
        return len(execution_result.data)
    return 1


def _find_missing_required_params(
    entry: ApiCatalogEntry,
    params: dict[str, Any],
) -> list[str]:
    """找出当前请求缺失的必填参数。

    功能：
        在真正调用上游前先做一次“安全刹车”，避免因为 LLM 没抽到主键或筛选项，
        反而触发宽查询、全表扫描或无意义的 4xx/5xx。

    Args:
        entry: 当前命中的注册表接口定义，包含 JSON Schema 的 `required` 声明。
        params: 路由阶段提取并校验后的参数。

    Returns:
        缺失字段名列表；空列表表示可以安全执行。
    """
    missing: list[str] = []
    for field in entry.param_schema.required:
        value = params.get(field)
        if value in (None, "", [], {}):
            missing.append(field)
    return missing


def _build_skipped_execution_result(
    *,
    trace_id: str,
    missing_required_params: list[str],
) -> ApiQueryExecutionResult:
    """为缺参场景构造 `SKIPPED` 结果。

    功能：
        把“网关主动放弃执行”的原因显式保存在状态总线里，而不是让前端只收到模糊错误。
    """
    return ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.SKIPPED,
        data=[],
        total=0,
        error=f"缺少必要参数：{', '.join(missing_required_params)}",
        error_code="MISSING_REQUIRED_PARAMS",
        trace_id=trace_id,
        skipped_reason="missing_required_params",
        meta={"missing_required_params": missing_required_params},
    )


def _build_context_pool(
    entry: ApiCatalogEntry,
    execution_result: ApiQueryExecutionResult,
) -> dict[str, ApiQueryContextStepResult]:
    """将单接口执行结果包装成 `context_pool` 结构。

    功能：
        当前 PoC 仍是单步骤执行，但这里先对齐成步骤总线形状，后续切到多步骤 DAG
        时不需要推翻前后端契约。

    Returns:
        以 `step_<api_id>` 为 key 的步骤结果字典。
    """
    data, shape_meta = _shape_context_data(execution_result.data)
    meta = dict(execution_result.meta)
    meta.update(shape_meta)
    return {
        _build_step_id(entry): ApiQueryContextStepResult(
            status=execution_result.status,
            domain=entry.domain,
            api_id=entry.id,
            api_path=entry.path,
            method=entry.method,
            data=data,
            total=execution_result.total,
            error=_build_error_detail(execution_result),
            skipped_reason=execution_result.skipped_reason,
            meta=meta,
        )
    }


def _build_step_id(entry: ApiCatalogEntry) -> str:
    """生成稳定的步骤 ID，便于未来跨阶段引用和调试。"""
    return f"step_{entry.id}"


def _build_error_detail(
    execution_result: ApiQueryExecutionResult,
) -> ApiQueryExecutionErrorDetail | None:
    """把内部错误语义折叠成 Renderer 可消费的结构化错误对象。"""
    if not execution_result.error:
        return None
    return ApiQueryExecutionErrorDetail(
        code=execution_result.error_code,
        message=execution_result.error,
        retryable=execution_result.retryable,
    )


def _shape_context_data(
    data: list[dict[str, Any]] | dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | dict[str, Any], dict[str, Any]]:
    """裁剪进入 `context_pool` 和 Renderer 的数据体量。

    功能：
        把执行结果控制在一个稳定的上下文预算内，避免大列表在规则渲染或未来 LLM 渲染时
        直接拖垮链路，同时通过 `meta` 保留真实行数和截断信息。

    Returns:
        `(shaped_data, meta)`，其中 `meta` 明确说明是否发生截断。
    """
    if data is None:
        return [], {
            "raw_row_count": 0,
            "render_row_count": 0,
            "render_row_limit": _CONTEXT_ROW_LIMIT,
            "truncated": False,
        }

    if isinstance(data, dict):
        return data, {
            "raw_row_count": 1,
            "render_row_count": 1,
            "render_row_limit": _CONTEXT_ROW_LIMIT,
            "truncated": False,
        }

    rows = _normalize_rows(data)
    # 这里优先保留前几条样本，目的是服务查询结果预览，而不是在网关层承担完整翻页职责。
    limited_rows = rows[:_CONTEXT_ROW_LIMIT]
    truncated = len(rows) > len(limited_rows)
    meta = {
        "raw_row_count": len(rows),
        "render_row_count": len(limited_rows),
        "render_row_limit": _CONTEXT_ROW_LIMIT,
        "truncated": truncated,
    }
    if truncated:
        meta["truncated_count"] = len(rows) - len(limited_rows)
    return limited_rows, meta


def _build_skip_message(execution_result: ApiQueryExecutionResult) -> str:
    """将跳过原因翻译为适合前端提示的中文文案。"""
    if execution_result.skipped_reason == "missing_required_params":
        missing_fields = execution_result.meta.get("missing_required_params", [])
        if missing_fields:
            return f"由于缺少必要参数 {', '.join(missing_fields)}，当前查询未被执行。"
    if execution_result.error:
        return execution_result.error
    return "由于缺少必要条件，当前查询未被执行。"


async def _build_stage2_degrade_response(
    dynamic_ui: DynamicUIService,
    *,
    trace_id: str,
    query: str,
    title: str,
    message: str,
    error_code: str,
    query_domains: list[str],
    business_intent_codes: list[str],
    reasoning: str | None = None,
) -> ApiQueryResponse:
    """把第二阶段失败统一折叠为可渲染的安全 Notice。

    功能：
        路由失败、无候选、候选内无法定点等场景都属于“未进入真实执行”的安全失败，
        不应该再抛裸 HTTP 错，而应返回一份冻结的只读 UI envelope 给前端。
    """
    execution_result = ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.SKIPPED,
        data=[],
        total=0,
        error=message,
        error_code=error_code,
        retryable=True,
        trace_id=trace_id,
        skipped_reason=error_code,
        meta={"stage": "stage2", "query": query, "reasoning": reasoning},
    )
    business_intents = _build_business_intents(business_intent_codes)
    context_pool = {
        "stage2_routing": ApiQueryContextStepResult(
            status=ApiQueryExecutionStatus.SKIPPED,
            domain=query_domains[0] if len(query_domains) == 1 else None,
            data=[],
            total=0,
            error=ApiQueryExecutionErrorDetail(
                code=error_code,
                message=message,
                retryable=True,
            ),
            skipped_reason=error_code,
            meta={
                "stage": "stage2",
                "query_domains": query_domains,
                "reasoning": reasoning,
            },
        )
    }
    base_runtime = ApiQueryUIRuntime(
        components=["Card", "Notice"],
        ui_actions=_build_runtime_actions({"refresh"}),
    )
    ui_spec = await dynamic_ui.generate_ui_spec(
        intent="query",
        data=[],
        context={
            "title": title,
            "user_query": query,
            "skip_message": message,
            "error": message,
            "context_pool": {
                step_id: step.model_dump(exclude_none=True)
                for step_id, step in context_pool.items()
            },
            "business_intents": [intent.model_dump() for intent in business_intents],
        },
        status=execution_result.status,
        runtime=base_runtime,
    )
    ui_runtime = _finalize_ui_runtime(base_runtime, ui_spec)
    return ApiQueryResponse(
        trace_id=trace_id,
        query_domains=query_domains,
        execution_status=execution_result.status,
        business_intents=business_intents,
        context_pool=context_pool,
        ui_runtime=ui_runtime,
        ui_spec=ui_spec,
        data_count=0,
        total=0,
        error=message,
    )


def _maybe_attach_snapshot(
    snapshot_service: UISnapshotService,
    *,
    trace_id: str,
    business_intents: list[ApiQueryBusinessIntent],
    ui_spec: dict[str, Any] | None,
    ui_runtime: ApiQueryUIRuntime,
    metadata: dict[str, Any],
) -> ApiQueryUIRuntime:
    """在高危写意图场景下挂载快照凭证。"""
    if not snapshot_service.should_capture(business_intents):
        return ui_runtime

    snapshot = snapshot_service.create_snapshot(
        trace_id=trace_id,
        business_intents=business_intents,
        ui_spec=ui_spec,
        ui_runtime=ui_runtime,
        metadata=metadata,
    )
    return ui_runtime.model_copy(
        update={
            "audit": ui_runtime.audit.model_copy(
                update={
                    "enabled": True,
                    "snapshot_required": True,
                    "snapshot_id": snapshot.snapshot_id,
                    "risk_level": "high",
                }
            )
        }
    )
