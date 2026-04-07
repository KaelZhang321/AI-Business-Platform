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

from app.models.schemas import (
    ApiQueryBusinessIntent,
    ApiQueryContextStepResult,
    ApiQueryDetailRuntime,
    ApiQueryExecutionErrorDetail,
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryMode,
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
    NOOP_BUSINESS_INTENT,
    get_business_intent_catalog_service,
    normalize_business_intent_codes,
    resolve_business_intent_risk_level,
)
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource, ApiCatalogSourceError
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchFilters
from app.services.api_catalog.param_extractor import ApiParamExtractor
from app.services.api_catalog.retriever import ApiCatalogRetriever
from app.services.api_query_llm_service import ApiQueryLLMService
from app.services.dynamic_ui_service import DynamicUIService, UISpecBuildResult
from app.services.ui_spec_guard import UISpecValidationResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-query", tags=["API Query"])

# ── 单例（避免每次请求重建 embedding model）──────────────────────
_retriever: ApiCatalogRetriever | None = None
_extractor: ApiParamExtractor | None = None
_executor: ApiExecutor | None = None
_planner: ApiDagPlanner | None = None
_dynamic_ui: DynamicUIService | None = None
_ui_catalog: UICatalogService | None = None
_snapshot_service: UISnapshotService | None = None
_registry_source: ApiCatalogRegistrySource | None = None
_api_query_llm: ApiQueryLLMService | None = None
_bearer = HTTPBearer(auto_error=False)
_READ_ONLY_METHODS = {"GET"}
# 这里固定保留 5 条是为了给 Renderer 足够上下文，又避免把大结果集整包塞进生成链路导致注意力失焦。
_CONTEXT_ROW_LIMIT = 5


def _get_services() -> tuple[ApiCatalogRetriever, ApiParamExtractor, ApiExecutor, DynamicUIService, UISnapshotService]:
    """获取 `api_query` 所需的单例服务。"""
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
    """获取 `/api_query` 专用 LLM 单例。

    功能：
        第二、三、五阶段必须共享同一模型配置，否则轻量路由、Planner 和 Renderer
        可能分别命中不同后端，导致同一请求在阶段间出现风格漂移甚至结构不兼容。
    """
    global _api_query_llm
    if _api_query_llm is None:
        _api_query_llm = ApiQueryLLMService()
    return _api_query_llm


def _get_ui_catalog_service() -> UICatalogService:
    """获取 UI 目录单例。

    功能：
        `api_query` 路由与 `DynamicUIService` 必须共享同一份进程内目录快照，否则
        `runtime-metadata`、Renderer Prompt 和最终 `ui_runtime` 很容易各说各话。
    """
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
    """获取 API Catalog 注册表源单例。

    功能：
        `direct` 快路需要按 `api_id` 精确命中元数据，但不值得为每次详情/分页请求
        都新建一次 MySQL 连接池。这里和其他 gateway 服务保持相同的进程级复用策略。
    """
    global _registry_source
    if _registry_source is None:
        _registry_source = ApiCatalogRegistrySource()
    return _registry_source


# ── 请求 / 响应 Schema ───────────────────────────────────────────


# ── 主接口：自然语言 → 数据 + UI ────────────────────────────────


@router.post("", response_model=ApiQueryResponse, summary="业务接口查询（支持自然语言与直达模式）")
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
    interaction_id = _resolve_interaction_id(request)
    conversation_id = _resolve_conversation_id(request_body)
    user_context = _extract_user_context(request)
    log_prefix = _build_api_query_log_prefix(trace_id, interaction_id, conversation_id)

    request_query = _summarize_request_query(request_body)
    logger.info("%s request mode=%s query=%s", log_prefix, request_body.mode.value, request_query)

    # 用户 token（透传给 business-server）
    user_token = f"Bearer {credentials.credentials}" if credentials else None
    if request_body.mode == ApiQueryMode.DIRECT:
        plan, step_entries, query_domains, business_intent_codes, direct_query_text = await _prepare_direct_execution(
            request_body,
            trace_id=trace_id,
            interaction_id=interaction_id,
            conversation_id=conversation_id,
        )
        return await _execute_prepared_plan(
            executor=executor,
            dynamic_ui=dynamic_ui,
            snapshot_service=snapshot_service,
            trace_id=trace_id,
            interaction_id=interaction_id,
            conversation_id=conversation_id,
            user_token=user_token,
            query_text=direct_query_text,
            plan=plan,
            step_entries=step_entries,
            query_domains_hint=query_domains,
            business_intent_codes=business_intent_codes,
            log_prefix=log_prefix,
            request_mode=request_body.mode.value,
            retrieval_filters=None,
        )

    allowed_business_intent_codes = _get_route_allowed_business_intent_codes()
    assert request_body.query is not None

    # Step 1: 轻量路由先产出 query_domains + business_intents，避免后续直接做全域 Top-K。
    route_hint = await extractor.route_query(
        request_body.query,
        user_context,
        allowed_business_intents=allowed_business_intent_codes,
        trace_id=trace_id,
    )
    if route_hint.route_status != "ok":
        logger.info(
            "%s stage2 route degraded code=%s query=%s",
            log_prefix,
            route_hint.route_error_code,
            request_body.query[:100],
        )
        return await _build_stage2_degrade_response(
            dynamic_ui,
            trace_id=trace_id,
            interaction_id=interaction_id,
            conversation_id=conversation_id,
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
        trace_id=trace_id,
    )
    if not candidates:
        logger.info(
            "%s no candidates after stratified retrieval domains=%s query=%s",
            log_prefix,
            route_hint.query_domains,
            request_body.query[:100],
        )
        return await _build_stage2_degrade_response(
            dynamic_ui,
            trace_id=trace_id,
            interaction_id=interaction_id,
            conversation_id=conversation_id,
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
            allowed_business_intents=allowed_business_intent_codes,
            routing_hints=route_hint,
            trace_id=trace_id,
        )
        if routing_result.route_status != "ok":
            logger.info(
                "%s route-and-extract degraded code=%s query=%s",
                log_prefix,
                routing_result.route_error_code,
                request_body.query[:100],
            )
            return await _build_stage2_degrade_response(
                dynamic_ui,
                trace_id=trace_id,
                interaction_id=interaction_id,
                conversation_id=conversation_id,
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
            logger.info("%s extractor could not choose endpoint", log_prefix)
            return await _build_stage2_degrade_response(
                dynamic_ui,
                trace_id=trace_id,
                interaction_id=interaction_id,
                conversation_id=conversation_id,
                query=request_body.query,
                title="无法确定查询接口",
                message="当前输入关联了多个候选接口，但仍缺少足够信息来确定最终查询目标。",
                error_code="selected_api_unresolved",
                query_domains=routing_result.query_domains or route_hint.query_domains,
                business_intent_codes=routing_result.business_intents or route_hint.business_intents,
                reasoning=routing_result.reasoning or route_hint.reasoning,
            )

        _ensure_read_only_entry(selected_entry, trace_id, interaction_id, conversation_id)
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
                trace_id=trace_id,
            )
        except DagPlanValidationError as exc:
            logger.info("%s planner degraded code=%s", log_prefix, exc.code)
            return await _build_stage3_degrade_response(
                dynamic_ui,
                trace_id=trace_id,
                interaction_id=interaction_id,
                conversation_id=conversation_id,
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
        # 这里不是重复做一次 Planner，而是把 LLM 产出的“图纸”重新拉回确定性安全闸。
        # 只有命中第二阶段候选白名单、依赖关系可拓扑执行、且不越过只读边界的步骤，才允许进入真实调用。
        step_entries = planner.validate_plan(plan, candidates)
    except DagPlanValidationError as exc:
        logger.info("%s planner validation degraded code=%s", log_prefix, exc.code)
        return await _build_stage3_degrade_response(
            dynamic_ui,
            trace_id=trace_id,
            interaction_id=interaction_id,
            conversation_id=conversation_id,
            query=request_body.query,
            title="数据执行计划校验失败",
            message="系统生成的数据依赖图存在安全风险，已终止执行以保护业务系统。",
            error_code=exc.code,
            query_domains=route_hint.query_domains,
            business_intent_codes=planning_intent_codes,
            reasoning=str(exc),
        )
    return await _execute_prepared_plan(
        executor=executor,
        dynamic_ui=dynamic_ui,
        snapshot_service=snapshot_service,
        trace_id=trace_id,
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        user_token=user_token,
        query_text=request_body.query,
        plan=plan,
        step_entries=step_entries,
        query_domains_hint=route_hint.query_domains,
        business_intent_codes=planning_intent_codes,
        log_prefix=log_prefix,
        request_mode=request_body.mode.value,
        retrieval_filters=retrieval_filters,
    )


@router.get("/runtime-metadata", response_model=ApiQueryRuntimeMetadataResponse, summary="获取 api_query 运行时元数据")
async def get_runtime_metadata() -> ApiQueryRuntimeMetadataResponse:
    """返回 api_query 对外暴露的业务意图 / UI 运行时契约。"""
    catalog_service = _get_ui_catalog_service()
    # 这里主动预热目录，是为了让运营侧最先看到 MySQL 中维护的真实组件/动作说明。
    await catalog_service.warmup()
    return ApiQueryRuntimeMetadataResponse(
        ui_runtime=ApiQueryUIRuntime(
            components=catalog_service.get_component_codes(intent="query"),
            ui_actions=catalog_service.build_runtime_actions(),
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
        template_scenarios=catalog_service.get_template_scenarios(),
    )


@router.post("/catalog/index", summary="重建 API Catalog 向量索引（管理端）")
async def rebuild_catalog_index() -> dict[str, Any]:
    """从业务 MySQL 重新入库所有接口到 Milvus。"""
    from app.services.api_catalog.indexer import ApiCatalogIndexer

    indexer = ApiCatalogIndexer()
    result = await indexer.index_all()
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


def _summarize_request_query(request_body: ApiQueryRequest) -> str:
    """生成适合日志与审计的请求摘要。

    功能：
        `direct` 模式本来就没有自然语言 query；这里主动收敛成“模式 + 关键锚点”，
        避免日志系统里再次出现 `None[:100]` 这类无意义异常，也方便区分慢链路和快链路。
    """
    if request_body.mode == ApiQueryMode.DIRECT and request_body.direct_query is not None:
        return f"direct:{request_body.direct_query.api_id}"
    return (request_body.query or "")[:100]


async def _prepare_direct_execution(
    request_body: ApiQueryRequest,
    *,
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
) -> tuple[ApiQueryExecutionPlan, dict[str, ApiCatalogEntry], list[str], list[str], str]:
    """为 `direct` 快路准备单步执行计划。

    功能：
        二跳详情/分页/刷新场景已经拿到了 `api_id + params`，此时继续调用路由 LLM、
        Milvus 和 Planner 只会平白增加延迟与抖动。这里把快路入口收敛成一条
        确定性预处理链：查目录、做硬校验、构造单步计划。

    Returns:
        `(plan, step_entries, query_domains, business_intent_codes, query_text)`。

    Raises:
        HTTPException: 当接口不存在、未激活、方法越界或参数不合法时抛出。
    """
    assert request_body.direct_query is not None

    registry_source = _get_registry_source()
    direct_query = request_body.direct_query
    try:
        entry = await registry_source.get_entry_by_id(direct_query.api_id)
    except ApiCatalogSourceError as exc:
        logger.exception(
            "%s direct registry lookup failed api_id=%s",
            _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
            direct_query.api_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"[{trace_id}] direct 模式加载接口目录失败：{exc}",
        ) from exc

    if entry is None:
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"direct 模式指定的接口不存在：{direct_query.api_id}",
        )

    _ensure_active_entry(
        entry,
        trace_id=trace_id,
        interaction_id=interaction_id,
        conversation_id=conversation_id,
    )
    _ensure_read_only_entry(entry, trace_id, interaction_id, conversation_id)
    validated_params = _validate_direct_query_params(
        entry,
        direct_query.params,
        trace_id=trace_id,
        interaction_id=interaction_id,
        conversation_id=conversation_id,
    )
    plan = build_single_step_plan(
        entry,
        validated_params,
        step_id=_build_step_id(entry),
        plan_id=f"direct_{trace_id[:8]}",
    )
    query_text = request_body.query or _build_direct_query_text(entry, validated_params)
    return plan, {_build_step_id(entry): entry}, [entry.domain], ["none"], query_text


async def _execute_prepared_plan(
    *,
    executor: ApiExecutor,
    dynamic_ui: DynamicUIService,
    snapshot_service: UISnapshotService,
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
    user_token: str | None,
    query_text: str,
    plan: ApiQueryExecutionPlan,
    step_entries: dict[str, ApiCatalogEntry],
    query_domains_hint: list[str],
    business_intent_codes: list[str],
    log_prefix: str,
    request_mode: str,
    retrieval_filters: ApiCatalogSearchFilters | None,
) -> ApiQueryResponse:
    """执行已准备好的只读计划，并统一收口到渲染响应。

    功能：
        `nl` 与 `direct` 的差异只应停留在“计划怎么来”；一旦进入真实调用，就必须
        共用同一套执行状态机、UI 渲染和快照治理，避免前端看到两种语义相近但细节漂移
        的响应壳。
    """
    dag_executor = ApiDagExecutor(executor)
    # 执行统一收口到 DAG executor，而不是在 route 层手写串/并行调用。
    # 这样“上游空结果短路下游”“JSONPath 依赖绑定”“单节点失败不拖垮全链路”都由同一套状态机负责，
    # 后续排障时只需要围绕 execution_report 回放，而不必回头拼接零散中间态。
    execution_report = await dag_executor.execute_plan(
        plan,
        step_entries,
        user_token=user_token,
        trace_id=trace_id,
    )
    # 真正进入渲染层前，先把步骤级执行报告折叠为稳定摘要。
    # 这里要保留逐步事实总线、选出主展示锚点，再计算聚合状态，避免 Renderer 反向猜“哪个步骤算主结果”。
    context_pool = _build_plan_context_pool(execution_report)
    aggregate_status = _summarize_execution_report(execution_report)
    anchor_record = _select_response_anchor(execution_report)
    internal_query_domains = _collect_execution_domains(execution_report, query_domains_hint)
    query_domains = _format_query_domains_for_response(internal_query_domains)
    business_intents = _build_business_intents(business_intent_codes)

    # 这里继续复用第五阶段统一渲染入口，确保快路不会绕过 UI Guard。
    data_for_ui = _build_ui_data_from_execution_report(execution_report, anchor_record)
    runtime = _build_runtime_from_execution_report(execution_report, anchor_record)
    ui_build_result = await _generate_ui_spec_result(
        dynamic_ui,
        intent="query",
        data=data_for_ui,
        context={
            "question": query_text,
            "user_query": query_text,
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
        trace_id=trace_id,
    )
    ui_spec = ui_build_result.spec
    ui_runtime = _finalize_render_runtime(runtime, ui_spec, ui_build_result)
    if ui_build_result.frozen:
        logger.warning(
            "%s stage5 ui frozen errors=%s",
            log_prefix,
            _summarize_validation_errors(ui_build_result.validation),
        )
    else:
        snapshot_metadata = {
            "request_mode": request_mode,
            "plan_id": plan.plan_id,
            "step_ids": [step.step_id for step in plan.steps],
            "api_id": anchor_record.entry.id if anchor_record else None,
            "api_path": anchor_record.entry.path if anchor_record else None,
            "query_domains": query_domains,
        }
        if retrieval_filters is not None:
            # 只有自然语言模式真的经过了召回链路，才保留检索过滤条件供排障复盘。
            snapshot_metadata["retrieval_filters"] = retrieval_filters.model_dump()

        ui_runtime = _maybe_attach_snapshot(
            snapshot_service,
            trace_id=trace_id,
            business_intents=business_intents,
            ui_spec=ui_spec,
            ui_runtime=ui_runtime,
            metadata=snapshot_metadata,
        )

    logger.info(
        "%s success mode=%s status=%s api_id=%s step_count=%s",
        log_prefix,
        request_mode,
        aggregate_status,
        anchor_record.entry.id if anchor_record else None,
        len(execution_report.records_by_step_id),
    )
    return ApiQueryResponse(
        trace_id=trace_id,
        execution_status=aggregate_status,
        execution_plan=plan,
        ui_runtime=ui_runtime,
        ui_spec=ui_spec,
        error=_build_response_error(execution_report),
    )


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


def _resolve_interaction_id(request: Request) -> str | None:
    """提取前端透传的交互 ID。

    功能：
        `interaction_id` 用来串起一次用户连续操作内的多次请求，例如“打开列表 -> 查看详情 ->
        提交确认”。网关这里不负责生成，只做透传与回显，避免和 `trace_id` 的单请求语义混淆。

    Args:
        request: 当前 FastAPI 请求对象。

    Returns:
        头部中的 `X-Interaction-Id`；空字符串会被折叠为 `None`。

    Edge Cases:
        - 前端未传时返回 `None`，不自行兜底生成
        - 仅做首尾空白裁剪，不在网关层擅自改写业务方生成的 ID
    """
    header_interaction_id = (request.headers.get("X-Interaction-Id") or "").strip()
    return header_interaction_id or None


def _resolve_conversation_id(request_body: ApiQueryRequest) -> str | None:
    """提取前端传入的会话 ID。

    功能：
        `conversation_id` 描述的是一段多轮业务会话，而不是单次点击。把它放进日志链路后，
        运维可以把“列表 -> 详情 -> 下一步查询”这类连续请求聚成一条业务上下文，而不必只靠
        多个 `trace_id` 人工拼接。

    Args:
        request_body: `/api-query` 当前请求体。

    Returns:
        请求体中的 `conversation_id`；空字符串和全空白会被折叠为 `None`。

    Edge Cases:
        - 前端未传时返回 `None`，网关不擅自生成，以免篡改业务会话语义
        - 只做空白裁剪，保留前端定义的原始 ID 形态，方便跨端对账
    """
    conversation_id = (request_body.conversation_id or "").strip()
    return conversation_id or None


def _build_api_query_log_prefix(
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
) -> str:
    """统一构造 `api_query` 日志前缀。

    功能：
        该接口已经长期依赖 `trace_id` 做单请求排障；本次补入 `interaction_id` 的目标，是让
        运维可以把同一次用户操作拆出来看；继续补入 `conversation_id`，则是为了把多轮问答
        串成同一业务会话，避免列表页和详情页日志只能看见零散请求切片。
    """
    return (
        f"api_query[trace={trace_id} interaction={interaction_id or '-'} "
        f"conversation={conversation_id or '-'}]"
    )


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


def _ensure_read_only_entry(
    entry: ApiCatalogEntry,
    trace_id: str,
    interaction_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """强制拦截非只读接口。

    功能：
        `api_query` 当前阶段只允许 Read，不允许任何真实 Mutation 进入执行器。
    """
    if entry.method in _READ_ONLY_METHODS:
        return
    logger.warning(
        "%s blocked non-read endpoint id=%s method=%s path=%s",
        _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
        entry.id,
        entry.method,
        entry.path,
    )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"[{trace_id}] api_query 仅支持只读接口，当前命中 {entry.method} {entry.path}",
    )


def _ensure_active_entry(
    entry: ApiCatalogEntry,
    *,
    trace_id: str,
    interaction_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """拦截未激活目录项，保持 `direct` 与召回链路的一致安全边界。

    功能：
        `nl` 模式默认通过 `status=active` 做 Milvus 标量过滤；`direct` 模式绕过召回后，
        必须在这里补上相同的治理红线，避免前端通过已下线接口 ID 直接穿透执行。
    """
    if entry.status == "active":
        return
    logger.warning(
        "%s blocked inactive endpoint id=%s status=%s path=%s",
        _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
        entry.id,
        entry.status,
        entry.path,
    )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"[{trace_id}] direct 模式仅允许调用激活接口，当前接口状态为 {entry.status}",
    )


def _validate_direct_query_params(
    entry: ApiCatalogEntry,
    params: dict[str, Any],
    *,
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
) -> dict[str, Any]:
    """校验 `direct` 模式的显式参数。

    功能：
        机器构造的快路请求不应该再沿用自然语言链路的“尽量猜”策略。这里严格执行：

        1. 参数名必须命中 schema
        2. required 字段必须齐全

        这样一旦前端拼错字段，就会在网关入口被立刻显式暴露，而不是静默打到业务系统。

    Returns:
        原样返回通过校验的参数字典，供执行计划直接复用。

    Raises:
        HTTPException: 当出现未声明参数或缺失必填参数时抛出 422。
    """
    declared_fields = set(entry.param_schema.properties.keys())
    unknown_fields = [field for field in params if field not in declared_fields]
    if unknown_fields:
        logger.warning(
            "%s direct params rejected id=%s unknown_fields=%s",
            _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
            entry.id,
            unknown_fields,
        )
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"direct 模式存在未声明参数：{', '.join(unknown_fields)}",
        )

    missing_required_params = _find_missing_required_params(entry, params)
    if missing_required_params:
        logger.warning(
            "%s direct params rejected id=%s missing_required=%s",
            _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
            entry.id,
            missing_required_params,
        )
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"direct 模式缺少必要参数：{', '.join(missing_required_params)}",
        )

    return dict(params)


def _build_direct_query_text(entry: ApiCatalogEntry, params: dict[str, Any]) -> str:
    """为快路构造稳定的渲染上下文文本。

    功能：
        `direct` 模式没有自然语言 query，但第五阶段仍需要一段可追踪的 `user_query`
        来参与标题、日志和冻结视图说明。这里用“接口描述 + 关键参数”生成一个稳定摘要。
    """
    if not params:
        return f"直达查询：{entry.description}"
    param_keys = ", ".join(sorted(params.keys()))
    return f"直达查询：{entry.description}（参数：{param_keys}）"


def _raise_direct_query_error(*, trace_id: str, detail: str) -> None:
    """统一抛出 `direct` 模式的 422 错误。

    功能：
        快路失败不允许偷偷回退到自然语言模式；这里统一返回结构化 422，
        让前端和联调日志都能明确感知是“快路契约错误”，而不是网关随机降级。
    """
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"[{trace_id}] {detail}",
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
    intent_catalog = get_business_intent_catalog_service()
    codes = _normalize_business_intent_codes(intent_codes)
    business_intents: list[ApiQueryBusinessIntent] = []
    for code in dict.fromkeys(codes):
        definition = intent_catalog.get_definition(code)
        if definition is None or not definition.enabled or not definition.allow_in_response:
            continue
        business_intents.append(
            ApiQueryBusinessIntent(
                code=code,
                name=definition.name,
                category="write" if definition.category == "write" else "read",
                description=definition.description,
                risk_level=resolve_business_intent_risk_level(code, intent_codes),
            )
        )

    if business_intents:
        return business_intents

    fallback_definition = intent_catalog.get_definition(NOOP_BUSINESS_INTENT)
    if fallback_definition is None:
        return []
    return [
        ApiQueryBusinessIntent(
            code=fallback_definition.code,
            name=fallback_definition.name,
            category="write" if fallback_definition.category == "write" else "read",
            description=fallback_definition.description,
            risk_level=resolve_business_intent_risk_level(fallback_definition.code, intent_codes),
        )
    ]


def _normalize_business_intent_codes(intent_codes: list[str]) -> list[str]:
    """把历史别名与旧只读编码折叠成稳定业务意图。

    功能：
        文档层已经把第二阶段语义收敛为 `saveToServer / deleteCustomer / none`，
        这里负责吸收旧 Prompt、旧 catalog 与高风险别名的历史债务，避免外部契约继续漂移。
    """
    return normalize_business_intent_codes(intent_codes)


def _get_route_allowed_business_intent_codes() -> set[str]:
    """读取第二阶段 Router 白名单。

    功能：
        白名单来源已经迁移到业务意图目录服务，路由层不再维护模块级硬编码 set，
        避免 MySQL 配置、Prompt 注入和响应契约继续各自漂移。
    """
    return get_business_intent_catalog_service().get_allowed_codes()


def _build_runtime_actions(action_codes: set[str] | None = None) -> list[ApiQueryUIAction]:
    """按当前运行时启用状态构造 UI 动作定义。

    功能：
        动作目录已经迁移到 `UICatalogService` 统一治理，路由层只保留“当前请求开放哪些动作”
        这一层决策，避免组件目录和运行时开关继续写死在文件内。
    """
    return _get_ui_catalog_service().build_runtime_actions(action_codes)


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
    components = _get_ui_catalog_service().get_component_codes(intent="query")

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


def _finalize_render_runtime(
    base_runtime: ApiQueryUIRuntime,
    ui_spec: dict[str, Any] | None,
    build_result: UISpecBuildResult,
) -> ApiQueryUIRuntime:
    """根据第五阶段结果收口最终运行时契约。

    功能：
        正常渲染时继续按 Spec 回填组件和动作；一旦触发 Guard 冻结，则主动清空交互能力，
        避免前端在“安全提示页”上仍然暴露详情、分页或潜在写动作。
    """
    finalized_runtime = _finalize_ui_runtime(base_runtime, ui_spec)
    if not build_result.frozen:
        return finalized_runtime

    components = _collect_component_types(ui_spec) or ["PlannerCard", "PlannerNotice"]
    return finalized_runtime.model_copy(
        update={
            "components": components,
            "ui_actions": [],
            "detail": ApiQueryDetailRuntime(),
            "pagination": ApiQueryPaginationRuntime(),
            "template": ApiQueryTemplateRuntime(),
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

    known_action_codes = _get_ui_catalog_service().get_all_action_codes()

    if _is_flat_ui_spec(node):
        for element in node["elements"].values():
            if isinstance(element, dict):
                _walk_action_payload(element, action_types, known_action_codes)
        return action_types

    _walk_action_payload(node, action_types, known_action_codes)
    return action_types


def _is_flat_ui_spec(node: Any) -> bool:
    """判断当前 UI Spec 是否已经是 `root/state/elements` 新协议。"""
    return isinstance(node, dict) and isinstance(node.get("root"), str) and isinstance(node.get("elements"), dict)


def _walk_action_payload(current: Any, action_types: set[str], known_action_codes: set[str]) -> None:
    """递归扫描动作定义载荷。

    功能：
        单独拆出这个 helper，是为了把“flat spec 扫 elements”和“旧树形 Spec 全量扫描”
        复用到同一套动作识别逻辑里，避免任务 1 之后两条分支再度分叉。
    """
    if isinstance(current, dict):
        action_type = current.get("type")
        action_name = current.get("action")
        if isinstance(action_type, str) and action_type in known_action_codes:
            action_types.add(action_type)
        if isinstance(action_name, str) and action_name in known_action_codes:
            action_types.add(action_name)
        for value in current.values():
            _walk_action_payload(value, action_types, known_action_codes)
    elif isinstance(current, list):
        for item in current:
            _walk_action_payload(item, action_types, known_action_codes)


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
    ordered_records = [execution_report.records_by_step_id[step_id] for step_id in execution_report.execution_order]

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
    if (
        step_count == 1
        and anchor_record is not None
        and anchor_record.execution_result.status
        in {
            ApiQueryExecutionStatus.SUCCESS,
            ApiQueryExecutionStatus.EMPTY,
        }
    ):
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
        components=_get_ui_catalog_service().get_component_codes(
            intent="query",
            requested_codes=["PlannerCard", "PlannerTable", "PlannerNotice"],
        ),
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
    interaction_id: str | None,
    conversation_id: str | None,
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
    ui_build_result = await _generate_ui_spec_result(
        dynamic_ui,
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
        trace_id=trace_id,
    )
    ui_runtime = _finalize_render_runtime(base_runtime, ui_build_result.spec, ui_build_result)
    return ApiQueryResponse(
        trace_id=trace_id,
        execution_status=execution_result.status,
        ui_runtime=ui_runtime,
        ui_spec=ui_build_result.spec,
        error=message,
    )


async def _build_stage3_degrade_response(
    dynamic_ui: DynamicUIService,
    *,
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
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
    ui_build_result = await _generate_ui_spec_result(
        dynamic_ui,
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
        trace_id=trace_id,
    )
    ui_runtime = _finalize_render_runtime(base_runtime, ui_build_result.spec, ui_build_result)
    return ApiQueryResponse(
        trace_id=trace_id,
        execution_status=execution_result.status,
        ui_runtime=ui_runtime,
        ui_spec=ui_build_result.spec,
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


async def _generate_ui_spec_result(
    dynamic_ui: DynamicUIService,
    *,
    intent: str,
    data: Any,
    context: dict[str, Any] | None,
    status: ApiQueryExecutionStatus | str | None,
    runtime: ApiQueryUIRuntime | None,
    trace_id: str,
) -> UISpecBuildResult:
    """兼容第五阶段新旧接口，统一返回带 Guard 状态的结果对象。

    功能：
        当前主链已经升级为“Spec + 校验结果”模型，但部分测试替身仍只实现旧
        `generate_ui_spec`。这里提供一层兼容封装，保证路由逻辑先稳定切到新契约，
        再逐步收敛测试和其他调用方。
    """
    if hasattr(dynamic_ui, "generate_ui_spec_result"):
        try:
            return await dynamic_ui.generate_ui_spec_result(
                intent=intent,
                data=data,
                context=context,
                status=status,
                runtime=runtime,
                trace_id=trace_id,
            )
        except TypeError:
            return await dynamic_ui.generate_ui_spec_result(
                intent=intent,
                data=data,
                context=context,
                status=status,
                runtime=runtime,
            )

    try:
        spec = await dynamic_ui.generate_ui_spec(
            intent=intent,
            data=data,
            context=context,
            status=status,
            runtime=runtime,
            trace_id=trace_id,
        )
    except TypeError:
        spec = await dynamic_ui.generate_ui_spec(
            intent=intent,
            data=data,
            context=context,
            status=status,
            runtime=runtime,
        )
    return UISpecBuildResult(spec=spec, validation=UISpecValidationResult(), frozen=False)


def _summarize_validation_errors(validation: UISpecValidationResult) -> str:
    """压缩第五阶段 Guard 错误，便于 route 日志快速定位。"""
    if not validation.errors:
        return "[]"
    items = [f"{error.code}@{error.path}" for error in validation.errors[:5]]
    if len(validation.errors) > 5:
        items.append(f"...(+{len(validation.errors) - 5})")
    return "[" + ", ".join(items) + "]"
