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
from pydantic import BaseModel, Field

from app.models.schemas import (
    ApiQueryBusinessIntent,
    ApiQueryDetailRuntime,
    ApiQueryPaginationRuntime,
    ApiQueryRequest,
    ApiQueryResponse,
    ApiQueryRuntimeMetadataResponse,
    ApiQueryUIAction,
    ApiQueryUIRuntime,
)
from app.services.api_catalog.executor import ApiCallError, ApiExecutor
from app.services.api_catalog.schema import ApiCatalogEntry
from app.services.api_catalog.param_extractor import ApiParamExtractor
from app.services.api_catalog.retriever import ApiCatalogRetriever
from app.services.dynamic_ui_service import DynamicUIService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-query", tags=["API Query"])

# ── 单例（避免每次请求重建 embedding model）──────────────────────
_retriever: ApiCatalogRetriever | None = None
_extractor: ApiParamExtractor | None = None
_executor: ApiExecutor | None = None
_dynamic_ui: DynamicUIService | None = None
_bearer = HTTPBearer(auto_error=False)
_READ_ONLY_METHODS = {"GET"}
_DEFAULT_COMPONENT_TYPES = ["Card", "Metric", "Table", "List", "Form", "Tag", "Chart"]
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


def _get_services() -> tuple[ApiCatalogRetriever, ApiParamExtractor, ApiExecutor, DynamicUIService]:
    global _retriever, _extractor, _executor, _dynamic_ui
    if _retriever is None:
        _retriever = ApiCatalogRetriever()
    if _extractor is None:
        _extractor = ApiParamExtractor()
    if _executor is None:
        _executor = ApiExecutor()
    if _dynamic_ui is None:
        _dynamic_ui = DynamicUIService()
    return _retriever, _extractor, _executor, _dynamic_ui


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
    retriever, extractor, executor, dynamic_ui = _get_services()
    trace_id = _resolve_trace_id(request)

    # 用户 token（透传给 business-server）
    user_token = f"Bearer {credentials.credentials}" if credentials else None

    # Step 1: 语义检索
    candidates = await retriever.search(request_body.query, top_k=request_body.top_k)
    if not candidates:
        logger.info("api_query[%s] no candidates for query=%s", trace_id, request_body.query[:100])
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"[{trace_id}] 未找到匹配的业务接口，请换一种表达方式重试",
        )

    # Step 2: LLM 路由 + 参数提取
    user_context = _extract_user_context(request)
    selected_entry, params = await extractor.extract(
        request_body.query, candidates, user_context
    )
    if selected_entry is None:
        logger.info("api_query[%s] extractor could not choose endpoint", trace_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"[{trace_id}] 无法从输入中确定要查询的接口，请描述得更具体",
        )

    _ensure_read_only_entry(selected_entry, trace_id)
    business_intents = _build_business_intents()

    # Step 3: 调用 business-server
    try:
        data, total = await executor.call(selected_entry, params, user_token)
    except ApiCallError as exc:
        logger.warning("api_query[%s] API call error for %s: %s", trace_id, selected_entry.path, exc)
        return ApiQueryResponse(
            trace_id=trace_id,
            api_id=selected_entry.id,
            api_path=selected_entry.path,
            params=params,
            business_intents=business_intents,
            ui_runtime=_build_ui_runtime(None, [], total=0, params=params),
            error=exc.user_message,
        )

    # Step 4: 生成 UI Spec
    data_for_ui = data if isinstance(data, list) else [data]
    ui_intent = selected_entry.ui_hint  # table / card / metric / list / chart
    ui_spec = await dynamic_ui.generate_ui_spec(
        intent="query" if ui_intent in ("table", "chart") else ui_intent,
        data=data_for_ui,
        context={
            "question": request_body.query,
            "title": selected_entry.description,
            "total": total,
            "api_id": selected_entry.id,
        },
    )
    ui_runtime = _build_ui_runtime(ui_spec, data_for_ui, total=total, params=params)

    return ApiQueryResponse(
        trace_id=trace_id,
        api_id=selected_entry.id,
        api_path=selected_entry.path,
        params=params,
        business_intents=business_intents,
        ui_runtime=ui_runtime,
        ui_spec=ui_spec,
        data_count=len(data_for_ui),
        total=total,
    )


@router.get("/runtime-metadata", response_model=ApiQueryRuntimeMetadataResponse, summary="获取 api_query 运行时元数据")
async def get_runtime_metadata() -> ApiQueryRuntimeMetadataResponse:
    """返回 api_query 对外暴露的业务意图 / UI 运行时契约。"""
    return ApiQueryRuntimeMetadataResponse(
        ui_runtime=ApiQueryUIRuntime(
            components=_DEFAULT_COMPONENT_TYPES,
            ui_actions=_build_runtime_actions(),
            detail=ApiQueryDetailRuntime(enabled=False, ui_action="remoteQuery"),
            pagination=ApiQueryPaginationRuntime(enabled=False, ui_action="remoteQuery"),
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
    # 从 request.state 获取（如果有认证中间件注入）
    if hasattr(request.state, "user_id"):
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


def _build_business_intents() -> list[ApiQueryBusinessIntent]:
    return [
        ApiQueryBusinessIntent(
            code="query_business_data",
            name="查询业务数据",
            category="read",
            description="仅允许读操作进入 api_query 执行链路。",
        )
    ]


def _build_runtime_actions(action_codes: set[str] | None = None) -> list[ApiQueryUIAction]:
    actions = [ApiQueryUIAction(**definition) for definition in _UI_ACTION_DEFINITIONS]
    if action_codes is None:
        return actions
    return [action for action in actions if action.code in action_codes]


def _build_ui_runtime(
    ui_spec: dict[str, Any] | None,
    rows: list[dict[str, Any]],
    *,
    total: int,
    params: dict[str, Any],
) -> ApiQueryUIRuntime:
    action_codes = _collect_action_types(ui_spec) or {"refresh", "export"}
    components = _collect_component_types(ui_spec) or ["Card", "Table"]
    identifier_field = _infer_identifier_field(rows)
    pagination_enabled = total > len(rows) if rows else total > 0

    if pagination_enabled:
        action_codes.add("remoteQuery")
    if identifier_field:
        action_codes.add("view_detail")

    return ApiQueryUIRuntime(
        components=components,
        ui_actions=_build_runtime_actions(action_codes),
        detail=ApiQueryDetailRuntime(
            enabled=identifier_field is not None,
            identifier_field=identifier_field,
            query_param=identifier_field,
            ui_action="remoteQuery" if identifier_field else None,
        ),
        pagination=ApiQueryPaginationRuntime(
            enabled=pagination_enabled,
            total=total,
            page_size=_infer_page_size(params, len(rows)),
            current_page=_infer_current_page(params),
            ui_action="remoteQuery" if pagination_enabled else None,
        ),
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
            props = current.get("props")
            if isinstance(props, dict):
                actions = props.get("actions")
                if isinstance(actions, list):
                    for action in actions:
                        if isinstance(action, dict):
                            action_type = action.get("type")
                            if isinstance(action_type, str):
                                action_types.add(action_type)
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
