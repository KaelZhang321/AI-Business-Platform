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
from app.services.api_catalog.dag_executor import ApiDagExecutor, DagExecutionReport, DagStepExecutionRecord
from app.services.api_catalog.dag_planner import ApiDagPlanner, DagPlanValidationError, build_single_step_plan
from app.services.api_catalog.business_intents import (
    CANONICAL_BUSINESS_INTENTS,
    normalize_business_intent_codes,
    resolve_business_intent_risk_level,
)
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
_planner: ApiDagPlanner | None = None
_dynamic_ui: DynamicUIService | None = None
_snapshot_service: UISnapshotService | None = None
_bearer = HTTPBearer(auto_error=False)
_READ_ONLY_METHODS = {"GET"}
# 这里固定保留 5 条是为了给 Renderer 足够上下文，又避免把大结果集整包塞进生成链路导致注意力失焦。
_CONTEXT_ROW_LIMIT = 5
_DEFAULT_COMPONENT_TYPES = ["PlannerCard", "PlannerTable", "PlannerDetailCard", "PlannerNotice"]
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
_ALLOWED_BUSINESS_INTENTS = CANONICAL_BUSINESS_INTENTS
_ROUTE_ALLOWED_BUSINESS_INTENT_CODES = set(_ALLOWED_BUSINESS_INTENTS)


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


def _get_planner() -> ApiDagPlanner:
    """获取第三阶段 Planner 单例。"""
    global _planner
    if _planner is None:
        _planner = ApiDagPlanner()
    return _planner


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
    retrieval_filters = _build_retrieval_filters(request_body)
    candidates = await retriever.search_stratified(
        request_body.query,
        domains=route_hint.query_domains,
        top_k=request_body.top_k,
        filters=retrieval_filters,
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

    # Step 3: 构造第三阶段执行计划。单候选仍走确定性一跳计划，避免把稳定链路暴露给额外模型波动。
    planning_intent_codes = list(route_hint.business_intents)
    if len(candidates) == 1:
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
        planning_intent_codes = list(routing_result.business_intents or route_hint.business_intents)
        plan = build_single_step_plan(
            selected_entry,
            routing_result.params,
            step_id=_build_step_id(selected_entry),
            plan_id=f"dag_{trace_id[:8]}",
        )
    else:
        planner = _get_planner()
        try:
            plan = await planner.build_plan(
                request_body.query,
                candidates,
                user_context,
                route_hint,
            )
        except DagPlanValidationError as exc:
            logger.info("api_query[%s] planner degraded code=%s", trace_id, exc.code)
            return await _build_stage3_degrade_response(
                dynamic_ui,
                trace_id=trace_id,
                query=request_body.query,
                title="数据执行计划生成失败",
                message="我找到了相关接口，但当前还无法稳定生成可执行的数据流，请补充更明确的查询链路后重试。",
                error_code=exc.code,
                query_domains=route_hint.query_domains,
                business_intent_codes=planning_intent_codes,
                reasoning=str(exc),
            )

    # Step 4: 对 DAG 做白名单与依赖校验，任何脏图纸都不能进入物理执行阶段。
    planner = _get_planner()
    try:
        step_entries = planner.validate_plan(plan, candidates)
    except DagPlanValidationError as exc:
        logger.info("api_query[%s] planner validation degraded code=%s", trace_id, exc.code)
        return await _build_stage3_degrade_response(
            dynamic_ui,
            trace_id=trace_id,
            query=request_body.query,
            title="数据执行计划校验失败",
            message="系统生成的数据依赖图存在安全风险，已终止执行以保护业务系统。",
            error_code=exc.code,
            query_domains=route_hint.query_domains,
            business_intent_codes=planning_intent_codes,
            reasoning=str(exc),
        )

    dag_executor = ApiDagExecutor(executor)
    execution_report = await dag_executor.execute_plan(
        plan,
        step_entries,
        user_token=user_token,
        trace_id=trace_id,
    )
    context_pool = _build_plan_context_pool(execution_report)
    aggregate_status = _summarize_execution_report(execution_report)
    anchor_record = _select_response_anchor(execution_report)
    internal_query_domains = _collect_execution_domains(execution_report, route_hint.query_domains)
    query_domains = _format_query_domains_for_response(internal_query_domains)
    business_intents = _build_business_intents(planning_intent_codes)

    # Step 5: 按多步骤执行结果构造当前规则渲染器仍能消费的数据视图。
    data_for_ui = _build_ui_data_from_execution_report(execution_report, anchor_record)
    runtime = _build_runtime_from_execution_report(execution_report, anchor_record)
    ui_spec = await dynamic_ui.generate_ui_spec(
        intent="query",
        data=data_for_ui,
        context={
            "question": request_body.query,
            "user_query": request_body.query,
            "title": _build_execution_title(execution_report, anchor_record),
            "detail_title": anchor_record.entry.description if anchor_record else "详情信息",
            "total": _build_response_total(anchor_record),
            "api_id": anchor_record.entry.id if anchor_record else None,
            "error": _build_response_error(execution_report),
            "empty_message": "未查到符合条件的数据，请调整筛选条件后重试。",
            "skip_message": _build_execution_skip_message(execution_report),
            "partial_message": "部分步骤执行失败或被短路，当前仅展示可安全返回的数据。",
            "query_render_mode": _infer_query_render_mode(execution_report, anchor_record),
            "context_pool": {step_id: step.model_dump(exclude_none=True) for step_id, step in context_pool.items()},
            "business_intents": [intent.model_dump() for intent in business_intents],
        },
        status=aggregate_status,
        runtime=runtime,
    )
    ui_runtime = _finalize_ui_runtime(runtime, ui_spec)
    ui_runtime = _maybe_attach_snapshot(
        snapshot_service,
        trace_id=trace_id,
        business_intents=business_intents,
        ui_spec=ui_spec,
        ui_runtime=ui_runtime,
        metadata={
            "plan_id": plan.plan_id,
            "step_ids": [step.step_id for step in plan.steps],
            "api_id": anchor_record.entry.id if anchor_record else None,
            "api_path": anchor_record.entry.path if anchor_record else None,
            "query_domains": query_domains,
            "retrieval_filters": retrieval_filters.model_dump(),
        },
    )

    return ApiQueryResponse(
        trace_id=trace_id,
        query_domains=query_domains,
        execution_status=aggregate_status,
        execution_plan=plan,
        api_id=anchor_record.entry.id if anchor_record else None,
        api_path=anchor_record.entry.path if anchor_record else None,
        params=anchor_record.resolved_params if anchor_record else {},
        business_intents=business_intents,
        context_pool=context_pool,
        ui_runtime=ui_runtime,
        ui_spec=ui_spec,
        data_count=_count_ui_data_rows(data_for_ui, anchor_record, step_count=len(execution_report.records_by_step_id)),
        total=_build_response_total(anchor_record),
        error=_build_response_error(execution_report),
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


def _build_retrieval_filters(request_body: ApiQueryRequest) -> ApiCatalogSearchFilters:
    """构造第二阶段召回使用的标量过滤器。

    功能：
        `status=active` 是第二阶段默认的安全护栏；`envs / tag_names` 则允许上层在
        不改 Prompt 的前提下，把环境隔离和业务标签收紧到硬过滤表达式里。

    Args:
        request_body: 当前 `api_query` 请求体。

    Returns:
        已去空、去重后的 Milvus 标量过滤器。

    Edge Cases:
        - 空字符串会被静默丢弃，避免拼出无意义的 `in [""]`
        - 标签名保留原始大小写和中文，以适配数据库中的稳定业务标签
    """
    return ApiCatalogSearchFilters(
        statuses=["active"],
        envs=_dedupe_non_empty([item.strip().lower() for item in request_body.envs]),
        tag_names=_dedupe_non_empty([item.strip() for item in request_body.tag_names]),
    )


def _resolve_trace_id(request: Request) -> str:
    """优先复用外部 Trace ID，缺失时由网关生成。"""
    header_trace_id = request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id")
    return header_trace_id or uuid4().hex


def _format_query_domains_for_response(query_domains: list[str]) -> list[str]:
    """将内部 domain 编码转换成对外稳定展示格式。

    功能：
        检索链路内部继续使用小写编码，便于和 Milvus 标量字段对齐；
        对外响应则统一转成大写，和技术方案中的展示契约保持一致。
    """
    return [_format_domain_for_response(domain) for domain in query_domains if domain]


def _format_domain_for_response(domain: str | None) -> str:
    """格式化单个业务域编码。"""
    normalized = (domain or "").strip()
    return normalized.upper() if normalized else ""


def _dedupe_non_empty(values: list[str]) -> list[str]:
    """对过滤入参做去空与去重，避免把脏值直接推进 Milvus 表达式。"""
    deduped: list[str] = []
    for value in values:
        if not value or value in deduped:
            continue
        deduped.append(value)
    return deduped


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
    """将业务意图编码转换为对外响应对象。

    功能：
        第二阶段内部允许保留历史别名，但对外响应必须收敛成设计文档中的稳定业务语义。

    Args:
        intent_codes: 第二阶段原始业务意图编码，可能混入历史别名或旧版只读编码。

    Returns:
        归一化后的业务意图对象列表；同一 canonical code 只保留一份。

    Edge Cases:
        - 历史高风险别名会被折叠成 canonical code，同时保留 `risk_level=high`
        - 纯读旧编码会统一折叠为 `none`
    """
    codes = _normalize_business_intent_codes(intent_codes)
    return [
        ApiQueryBusinessIntent(
            code=code,
            name=_ALLOWED_BUSINESS_INTENTS[code]["name"],
            category=_ALLOWED_BUSINESS_INTENTS[code]["category"],
            description=_ALLOWED_BUSINESS_INTENTS[code]["description"],
            risk_level=resolve_business_intent_risk_level(code, intent_codes),
        )
        for code in dict.fromkeys(codes)
    ]


def _normalize_business_intent_codes(intent_codes: list[str]) -> list[str]:
    """把历史别名与旧只读编码折叠成稳定业务意图。

    功能：
        文档层已经把第二阶段语义收敛为 `saveToServer / deleteCustomer / none`，
        这里负责吸收旧 Prompt、旧 catalog 与高风险别名的历史债务，避免外部契约继续漂移。
    """
    return normalize_business_intent_codes(intent_codes)


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
    components = ["PlannerCard", "PlannerTable", "PlannerDetailCard", "PlannerNotice"]

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
    """用最终生成的 UI Spec 回填组件与动作清单。

    功能：
        第五阶段正在从旧树形 Spec 迁移到 flat spec。这里统一从最终返回给前端的
        `ui_spec` 反推组件与动作，避免运行时元数据和真实 Spec 再次漂移。
    """
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
    """递归收集 UI Spec 中出现的组件类型。

    功能：
        同时兼容旧树形 Spec 和 `root/state/elements` 新协议，确保任务 1 切换契约后，
        `ui_runtime.components` 仍然能如实反映最终下发给前端的组件目录。
    """
    component_types: set[str] = set()

    if _is_flat_ui_spec(node):
        for element in node["elements"].values():
            if not isinstance(element, dict):
                continue
            node_type = element.get("type")
            if isinstance(node_type, str):
                component_types.add(node_type)
        return sorted(component_types)

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
    """递归收集 UI Spec 中出现的动作类型。

    功能：
        flat spec 把动作配置折叠进 `elements`，树形 Spec 则是直接嵌套在节点里。
        这里统一抽出运行时动作，保证 `ui_runtime.ui_actions` 和真实 Spec 保持一致。
    """
    action_types: set[str] = set()

    if _is_flat_ui_spec(node):
        for element in node["elements"].values():
            if isinstance(element, dict):
                _walk_action_payload(element, action_types)
        return action_types

    _walk_action_payload(node, action_types)
    return action_types


def _is_flat_ui_spec(node: Any) -> bool:
    """判断当前 UI Spec 是否已经是 `root/state/elements` 新协议。"""
    return isinstance(node, dict) and isinstance(node.get("root"), str) and isinstance(node.get("elements"), dict)


def _walk_action_payload(current: Any, action_types: set[str]) -> None:
    """递归扫描动作定义载荷。

    功能：
        单独拆出这个 helper，是为了把“flat spec 扫 elements”和“旧树形 Spec 全量扫描”
        复用到同一套动作识别逻辑里，避免任务 1 之后两条分支再度分叉。
    """
    if isinstance(current, dict):
        action_type = current.get("type")
        action_name = current.get("action")
        if isinstance(action_type, str) and action_type in _RUNTIME_ACTION_CODES:
            action_types.add(action_type)
        if isinstance(action_name, str) and action_name in _RUNTIME_ACTION_CODES:
            action_types.add(action_name)
        for value in current.values():
            _walk_action_payload(value, action_types)
    elif isinstance(current, list):
        for item in current:
            _walk_action_payload(item, action_types)


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


def _build_plan_context_pool(execution_report: DagExecutionReport) -> dict[str, ApiQueryContextStepResult]:
    """将第三阶段执行报告转换成多步骤 `context_pool`。

    功能：
        `context_pool` 是第四、五阶段之间最关键的事实总线。这里必须保留每一步的
        状态、数据与运行时元信息，避免 Renderer 在多步骤场景下重新“猜”来源。
    """
    context_pool: dict[str, ApiQueryContextStepResult] = {}

    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        context_pool.update(
            _build_context_pool(
                record.entry,
                record.execution_result,
                step_id=record.step.step_id,
                extra_meta={
                    "plan_id": execution_report.plan.plan_id,
                    "depends_on": list(record.step.depends_on),
                    "resolved_params": record.resolved_params,
                },
            )
        )

    return context_pool


def _summarize_execution_report(execution_report: DagExecutionReport) -> ApiQueryExecutionStatus:
    """将多步骤执行结果收敛成对外主状态。

    功能：
        旧版 `api_query` 只有一个主步骤，现在需要在多步骤下给前端一个稳定总状态。
        这里优先表达“是否还有可展示的成功数据”，其次再表达是否发生部分失败。
    """
    statuses = [record.execution_result.status for record in execution_report.records_by_step_id.values()]

    if not statuses:
        return ApiQueryExecutionStatus.SKIPPED

    has_success = any(status == ApiQueryExecutionStatus.SUCCESS for status in statuses)
    has_error = any(status == ApiQueryExecutionStatus.ERROR for status in statuses)
    has_skipped = any(status == ApiQueryExecutionStatus.SKIPPED for status in statuses)

    if has_success and (has_error or has_skipped):
        return ApiQueryExecutionStatus.PARTIAL_SUCCESS
    if has_success:
        return ApiQueryExecutionStatus.SUCCESS
    if has_error:
        return ApiQueryExecutionStatus.ERROR
    if all(status == ApiQueryExecutionStatus.EMPTY for status in statuses):
        return ApiQueryExecutionStatus.EMPTY
    if any(status == ApiQueryExecutionStatus.EMPTY for status in statuses):
        return ApiQueryExecutionStatus.EMPTY
    return ApiQueryExecutionStatus.SKIPPED


def _select_response_anchor(execution_report: DagExecutionReport) -> DagStepExecutionRecord | None:
    """选择对外响应锚点步骤。

    功能：
        当前规则渲染器仍然更擅长消费“一个主结果”。这里优先选择最后一个成功步骤，
        若不存在，再回退到最后一个空结果或最后执行步骤，保证响应 envelope 有稳定锚点。
    """
    ordered_records = [
        execution_report.records_by_step_id[step_id]
        for step_id in execution_report.execution_order
    ]

    for candidate_status in (
        ApiQueryExecutionStatus.SUCCESS,
        ApiQueryExecutionStatus.EMPTY,
        ApiQueryExecutionStatus.SKIPPED,
        ApiQueryExecutionStatus.ERROR,
    ):
        for record in reversed(ordered_records):
            if record.execution_result.status == candidate_status:
                return record

    return ordered_records[-1] if ordered_records else None


def _collect_execution_domains(execution_report: DagExecutionReport, fallback_domains: list[str]) -> list[str]:
    """汇总执行过程中实际涉及的业务域。"""
    executed_domains = []
    for step_id in execution_report.execution_order:
        domain = execution_report.records_by_step_id[step_id].entry.domain
        if domain and domain not in executed_domains:
            executed_domains.append(domain)

    if executed_domains:
        return executed_domains
    return list(fallback_domains)


def _normalize_rows(data: list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
    """把单对象或空值统一折叠成列表形态。"""
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _build_ui_data_from_execution_report(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> list[dict[str, Any]]:
    """为当前规则渲染器构造可展示的数据集。

    功能：
        多步骤 DAG 完成后，前端规则渲染器未必能直接理解整个 `context_pool`。
        这里做一个保守桥接：

        - 单步骤：继续展示原始业务数据
        - 多步骤：展示步骤摘要表，至少保证用户能看到每一步做了什么、结果如何
    """
    if len(execution_report.records_by_step_id) <= 1 and anchor_record is not None:
        return _normalize_data_for_ui(anchor_record.execution_result)

    summary_rows: list[dict[str, Any]] = []
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        shaped_data, shaped_meta = _shape_context_data(record.execution_result.data)
        summary_rows.append(
            {
                "stepId": step_id,
                "domain": record.entry.domain,
                "apiPath": record.entry.path,
                "status": record.execution_result.status.value,
                "recordCount": _count_execution_rows(record.execution_result),
                "renderCount": shaped_meta["render_row_count"],
                "truncated": shaped_meta["truncated"],
            }
        )

    return summary_rows


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


def _count_ui_data_rows(
    ui_rows: list[dict[str, Any]],
    anchor_record: DagStepExecutionRecord | None,
    *,
    step_count: int,
) -> int:
    """统计响应层对外展示的数据条数。"""
    if step_count == 1 and anchor_record is not None and anchor_record.execution_result.status in {
        ApiQueryExecutionStatus.SUCCESS,
        ApiQueryExecutionStatus.EMPTY,
    }:
        return _count_execution_rows(anchor_record.execution_result)
    return len(ui_rows)


def _build_runtime_from_execution_report(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> ApiQueryUIRuntime:
    """根据执行报告推导前端运行时契约。

    功能：
        单步骤结果仍可复用原有详情/分页/模板契约；多步骤场景先收敛为保守的
        只读工作台，避免把错误的详情/翻页动作挂到摘要表上。
    """
    if len(execution_report.records_by_step_id) == 1 and anchor_record is not None:
        return _build_ui_runtime(
            anchor_record.entry,
            anchor_record.execution_result,
            params=anchor_record.resolved_params,
        )

    return ApiQueryUIRuntime(
        components=["PlannerCard", "PlannerTable", "PlannerNotice"],
        ui_actions=_build_runtime_actions({"refresh", "export"}),
    )


def _infer_query_render_mode(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> str:
    """推断当前查询结果应使用的读态渲染模式。

    功能：
        规则 Renderer 需要区分“列表结果”、“单对象详情”和“多步骤摘要表”。
        这里把判定收敛在 route 层，是为了让渲染器消费一个明确语义，而不是继续从
        被裁剪后的 `data_for_ui` 反向猜测原始执行形态。

    Returns:
        `detail` / `table` / `summary_table` 三类之一。

    Edge Cases:
        - 多步骤结果即使最终只剩一行，也仍然视为 `summary_table`
        - 单步骤命中 `dict` 原始数据时，才升级为 `detail`
    """
    if len(execution_report.records_by_step_id) > 1:
        return "summary_table"
    if anchor_record is None:
        return "table"
    if isinstance(anchor_record.execution_result.data, dict):
        return "detail"
    return "table"


def _build_execution_title(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> str:
    """生成多步骤查询在 UI 顶部展示的标题。"""
    if len(execution_report.records_by_step_id) <= 1 and anchor_record is not None:
        return anchor_record.entry.description
    return f"执行计划 {execution_report.plan.plan_id}"


def _build_response_total(anchor_record: DagStepExecutionRecord | None) -> int:
    """提取当前响应锚点的总记录数。"""
    if anchor_record is None:
        return 0
    return anchor_record.execution_result.total


def _build_response_error(execution_report: DagExecutionReport) -> str | None:
    """提取多步骤执行的代表性错误信息。"""
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        if record.execution_result.error:
            return record.execution_result.error
    return None


def _build_execution_skip_message(execution_report: DagExecutionReport) -> str:
    """把多步骤跳过原因收敛成适合前端展示的文案。"""
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        execution_result = record.execution_result
        if execution_result.status == ApiQueryExecutionStatus.SKIPPED:
            return _build_skip_message(execution_result)
    return "由于缺少必要条件，当前查询未被执行。"


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
    *,
    step_id: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, ApiQueryContextStepResult]:
    """将单接口执行结果包装成 `context_pool` 结构。

    功能：
        这里既服务当前的单步骤直达路径，也服务第三阶段多步骤 DAG 汇总。
        因此步骤 ID 和附加元数据都允许由上层覆盖，避免未来再次改契约。

    Returns:
        以 `step_id` 为 key 的步骤结果字典。
    """
    data, shape_meta = _shape_context_data(execution_result.data)
    meta = dict(execution_result.meta)
    meta.update(shape_meta)
    if extra_meta:
        meta.update(extra_meta)
    return {
        step_id or _build_step_id(entry): ApiQueryContextStepResult(
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
    if execution_result.skipped_reason == "skipped_due_to_empty_upstream":
        empty_bindings = execution_result.meta.get("empty_bindings", [])
        if empty_bindings:
            return "由于上游步骤未返回可继续传递的数据，当前依赖步骤已被安全跳过。"
        return "由于上游步骤没有返回可用数据，当前查询未继续执行。"
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
    response_query_domains = _format_query_domains_for_response(query_domains)
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
            domain=response_query_domains[0] if len(response_query_domains) == 1 else None,
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
                "query_domains": response_query_domains,
                "reasoning": reasoning,
            },
        )
    }
    base_runtime = ApiQueryUIRuntime(
        components=["PlannerCard", "PlannerNotice"],
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
            "context_pool": {step_id: step.model_dump(exclude_none=True) for step_id, step in context_pool.items()},
            "business_intents": [intent.model_dump() for intent in business_intents],
        },
        status=execution_result.status,
        runtime=base_runtime,
    )
    ui_runtime = _finalize_ui_runtime(base_runtime, ui_spec)
    return ApiQueryResponse(
        trace_id=trace_id,
        query_domains=response_query_domains,
        execution_status=execution_result.status,
        business_intents=business_intents,
        context_pool=context_pool,
        ui_runtime=ui_runtime,
        ui_spec=ui_spec,
        data_count=0,
        total=0,
        error=message,
    )


async def _build_stage3_degrade_response(
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
    """把第三阶段规划或校验失败折叠为可渲染的安全 Notice。"""
    response_query_domains = _format_query_domains_for_response(query_domains)
    execution_result = ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.SKIPPED,
        data=[],
        total=0,
        error=message,
        error_code=error_code,
        retryable=True,
        trace_id=trace_id,
        skipped_reason=error_code,
        meta={"stage": "stage3", "query": query, "reasoning": reasoning},
    )
    business_intents = _build_business_intents(business_intent_codes)
    context_pool = {
        "stage3_planner": ApiQueryContextStepResult(
            status=ApiQueryExecutionStatus.SKIPPED,
            domain=response_query_domains[0] if len(response_query_domains) == 1 else None,
            data=[],
            total=0,
            error=ApiQueryExecutionErrorDetail(
                code=error_code,
                message=message,
                retryable=True,
            ),
            skipped_reason=error_code,
            meta={
                "stage": "stage3",
                "query_domains": response_query_domains,
                "reasoning": reasoning,
            },
        )
    }
    base_runtime = ApiQueryUIRuntime(
        components=["PlannerCard", "PlannerNotice"],
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
            "context_pool": {step_id: step.model_dump(exclude_none=True) for step_id, step in context_pool.items()},
            "business_intents": [intent.model_dump() for intent in business_intents],
        },
        status=execution_result.status,
        runtime=base_runtime,
    )
    ui_runtime = _finalize_ui_runtime(base_runtime, ui_spec)
    return ApiQueryResponse(
        trace_id=trace_id,
        query_domains=response_query_domains,
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
