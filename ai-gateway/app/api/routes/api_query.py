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
    "query_business_data": {
        "name": "查询业务数据",
        "category": "read",
        "description": "仅允许读操作进入 api_query 执行链路。",
    },
    "query_detail_data": {
        "name": "查询详情数据",
        "category": "read",
        "description": "读取单条业务详情，用于详情页或明细卡片。",
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


def _get_services() -> tuple[ApiCatalogRetriever, ApiParamExtractor, ApiExecutor, DynamicUIService, UISnapshotService]:
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
    1. Milvus 语义检索候选接口（Top-K）
    2. LLM 路由选择最优接口 + 提取参数（一次调用）
    3. 透传 Token 调用 business-server
    4. 响应规范化 → DynamicUIService → UI Spec
    """
    retriever, extractor, executor, dynamic_ui, snapshot_service = _get_services()
    trace_id = _resolve_trace_id(request)

    # 用户 token（透传给 business-server）
    user_token = f"Bearer {credentials.credentials}" if credentials else None

    # Step 1: 语义检索
    candidates = await retriever.search(
        request_body.query,
        top_k=request_body.top_k,
        filters=ApiCatalogSearchFilters(statuses=["active"]),
    )
    if not candidates:
        logger.info("api_query[%s] no candidates for query=%s", trace_id, request_body.query[:100])
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"[{trace_id}] 未找到匹配的业务接口，请换一种表达方式重试",
        )

    # Step 2: LLM 路由 + 参数提取
    user_context = _extract_user_context(request)
    routing_result = await extractor.extract_routing_result(
        request_body.query,
        candidates,
        user_context,
        allowed_business_intents=set(_ALLOWED_BUSINESS_INTENTS),
    )
    selected_entry = _find_selected_entry(candidates, routing_result)
    if selected_entry is None:
        logger.info("api_query[%s] extractor could not choose endpoint", trace_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"[{trace_id}] 无法从输入中确定要查询的接口，请描述得更具体",
        )

    _ensure_read_only_entry(selected_entry, trace_id)
    params = dict(routing_result.params)
    query_domains = routing_result.query_domains or [selected_entry.domain]
    business_intents = _build_business_intents(
        routing_result.business_intents or selected_entry.business_intents
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
    header_trace_id = request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id")
    return header_trace_id or uuid4().hex


def _ensure_read_only_entry(entry: ApiCatalogEntry, trace_id: str) -> None:
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
    codes = [code for code in intent_codes if code in _ALLOWED_BUSINESS_INTENTS]
    if not codes:
        codes = ["query_business_data"]
    return [
        ApiQueryBusinessIntent(
            code=code,
            name=_ALLOWED_BUSINESS_INTENTS[code]["name"],
            category=_ALLOWED_BUSINESS_INTENTS[code]["category"],
            description=_ALLOWED_BUSINESS_INTENTS[code]["description"],
        )
        for code in dict.fromkeys(codes)
    ]


def _build_runtime_actions(action_codes: set[str] | None = None) -> list[ApiQueryUIAction]:
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
    for key in ("pageSize", "page_size", "size", "limit"):
        value = params.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return row_count or None


def _infer_current_page(params: dict[str, Any]) -> int | None:
    for key in ("page", "pageNum", "page_no", "pageIndex", "current"):
        value = params.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def _find_selected_entry(
    candidates: list[Any],
    routing_result: ApiQueryRoutingResult,
) -> ApiCatalogEntry | None:
    selected = next(
        (candidate.entry for candidate in candidates if candidate.entry.id == routing_result.selected_api_id),
        None,
    )
    if selected is not None:
        return selected
    return candidates[0].entry if candidates else None


def _normalize_rows(data: list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _normalize_data_for_ui(execution_result: ApiQueryExecutionResult) -> list[dict[str, Any]]:
    data, _ = _shape_context_data(execution_result.data)
    return _normalize_rows(data)


def _count_execution_rows(execution_result: ApiQueryExecutionResult) -> int:
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


def _maybe_attach_snapshot(
    snapshot_service: UISnapshotService,
    *,
    trace_id: str,
    business_intents: list[ApiQueryBusinessIntent],
    ui_spec: dict[str, Any] | None,
    ui_runtime: ApiQueryUIRuntime,
    metadata: dict[str, Any],
) -> ApiQueryUIRuntime:
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
