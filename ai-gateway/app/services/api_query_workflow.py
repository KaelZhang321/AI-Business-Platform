from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, status
from langgraph.graph import END, StateGraph

from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionStatus,
    ApiQueryMode,
    ApiQueryPatchTrigger,
    ApiQueryRequest,
    ApiQueryResponse,
    ApiQueryResponseMode,
    ApiQueryRoutingResult,
)
from app.services.api_catalog.dag_executor import ApiDagExecutor
from app.services.api_catalog.dag_planner import ApiDagPlanner, DagPlanValidationError, build_single_step_plan
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.param_extractor import ApiParamExtractor
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource, ApiCatalogSourceError
from app.services.api_catalog.retriever import ApiCatalogRetriever
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchFilters
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_state import (
    ApiQueryDegradeContext,
    ApiQueryMutationFormContext,
    ApiQueryRuntimeContext,
    ApiQueryState,
    build_execution_state,
    summarize_route_hint,
)
from app.services.dynamic_ui_service import DynamicUIService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.workflows.base_workflow import BaseStateGraphWorkflow
from app.services.workflows.graph_events import build_workflow_observability_fields, format_workflow_observability_log
from app.services.workflows.types import WorkflowRunContext, WorkflowTraceContext

logger = logging.getLogger(__name__)

_QUERY_SAFE_METHODS = {"GET", "POST"}
_PATCH_PAGE_SIZE_MAX = 50


class ApiQueryWorkflow(BaseStateGraphWorkflow[ApiQueryState]):
    """`/api-query` 外层静态工作流。

    功能：
        把原先堆在 FastAPI route 中的阶段推进逻辑切到 LangGraph 外层 StateGraph 上，同时
        保持现有领域服务不变：

        1. `direct` 与 `nl` 进入同一个 workflow 外壳
        2. 第二、三阶段失败统一回到 `build_response`
        3. 第四阶段通过 `ApiDagExecutor` 兼容门面进入 LangGraph 内层执行子图

    Edge Cases:
        - `user_token`、原始 candidates 和原始路由结果只保留在 runtime context
        - direct 契约错误继续抛 HTTPException，不偷偷回退自然语言链路
        - 若 workflow 结束时没有产出 response，会抛出运行时错误，避免静默返回空体
    """

    def __init__(
        self,
        *,
        services_getter: Callable[
            [],
            tuple[ApiCatalogRetriever, ApiParamExtractor, ApiExecutor, DynamicUIService, UISnapshotService],
        ],
        planner_getter: Callable[[], ApiDagPlanner],
        response_builder_getter: Callable[[], ApiQueryResponseBuilder],
        registry_source_getter: Callable[[], ApiCatalogRegistrySource],
        allowed_business_intent_codes_getter: Callable[[], set[str]],
    ) -> None:
        super().__init__()
        self._services_getter = services_getter
        self._planner_getter = planner_getter
        self._response_builder_getter = response_builder_getter
        self._registry_source_getter = registry_source_getter
        self._allowed_business_intent_codes_getter = allowed_business_intent_codes_getter
        self._runtime_contexts: dict[str, ApiQueryRuntimeContext] = {}

    @property
    def workflow_name(self) -> str:
        return "api_query_workflow"

    def build_graph(self):
        """构建 `/api-query` 外层静态图。"""

        graph = StateGraph(ApiQueryState)
        graph.add_node("prepare_request", self._prepare_request)
        graph.add_node("prepare_direct_plan", self._prepare_direct_plan)
        graph.add_node("route_query", self._route_query)
        graph.add_node("retrieve_candidates", self._retrieve_candidates)
        graph.add_node("build_plan", self._build_plan)
        graph.add_node("validate_plan", self._validate_plan)
        graph.add_node("execute_plan", self._execute_plan)
        graph.add_node("build_mutation_form", self._build_mutation_form)
        graph.add_node("build_response", self._build_response)

        graph.set_entry_point("prepare_request")
        graph.add_conditional_edges(
            "prepare_request",
            self._route_mode,
            {
                "direct": "prepare_direct_plan",
                "nl": "route_query",
            },
        )
        graph.add_edge("prepare_direct_plan", "execute_plan")
        graph.add_conditional_edges(
            "route_query",
            self._after_route_query,
            {
                "retrieve_candidates": "retrieve_candidates",
                "build_response": "build_response",
            },
        )
        graph.add_conditional_edges(
            "retrieve_candidates",
            self._after_retrieve_candidates,
            {
                "build_plan": "build_plan",
                "build_response": "build_response",
            },
        )
        graph.add_conditional_edges(
            "build_plan",
            self._after_build_plan,
            {
                "validate_plan": "validate_plan",
                "build_mutation_form": "build_mutation_form",
                "build_response": "build_response",
            },
        )
        graph.add_conditional_edges(
            "validate_plan",
            self._after_validate_plan,
            {
                "execute_plan": "execute_plan",
                "build_mutation_form": "build_mutation_form",
                "build_response": "build_response",
            },
        )
        graph.add_edge("execute_plan", "build_response")
        graph.add_edge("build_mutation_form", "build_response")
        graph.add_edge("build_response", END)
        return graph

    async def run(
        self,
        request_body: ApiQueryRequest,
        *,
        trace_id: str,
        interaction_id: str | None,
        conversation_id: str | None,
        user_context: dict[str, Any],
        user_token: str | None,
    ) -> ApiQueryResponse:
        """执行 `/api-query` 外层工作流。

        Args:
            request_body: 当前请求对象。
            trace_id: 单次请求 Trace ID。
            interaction_id: 同一次连续交互内的请求聚合 ID。
            conversation_id: 多轮会话 ID。
            user_context: 从请求上下文提取出的用户事实。
            user_token: 透传给业务系统的授权头。

        Returns:
            与现有 `/api-query` 完全兼容的 `ApiQueryResponse`。

        Raises:
            RuntimeError: 当工作流未产出最终响应时抛出。
        """

        log_prefix = _build_api_query_log_prefix(trace_id, interaction_id, conversation_id)
        request_query = _summarize_request_query(request_body)
        logger.info(
            "%s",
            format_workflow_observability_log(
                f"{log_prefix} request received",
                observability_fields=self._build_observability_fields(
                    trace_id=trace_id,
                    interaction_id=interaction_id,
                    conversation_id=conversation_id,
                    phase="request",
                    node="run",
                ),
                payload={"mode": request_body.mode.value, "query": request_query},
            ),
        )

        self._runtime_contexts[trace_id] = ApiQueryRuntimeContext(
            user_context=user_context,
            user_token=user_token,
            request_body=request_body,
            log_prefix=log_prefix,
        )
        try:
            final_state = await self.invoke(
                {
                    "request_mode": request_body.mode.value,
                    "query_text": request_query,
                    "trace_id": trace_id,
                    "interaction_id": interaction_id,
                    "conversation_id": conversation_id,
                    "candidate_ids": [],
                    "query_domains_hint": [],
                    "business_intent_codes": [],
                    "plan": None,
                    "response_mode": request_body.response_mode,
                    "patch_context": request_body.patch_context,
                    "execution_status": None,
                    "error_code": None,
                    "degrade_reason": None,
                    "degrade_stage": None,
                }
            )
        finally:
            self._runtime_contexts.pop(trace_id, None)

        response = final_state.get("response")
        if response is None:
            raise RuntimeError(f"{self.workflow_name} finished without response")
        return response

    async def _prepare_request(self, state: ApiQueryState) -> dict[str, Any]:
        """工作流入口节点。

        功能：
            第一版外层图只需要显式承认“已完成请求初始化”，不在这里塞额外业务逻辑。
            这样 `prepare_request` 仍是稳定的图入口，后续补指标、幂等或 tracing hook 时
            不需要再改图结构。
        """

        self._log_node_event(state, node="prepare_request", phase="request")
        return {}

    async def _prepare_direct_plan(self, state: ApiQueryState) -> dict[str, Any]:
        """`direct` 快路：构造单步执行计划。"""

        self._log_node_event(state, node="prepare_direct_plan", phase="direct")
        runtime_context = self._get_runtime_context(state)
        request_body = _require_request_body(runtime_context)
        plan, step_entries, query_domains, business_intent_codes, direct_query_text = await self._prepare_direct_execution(
            request_body,
            trace_id=state["trace_id"],
            interaction_id=state.get("interaction_id"),
            conversation_id=state.get("conversation_id"),
        )
        runtime_context.step_entries = step_entries
        return {
            "plan": plan,
            "query_text": direct_query_text,
            "query_domains_hint": query_domains,
            "business_intent_codes": business_intent_codes,
        }

    async def _route_query(self, state: ApiQueryState) -> dict[str, Any]:
        """第二阶段：轻量路由。"""

        self._log_node_event(state, node="route_query", phase="stage2")
        runtime_context = self._get_runtime_context(state)
        request_body = _require_request_body(runtime_context)
        assert request_body.query is not None

        route_hint = await self._get_extractor().route_query(
            request_body.query,
            runtime_context.user_context,
            allowed_business_intents=self._allowed_business_intent_codes_getter(),
            trace_id=state["trace_id"],
        )
        runtime_context.route_hint = route_hint
        updates: dict[str, Any] = {
            "route_hint_summary": summarize_route_hint(route_hint),
            "query_domains_hint": list(route_hint.query_domains),
            "business_intent_codes": list(route_hint.business_intents),
        }
        if route_hint.route_status == "ok":
            return updates

        message = "抱歉，我没有完全理解您的意图，或系统中暂未开放相关查询能力，请尝试换种说法。"
        runtime_context.degrade_context = ApiQueryDegradeContext(
            stage="stage2",
            title="未识别到可用业务域",
            message=message,
            error_code=route_hint.route_error_code or "routing_failed",
            query_domains=list(route_hint.query_domains),
            business_intent_codes=list(route_hint.business_intents),
            reasoning=route_hint.reasoning,
        )
        return {
            **updates,
            "error_code": runtime_context.degrade_context.error_code,
            "degrade_reason": message,
            "degrade_stage": "stage2",
        }

    async def _retrieve_candidates(self, state: ApiQueryState) -> dict[str, Any]:
        """第二阶段：按业务域分层召回候选接口。"""

        self._log_node_event(state, node="retrieve_candidates", phase="stage2")
        runtime_context = self._get_runtime_context(state)
        request_body = _require_request_body(runtime_context)
        assert request_body.query is not None

        retrieval_filters = _build_retrieval_filters(request_body)
        runtime_context.retrieval_filters = retrieval_filters
        candidates = await self._get_retriever().search_stratified(
            request_body.query,
            domains=state.get("query_domains_hint", []),
            top_k=request_body.top_k,
            filters=retrieval_filters,
            trace_id=state["trace_id"],
        )
        runtime_context.candidates = candidates
        if candidates:
            return {"candidate_ids": [candidate.entry.id for candidate in candidates]}

        message = "当前问题没有召回到可执行的查询接口，请调整表达方式后重试。"
        runtime_context.degrade_context = ApiQueryDegradeContext(
            stage="stage2",
            title="未找到匹配接口",
            message=message,
            error_code="no_catalog_match",
            query_domains=list(state.get("query_domains_hint", [])),
            business_intent_codes=list(state.get("business_intent_codes", [])),
            reasoning=(runtime_context.route_hint.reasoning if runtime_context.route_hint else None),
        )
        return {
            "candidate_ids": [],
            "error_code": "no_catalog_match",
            "degrade_reason": message,
            "degrade_stage": "stage2",
        }

    async def _build_plan(self, state: ApiQueryState) -> dict[str, Any]:
        """第三阶段：生成内部执行计划。"""

        self._log_node_event(state, node="build_plan", phase="stage3")
        runtime_context = self._get_runtime_context(state)
        request_body = _require_request_body(runtime_context)
        assert request_body.query is not None

        candidates = runtime_context.candidates
        route_hint = runtime_context.route_hint
        planning_intent_codes = list(state.get("business_intent_codes", []))

        if len(candidates) == 1:
            routing_result = await self._get_extractor().extract_routing_result(
                request_body.query,
                candidates,
                runtime_context.user_context,
                allowed_business_intents=self._allowed_business_intent_codes_getter(),
                routing_hints=route_hint,
                trace_id=state["trace_id"],
            )
            if routing_result.route_status != "ok":
                message = "我找到了相关业务域，但还无法稳定确定具体接口，请补充更明确的查询条件后重试。"
                runtime_context.degrade_context = ApiQueryDegradeContext(
                    stage="stage2",
                    title="无法确定查询接口",
                    message=message,
                    error_code=routing_result.route_error_code or "route_and_extract_failed",
                    query_domains=list(routing_result.query_domains or state.get("query_domains_hint", [])),
                    business_intent_codes=list(routing_result.business_intents or state.get("business_intent_codes", [])),
                    reasoning=routing_result.reasoning or (route_hint.reasoning if route_hint else None),
                )
                return {
                    "error_code": runtime_context.degrade_context.error_code,
                    "degrade_reason": message,
                    "degrade_stage": "stage2",
                    "query_domains_hint": runtime_context.degrade_context.query_domains,
                    "business_intent_codes": runtime_context.degrade_context.business_intent_codes,
                }

            selected_entry = _find_selected_entry(candidates, routing_result)
            if selected_entry is None:
                message = "当前输入关联了多个候选接口，但仍缺少足够信息来确定最终查询目标。"
                runtime_context.degrade_context = ApiQueryDegradeContext(
                    stage="stage2",
                    title="无法确定查询接口",
                    message=message,
                    error_code="selected_api_unresolved",
                    query_domains=list(routing_result.query_domains or state.get("query_domains_hint", [])),
                    business_intent_codes=list(routing_result.business_intents or state.get("business_intent_codes", [])),
                    reasoning=routing_result.reasoning or (route_hint.reasoning if route_hint else None),
                )
                return {
                    "error_code": "selected_api_unresolved",
                    "degrade_reason": message,
                    "degrade_stage": "stage2",
                    "query_domains_hint": runtime_context.degrade_context.query_domains,
                    "business_intent_codes": runtime_context.degrade_context.business_intent_codes,
                }

            planning_intent_codes = list(routing_result.business_intents or state.get("business_intent_codes", []))

            # mutation 接口：不进入执行图，走表单快路。
            if selected_entry.operation_safety == "mutation":
                logger.info(
                    "%s mutation candidate detected api_id=%s — routing to mutation_form path",
                    _build_api_query_log_prefix(
                        state["trace_id"],
                        state.get("interaction_id"),
                        state.get("conversation_id"),
                    ),
                    selected_entry.id,
                )
                runtime_context.mutation_form_context = ApiQueryMutationFormContext(
                    entry=selected_entry,
                    pre_fill_params=dict(routing_result.params),
                    business_intent_code=_resolve_write_intent_code(planning_intent_codes),
                )
                return {"business_intent_codes": planning_intent_codes}

            self._ensure_query_safe_entry(
                selected_entry,
                trace_id=state["trace_id"],
                interaction_id=state.get("interaction_id"),
                conversation_id=state.get("conversation_id"),
            )
            plan = build_single_step_plan(
                selected_entry,
                routing_result.params,
                step_id=_build_step_id(selected_entry),
                plan_id=f"dag_{state['trace_id'][:8]}",
            )
            return {"plan": plan, "business_intent_codes": planning_intent_codes}

        # 多候选 + 写意图时，若候选里只有一个 mutation 接口，优先走表单快路。
        # 这样可以避免被 Planner 噪声（例如 unknown_api / api_id_mismatch）拖入 stage3 降级。
        if _has_write_intent(planning_intent_codes):
            mutation_context = await self._try_build_mutation_form_context(state, runtime_context)
            if mutation_context is not None:
                runtime_context.mutation_form_context = mutation_context
                logger.info(
                    "%s write intent routed to mutation_form path before planner api_id=%s",
                    _build_api_query_log_prefix(
                        state["trace_id"],
                        state.get("interaction_id"),
                        state.get("conversation_id"),
                    ),
                    mutation_context.entry.id,
                )
                return {"business_intent_codes": planning_intent_codes}

        try:
            plan = await self._planner_getter().build_plan(
                request_body.query,
                candidates,
                runtime_context.user_context,
                route_hint,
                trace_id=state["trace_id"],
            )
        except DagPlanValidationError as exc:
            message = "我找到了相关接口，但当前还无法稳定生成可执行的数据流，请补充更明确的查询链路后重试。"
            runtime_context.degrade_context = ApiQueryDegradeContext(
                stage="stage3",
                title="数据执行计划生成失败",
                message=message,
                error_code=exc.code,
                query_domains=list(state.get("query_domains_hint", [])),
                business_intent_codes=planning_intent_codes,
                reasoning=str(exc),
            )
            return {
                "error_code": exc.code,
                "degrade_reason": message,
                "degrade_stage": "stage3",
            }

        return {"plan": plan, "business_intent_codes": planning_intent_codes}

    async def _validate_plan(self, state: ApiQueryState) -> dict[str, Any]:
        """第三阶段：对白名单与依赖关系做确定性校验。"""

        self._log_node_event(state, node="validate_plan", phase="stage3")
        runtime_context = self._get_runtime_context(state)
        try:
            runtime_context.step_entries = self._planner_getter().validate_plan(state["plan"], runtime_context.candidates)
        except DagPlanValidationError as exc:
            # 写意图场景在 stage3 校验失败时，优先尝试转 mutation 表单快路。
            # 真实线上常见失败码不止 planner_unsafe_api（如 planner_unknown_api / api_id_mismatch）。
            if exc.code == "planner_unsafe_api" or _has_write_intent(list(state.get("business_intent_codes", []))):
                mutation_context = await self._try_build_mutation_form_context(state, runtime_context)
                if mutation_context is not None:
                    runtime_context.mutation_form_context = mutation_context
                    logger.info(
                        "%s planner_unsafe_api intercepted — redirected to mutation_form path api_id=%s",
                        _build_api_query_log_prefix(
                            state["trace_id"],
                            state.get("interaction_id"),
                            state.get("conversation_id"),
                        ),
                        mutation_context.entry.id,
                    )
                    return {}

            message = "系统生成的数据依赖图存在安全风险，已终止执行以保护业务系统。"
            runtime_context.degrade_context = ApiQueryDegradeContext(
                stage="stage3",
                title="数据执行计划校验失败",
                message=message,
                error_code=exc.code,
                query_domains=list(state.get("query_domains_hint", [])),
                business_intent_codes=list(state.get("business_intent_codes", [])),
                reasoning=str(exc),
            )
            return {
                "error_code": exc.code,
                "degrade_reason": message,
                "degrade_stage": "stage3",
            }
        return {}

    async def _try_build_mutation_form_context(
        self,
        state: ApiQueryState,
        runtime_context: ApiQueryRuntimeContext,
    ) -> ApiQueryMutationFormContext | None:
        """从候选集中找出 mutation 接口，提取预填参数，构造表单快路上下文。

        功能：
            当多候选路径的 validate_plan 因 planner_unsafe_api 失败时，
            此方法将候选集中的 mutation 接口提取出来，用 LLM 提取用户意图中的参数，
            复用单候选 mutation 路径的表单快路逻辑。

        Returns:
            若候选集中存在 mutation 接口则返回 ApiQueryMutationFormContext，否则返回 None。
        """

        candidates = runtime_context.candidates
        mutation_entries = [candidate.entry for candidate in candidates if candidate.entry.operation_safety == "mutation"]
        if len(mutation_entries) != 1:
            return None
        mutation_entry = mutation_entries[0]

        request_body = _require_request_body(runtime_context)
        query = request_body.query or ""

        # 用 LLM 为 mutation 接口提取预填参数（与单候选路径相同的提取逻辑）
        extractor = self._get_extractor()
        try:
            from app.services.api_catalog.schema import ApiCatalogSearchResult

            routing_result = await extractor.extract_routing_result(
                query,
                [ApiCatalogSearchResult(entry=mutation_entry, score=1.0)],
                runtime_context.user_context,
                trace_id=state["trace_id"],
            )
            pre_fill_params = dict(routing_result.params)
        except Exception:
            logger.warning(
                "%s mutation param extraction failed — using empty pre_fill",
                _build_api_query_log_prefix(
                    state["trace_id"],
                    state.get("interaction_id"),
                    state.get("conversation_id"),
                ),
            )
            pre_fill_params = {}

        planning_intent_codes = list(state.get("business_intent_codes", []))
        return ApiQueryMutationFormContext(
            entry=mutation_entry,
            pre_fill_params=pre_fill_params,
            business_intent_code=_resolve_write_intent_code(planning_intent_codes),
        )



    async def _execute_plan(self, state: ApiQueryState) -> dict[str, Any]:
        """第四阶段：通过兼容门面进入 LangGraph 内层执行图。"""

        self._log_node_event(state, node="execute_plan", phase="stage4")
        runtime_context = self._get_runtime_context(state)
        _, _, executor, _, _ = self._services_getter()
        dag_executor = ApiDagExecutor(executor)
        execution_report = await dag_executor.execute_plan(
            state["plan"],
            runtime_context.step_entries,
            user_token=runtime_context.user_token,
            trace_id=state["trace_id"],
            interaction_id=state.get("interaction_id"),
            conversation_id=state.get("conversation_id"),
        )
        runtime_context.execution_state = build_execution_state(
            plan=state["plan"],
            trace_id=state["trace_id"],
            records_by_step_id=execution_report.records_by_step_id,
            execution_order=execution_report.execution_order,
        )
        return {}

    async def _build_mutation_form(self, state: ApiQueryState) -> dict[str, Any]:
        """mutation 表单快路节点：不执行变更，只生成预填表单响应。

        功能：
            当 `_build_plan` 识别到单候选 mutation 接口时，workflow 直接跳过
            validate_plan / execute_plan，进入此节点生成预填表单 UI Spec，
            交给 `build_response` 返回给前端。

            前端拿到响应后，在用户确认前不会发起任何写请求；确认后直接调用
            `ui_runtime.form.api_id` 指向的业务系统接口提交修改。
        """

        self._log_node_event(state, node="build_mutation_form", phase="stage3")
        # 此节点不做实际计算；mutation_form_context 已在 _build_plan 中写入 runtime_context。
        # build_response 会根据 mutation_form_context != None 分支到 build_mutation_form_response。
        return {}

    async def _build_response(self, state: ApiQueryState) -> dict[str, Any]:
        """统一响应出口。

        功能：
            外层图里不再允许第二、三、四阶段各自 `return ApiQueryResponse`。所有主路径和
            降级路径都统一汇总到这里，再交给 response builder 折叠成对外契约。
        """

        self._log_node_event(state, node="build_response", phase="response", execution_status=state.get("execution_status"))
        runtime_context = self._get_runtime_context(state)
        builder = self._response_builder_getter()
        if runtime_context.degrade_context is not None:
            degrade_context = runtime_context.degrade_context
            if degrade_context.stage == "stage2":
                response = await builder.build_stage2_degrade_response(
                    state=state,
                    title=degrade_context.title,
                    message=degrade_context.message,
                    error_code=degrade_context.error_code,
                    query_domains=degrade_context.query_domains,
                    business_intent_codes=degrade_context.business_intent_codes,
                    reasoning=degrade_context.reasoning,
                )
            else:
                response = await builder.build_stage3_degrade_response(
                    state=state,
                    title=degrade_context.title,
                    message=degrade_context.message,
                    error_code=degrade_context.error_code,
                    query_domains=degrade_context.query_domains,
                    business_intent_codes=degrade_context.business_intent_codes,
                    reasoning=degrade_context.reasoning,
                )
        elif runtime_context.mutation_form_context is not None:
            mutation_ctx = runtime_context.mutation_form_context
            response = await builder.build_mutation_form_response(
                state=state,
                entry=mutation_ctx.entry,
                pre_fill_params=mutation_ctx.pre_fill_params,
                business_intent_code=mutation_ctx.business_intent_code,
                query_domains_hint=state.get("query_domains_hint", []),
            )
        else:
            if runtime_context.execution_state is None:
                raise RuntimeError("ApiQueryWorkflow build_response called without execution_state")
            response = await builder.build_execution_response(
                state=state,
                runtime_context=runtime_context,
                execution_state=runtime_context.execution_state,
                query_domains_hint=state.get("query_domains_hint", []),
                business_intent_codes=state.get("business_intent_codes", []),
                response_mode=state["response_mode"],
                patch_context=state.get("patch_context"),
            )

        self._log_node_event(
            state,
            node="build_response",
            phase="response",
            execution_status=response.execution_status,
        )

        return {
            "response": response,
            "execution_status": response.execution_status,
            "ui_runtime": response.ui_runtime,
            "ui_spec": response.ui_spec,
            "plan": response.execution_plan,
        }

    def _route_mode(self, state: ApiQueryState) -> str:
        """决定进入 `direct` 还是 `nl` 分支。"""

        return "direct" if state["request_mode"] == ApiQueryMode.DIRECT.value else "nl"

    def _after_route_query(self, state: ApiQueryState) -> str:
        """第二阶段路由后的去向。"""

        return "build_response" if state.get("degrade_stage") else "retrieve_candidates"

    def _after_retrieve_candidates(self, state: ApiQueryState) -> str:
        """召回完成后的去向。"""

        return "build_response" if state.get("degrade_stage") else "build_plan"

    def _after_build_plan(self, state: ApiQueryState) -> str:
        """计划生成后的去向。"""

        if state.get("degrade_stage"):
            return "build_response"
        runtime_context = self._get_runtime_context(state)
        if runtime_context.mutation_form_context is not None:
            return "build_mutation_form"
        return "validate_plan"

    def _after_validate_plan(self, state: ApiQueryState) -> str:
        """计划校验后的去向。"""

        if state.get("degrade_stage"):
            return "build_response"
        runtime_context = self._get_runtime_context(state)
        if runtime_context.mutation_form_context is not None:
            return "build_mutation_form"
        return "execute_plan"


    def _get_runtime_context(self, state: ApiQueryState) -> ApiQueryRuntimeContext:
        """按 trace_id 读取当前请求的 runtime context。"""

        trace_id = state["trace_id"]
        runtime_context = self._runtime_contexts.get(trace_id)
        if runtime_context is None:
            raise RuntimeError(f"runtime context missing for trace_id={trace_id}")
        return runtime_context

    def _get_retriever(self) -> ApiCatalogRetriever:
        """读取当前 retriever 依赖。"""

        retriever, _, _, _, _ = self._services_getter()
        return retriever

    def _get_extractor(self) -> ApiParamExtractor:
        """读取当前 extractor 依赖。"""

        _, extractor, _, _, _ = self._services_getter()
        return extractor

    def _log_node_event(
        self,
        state: ApiQueryState,
        *,
        node: str,
        phase: str,
        execution_status: ApiQueryExecutionStatus | str | None = None,
    ) -> None:
        """输出统一节点观测日志。

        功能：
            wave 4 的目标不是新增功能，而是把工作流迁移后的最小观测字段固定下来。这里
            每个核心节点都走同一套日志格式，后续接指标或 SSE 时可以直接复用。
        """

        logger.info(
            "%s",
            format_workflow_observability_log(
                "api_query workflow node",
                observability_fields=self._build_observability_fields(
                    trace_id=state["trace_id"],
                    interaction_id=state.get("interaction_id"),
                    conversation_id=state.get("conversation_id"),
                    phase=phase,
                    node=node,
                    execution_status=execution_status,
                ),
            ),
        )

    def _build_observability_fields(
        self,
        *,
        trace_id: str,
        interaction_id: str | None,
        conversation_id: str | None,
        phase: str,
        node: str,
        execution_status: ApiQueryExecutionStatus | str | None = None,
    ) -> dict[str, Any]:
        """构造当前工作流节点的最小观测字段。"""

        return build_workflow_observability_fields(
            run_context=WorkflowRunContext(
                workflow_name=self.workflow_name,
                trace_context=WorkflowTraceContext(
                    trace_id=trace_id,
                    interaction_id=interaction_id,
                    conversation_id=conversation_id,
                ),
                phase=phase,
            ),
            node=node,
            execution_status=str(execution_status.value if isinstance(execution_status, ApiQueryExecutionStatus) else execution_status)
            if execution_status is not None
            else None,
        )

    async def _prepare_direct_execution(
        self,
        request_body: ApiQueryRequest,
        *,
        trace_id: str,
        interaction_id: str | None,
        conversation_id: str | None,
    ) -> tuple[ApiQueryExecutionPlan, dict[str, ApiCatalogEntry], list[str], list[str], str]:
        """为 `direct` 快路准备单步执行计划。"""

        assert request_body.direct_query is not None

        registry_source = self._registry_source_getter()
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
        self._ensure_query_safe_entry(entry, trace_id=trace_id, interaction_id=interaction_id, conversation_id=conversation_id)
        validated_params = _validate_direct_query_params(
            entry,
            direct_query.params,
            trace_id=trace_id,
            interaction_id=interaction_id,
            conversation_id=conversation_id,
        )
        _validate_direct_patch_request(
            request_body,
            entry,
            validated_params,
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

    def _ensure_query_safe_entry(
        self,
        entry: ApiCatalogEntry,
        *,
        trace_id: str,
        interaction_id: str | None,
        conversation_id: str | None,
    ) -> None:
        """强制拦截非查询安全接口。"""

        if entry.operation_safety == "mutation":
            logger.warning(
                "%s blocked non-query-safe endpoint id=%s safety=%s method=%s path=%s",
                _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
                entry.id,
                entry.operation_safety,
                entry.method,
                entry.path,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"[{trace_id}] api_query 仅支持查询安全接口，当前接口语义为 {entry.operation_safety}",
            )

        if entry.method in _QUERY_SAFE_METHODS:
            return
        logger.warning(
            "%s blocked non-query-method endpoint id=%s method=%s path=%s",
            _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
            entry.id,
            entry.method,
            entry.path,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"[{trace_id}] api_query 仅支持 GET/POST 查询接口，当前命中 {entry.method} {entry.path}",
        )


def _require_request_body(runtime_context: ApiQueryRuntimeContext) -> ApiQueryRequest:
    """读取并校验请求体。"""

    if runtime_context.request_body is None:
        raise RuntimeError("ApiQueryWorkflow runtime context missing request_body")
    return runtime_context.request_body


def _build_api_query_log_prefix(trace_id: str, interaction_id: str | None, conversation_id: str | None) -> str:
    """统一构造 `api_query` 日志前缀。"""

    return f"api_query[trace={trace_id} interaction={interaction_id or '-'} conversation={conversation_id or '-'}]"


def _summarize_request_query(request_body: ApiQueryRequest) -> str:
    """生成适合日志与审计的请求摘要。"""

    if request_body.mode == ApiQueryMode.DIRECT and request_body.direct_query is not None:
        return f"direct:{request_body.direct_query.api_id}"
    return (request_body.query or "")[:100]


def _build_retrieval_filters(request_body: ApiQueryRequest) -> ApiCatalogSearchFilters:
    """构造第二阶段召回使用的标量过滤器。"""

    return ApiCatalogSearchFilters(
        statuses=["active"],
        envs=_dedupe_non_empty([item.strip().lower() for item in request_body.envs]),
        tag_names=_dedupe_non_empty([item.strip() for item in request_body.tag_names]),
    )


def _dedupe_non_empty(values: list[str]) -> list[str]:
    """对过滤入参做去空与去重。"""

    deduped: list[str] = []
    for value in values:
        if not value or value in deduped:
            continue
        deduped.append(value)
    return deduped


def _find_selected_entry(candidates: list[Any], routing_result: ApiQueryRoutingResult) -> ApiCatalogEntry | None:
    """根据路由结果从候选集中找出最终命中接口。"""

    return next(
        (candidate.entry for candidate in candidates if candidate.entry.id == routing_result.selected_api_id),
        None,
    )


def _ensure_active_entry(
    entry: ApiCatalogEntry,
    *,
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
) -> None:
    """拦截未激活目录项，保持 `direct` 与召回链路的一致安全边界。"""

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
    """校验 `direct` 模式的显式参数。"""

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


def _validate_direct_patch_request(
    request_body: ApiQueryRequest,
    entry: ApiCatalogEntry,
    params: dict[str, Any],
    *,
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
) -> None:
    """校验列表 patch 快路的专属约束。"""

    if request_body.response_mode != ApiQueryResponseMode.PATCH:
        return

    log_prefix = _build_api_query_log_prefix(trace_id, interaction_id, conversation_id)
    pagination_hint = entry.pagination_hint
    if entry.method != "GET" or not pagination_hint.enabled:
        logger.warning("%s direct patch rejected id=%s reason=unsupported_entry", log_prefix, entry.id)
        _raise_direct_query_error(
            trace_id=trace_id,
            detail="PATCH_MODE_NOT_SUPPORTED: 当前接口不是开启分页能力的只读 GET 列表接口",
        )

    page_param = pagination_hint.page_param or "pageNum"
    page_size_param = pagination_hint.page_size_param or "pageSize"
    missing_pagination_params = [param_name for param_name in (page_param, page_size_param) if param_name not in params]
    if missing_pagination_params:
        logger.warning(
            "%s direct patch rejected id=%s missing_pagination_params=%s",
            log_prefix,
            entry.id,
            missing_pagination_params,
        )
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"PATCH_MODE_NOT_SUPPORTED: patch 模式必须显式提供分页参数：{', '.join(missing_pagination_params)}",
        )

    page_size_value = params.get(page_size_param)
    if isinstance(page_size_value, (int, float)) and int(page_size_value) > _PATCH_PAGE_SIZE_MAX:
        logger.warning(
            "%s direct patch rejected id=%s page_size=%s over_limit=%s",
            log_prefix,
            entry.id,
            page_size_value,
            _PATCH_PAGE_SIZE_MAX,
        )
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"patch 模式下 {page_size_param} 不能超过 {_PATCH_PAGE_SIZE_MAX}",
        )

    patch_context = request_body.patch_context
    if patch_context is None:
        return

    if patch_context.trigger in {ApiQueryPatchTrigger.FILTER_SUBMIT, ApiQueryPatchTrigger.FILTER_RESET}:
        page_value = params.get(page_param)
        if page_value != 1:
            logger.warning(
                "%s direct patch rejected id=%s trigger=%s invalid_page_reset=%s",
                log_prefix,
                entry.id,
                patch_context.trigger.value,
                page_value,
            )
            _raise_direct_query_error(
                trace_id=trace_id,
                detail=f"patch 模式下触发 {patch_context.trigger.value} 时必须将 {page_param} 重置为 1",
            )


def _build_direct_query_text(entry: ApiCatalogEntry, params: dict[str, Any]) -> str:
    """为快路构造稳定的渲染上下文文本。"""

    if not params:
        return f"直达查询：{entry.description}"
    return f"直达查询：{entry.description}（参数：{', '.join(sorted(params.keys()))}）"


def _raise_direct_query_error(*, trace_id: str, detail: str) -> None:
    """统一抛出 `direct` 模式的 422 错误。"""

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"[{trace_id}] {detail}",
    )


def _find_missing_required_params(entry: ApiCatalogEntry, params: dict[str, Any]) -> list[str]:
    """找出当前请求缺失的必填参数。"""

    missing: list[str] = []
    for field in entry.param_schema.required:
        value = params.get(field)
        if value in (None, "", [], {}):
            missing.append(field)
    return missing


def _build_step_id(entry: ApiCatalogEntry) -> str:
    """生成稳定步骤 ID。"""

    return f"step_{entry.id}"


def _resolve_write_intent_code(business_intent_codes: list[str]) -> str:
    """从路由意图编码列表中解析写意图编码。

    功能：
        mutation form 快路需要明确知道当前是哪个业务意图，以便在提交契约中
        传递 `business_intent`。这里优先取明确写意图，兜底到 `saveToServer`。
    """

    write_intents = [code for code in business_intent_codes if code and code != "none"]
    return write_intents[0] if write_intents else "saveToServer"


def _has_write_intent(business_intent_codes: list[str]) -> bool:
    """判断当前路由结果是否包含写意图编码。"""

    return any(code and code != "none" for code in business_intent_codes)
