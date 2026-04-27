from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, status
from langgraph.graph import END, StateGraph

from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionStatus,
    ApiQueryRequest,
    ApiQueryResponse,
    ApiQueryRoutingResult,
)
from app.services.api_catalog.dag_executor import ApiDagExecutor
from app.services.api_catalog.dag_planner import ApiDagPlanner, DagPlanValidationError, build_single_step_plan
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.param_extractor import ApiParamExtractor
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_catalog.retriever import ApiCatalogRetriever
from app.services.api_catalog.schema import (
    ApiCatalogEntry,
    ApiCatalogPredecessorSpec,
    ApiCatalogSearchFilters,
)
from app.services.customer_profile_fixed_service import CustomerProfileFixedService
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_state import (
    ApiQueryDegradeContext,
    ApiQueryDeletePreviewContext,
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
_DELETE_LOOKUP_PAGE_SIZE = 20
_DELETE_ENTRY_KEYWORDS = ("delete", "remove", "del", "删除", "移除", "清除", "注销", "作废")
_DELETE_LOOKUP_SEGMENT_KEYWORDS = ("list", "page", "query", "search", "get", "detail", "info", "select")
_DELETE_LOOKUP_NAME_FIELD_KEYWORDS = ("name", "keyword", "keywords", "title", "query", "search")
_DELETE_LOOKUP_EXCLUDED_FIELDS = {
    "id",
    "ids",
    "status",
    "page",
    "pageno",
    "pagenum",
    "pagesize",
    "size",
    "limit",
    "sortfield",
    "sortorder",
    "starttime",
    "endtime",
    "createby",
    "updateby",
    "createtime",
    "updatetime",
}
_DELETE_NAME_PATTERNS = (
    re.compile(
        r"(?:删除|移除|清除|注销|作废)(?:一个|一名|一条|一个名为|名为)?(?P<name>.+?)(?:角色|账号|部门|岗位|员工|用户)\s*$"
    ),
    re.compile(
        r"(?:删除|移除|清除|注销|作废).*(?:角色|账号|部门|岗位|员工|用户)[：: ]+(?P<name>[^，。；;]+)\s*$"
    ),
)

_PREDECESSOR_SELECT_MODE_TO_BINDING_TEMPLATE = {
    "single": "$[{step_id}.data].{source_path}",
    "first": "$[{step_id}.data].{source_path}",
    "all": "$[{step_id}.data][*].{source_path}",
    "user_select": "$[{step_id}.data][*].{source_path}",
}


class ApiQueryWorkflow(BaseStateGraphWorkflow[ApiQueryState]):
    """`/api-query` 外层静态工作流。

    功能：
        把原先堆在 FastAPI route 中的阶段推进逻辑切到 LangGraph 外层 StateGraph 上，同时
        保持现有领域服务不变：

        1. 统一自然语言入口，先路由再召回再规划
        2. 第二、三阶段失败统一回到 `build_response`
        3. 第四阶段通过 `ApiDagExecutor` 兼容门面进入 LangGraph 内层执行子图

    Edge Cases:
        - `user_token`、原始 candidates 和原始路由结果只保留在 runtime context
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
        customer_profile_service: CustomerProfileFixedService | None = None,
    ) -> None:
        super().__init__()
        self._services_getter = services_getter
        self._planner_getter = planner_getter
        self._response_builder_getter = response_builder_getter
        self._registry_source_getter = registry_source_getter
        self._allowed_business_intent_codes_getter = allowed_business_intent_codes_getter
        self._customer_profile_service = customer_profile_service or CustomerProfileFixedService()
        self._runtime_contexts: dict[str, ApiQueryRuntimeContext] = {}

    @property
    def workflow_name(self) -> str:
        return "api_query_workflow"

    def build_graph(self):
        """构建 `/api-query` 外层静态图。

        功能：
            外层图的职责是把自然语言主链路、写意图快路和降级出口收敛到一个稳定骨架，
            这样新增阶段节点时只需调整图，不需要再回到 route 层改分支判断。

        Returns:
            已注册节点与条件边的 `StateGraph`。

        Edge Cases:
            - 所有降级路径最终都汇入 `build_response`，避免不同节点直接返回不一致响应
            - mutation/delete 快路不进入执行图，防止读链误触发写接口
        """

        graph = StateGraph(ApiQueryState)
        graph.add_node("prepare_request", self._prepare_request)
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
            self._after_prepare_request,
            {
                "route_query": "route_query",
                "build_response": "build_response",
            },
        )
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
        # 所有成功、写快路和降级分支都只允许从一个出口折叠响应，保证返回契约稳定。
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

        Edge Cases:
            - runtime context 必须按 trace_id 隔离，避免并发请求互相污染用户上下文
            - 即使 invoke 抛错，也要在 finally 中清理 runtime context，防止内存泄漏
            - 工作流结束但没有 response 会被视为编排错误，显式抛出而不是返回空体
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
                payload={"query": request_query},
            ),
        )

        # 运行时重对象只放在请求级 side table，避免 LangGraph state 挂载敏感数据。
        self._runtime_contexts[trace_id] = ApiQueryRuntimeContext(
            user_context=user_context,
            user_token=user_token,
            request_body=request_body,
            selection_context=(
                dict(request_body.selection_context)
                if isinstance(request_body.selection_context, dict)
                else None
            ),
            log_prefix=log_prefix,
        )
        try:
            final_state = await self.invoke(
                {
                    "request_mode": "nl",
                    "query_text": request_query,
                    "trace_id": trace_id,
                    "interaction_id": interaction_id,
                    "conversation_id": conversation_id,
                    "candidate_ids": [],
                    "query_domains_hint": [],
                    "business_intent_codes": [],
                    "plan": None,
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
            在通用 route/retrieve/plan 之前先处理高确定性的客户档案固定分支。该分支的接口清单、
            参数绑定和 UI 顺序都来自业务确认的 Excel active endpoint 元数据，不应再交给 LLM
            自由规划。

        Returns:
            未命中固定分支时返回空增量；命中时直接写入最终响应，让状态图进入统一响应出口。

        Edge Cases:
            - 固定分支资源不可用时会回退通用链路，不影响原 `/api-query` 能力
            - 多客户候选会在这里短路为 wait-select，避免下游 15 个档案接口扩散调用
        """

        self._log_node_event(state, node="prepare_request", phase="request")
        runtime_context = self._get_runtime_context(state)
        request_body = _require_request_body(runtime_context)
        _, _, executor, _, _ = self._services_getter()

        # 固定客户档案是确定性业务页，必须先于通用召回处理，避免 LLM 把它规划成单接口问数。
        response = await self._customer_profile_service.handle(
            request_body=request_body,
            executor=executor,
            user_token=runtime_context.user_token,
            user_id=_resolve_runtime_user_id(runtime_context.user_context),
            trace_id=state["trace_id"],
        )
        if response is None:
            return {}

        logger.info(
            "%s",
            format_workflow_observability_log(
                f"{runtime_context.log_prefix} customer profile fixed branch matched",
                observability_fields=self._build_observability_fields(
                    trace_id=state["trace_id"],
                    interaction_id=state.get("interaction_id"),
                    conversation_id=state.get("conversation_id"),
                    phase="request",
                    node="prepare_request",
                    execution_status=response.execution_status,
                ),
                payload={"execution_status": response.execution_status, "has_error": bool(response.error)},
            ),
        )
        return {
            "response": response,
            "execution_status": response.execution_status,
            "ui_spec": response.ui_spec,
            "plan": response.execution_plan,
            "query_domains_hint": ["customer_profile"],
            "business_intent_codes": ["customer_profile_fixed"],
        }

    async def _route_query(self, state: ApiQueryState) -> dict[str, Any]:
        """第二阶段：轻量路由。

        功能：
            在不触碰候选检索的前提下，先判断当前问题属于哪个业务域和意图集合，为后续
            分层召回缩小范围。这样可以减少多域混召带来的噪声和误匹配。

        Returns:
            路由提示摘要及域/意图更新；失败时同时写入降级原因。

        Edge Cases:
            - route_status 非 `ok` 时不会继续召回，避免把错误域提示放大成检索噪声
            - 路由失败仍保留 reasoning/query_domains，便于前端和日志解释为什么降级
        """

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
        self._log_routing_intent_summary(state, route_hint)
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
        """第二阶段：按业务域分层召回候选接口。

        功能：
            这一层负责把路由提示转成实际的目录检索约束，尽量在进入 planner 之前先把
            候选集压到“少而准”的范围，避免第三阶段被无关接口拖垮。

        Returns:
            候选 ID 列表；未召回时返回降级状态字段。

        Edge Cases:
            - 自然语言模式才会记录 retrieval filters，供后续快照审计复盘
            - 候选为空时立即降级，不允许 planner 在空候选上继续猜接口
        """

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
        runtime_context.subgraph_result = self._get_subgraph_result_for_trace(state["trace_id"])
        self._log_retrieved_candidates(state, candidates)
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
        """第三阶段：生成内部执行计划。

        功能：
            这里统一承接“单候选确定执行”“多候选交给 planner”“写意图改走确认快路”三类
            决策，保证 route 层和 response builder 不需要知道 planner 的分支细节。

        Returns:
            计划、业务意图或降级状态增量；写意图快路会把上下文写入 runtime_context。

        Edge Cases:
            - 单候选 mutation 不进入执行图，优先改写为 mutation/delete 预检快路
            - 多候选写意图即使 planner 失败，也应尽量回退到确认页而不是直接 Notice
            - `selected_entry` 无法解析时按 stage2 降级处理，避免把“路由未定”误报成 planner 失败
        """

        self._log_node_event(state, node="build_plan", phase="stage3")
        runtime_context = self._get_runtime_context(state)
        request_body = _require_request_body(runtime_context)
        assert request_body.query is not None

        candidates = runtime_context.candidates
        route_hint = runtime_context.route_hint
        planning_intent_codes = list(state.get("business_intent_codes", []))

        # 单候选优先走 extractor 精确提参；只有真正多候选才让 planner 参与选路。
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
                write_intent_code = _resolve_write_intent_code(planning_intent_codes)
                if write_intent_code == "deleteCustomer":
                    delete_preview_context = await self._try_build_delete_preview_context(
                        state,
                        runtime_context,
                        selected_entry=selected_entry,
                        business_intent_code=write_intent_code,
                        pre_fill_params=dict(routing_result.params),
                    )
                    if delete_preview_context is not None:
                        runtime_context.delete_preview_context = delete_preview_context
                        logger.info(
                            "%s delete mutation candidate detected api_id=%s — routing to delete preview path",
                            _build_api_query_log_prefix(
                                state["trace_id"],
                                state.get("interaction_id"),
                                state.get("conversation_id"),
                            ),
                            selected_entry.id,
                        )
                        return {"business_intent_codes": planning_intent_codes}

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
            plan = await self._build_single_candidate_plan(
                state=state,
                runtime_context=runtime_context,
                selected_entry=selected_entry,
                selected_params=dict(routing_result.params),
            )
            self._log_planner_dag_summary(state, plan)
            return {"plan": plan, "business_intent_codes": planning_intent_codes}

        # 多候选 + 写意图时，优先尝试确认页/表单快路。
        # 这一步的目标是把“可确认的写请求”从 planner 噪声里提前捞出来。
        if _has_write_intent(planning_intent_codes):
            write_intent_code = _resolve_write_intent_code(planning_intent_codes)
            if write_intent_code == "deleteCustomer":
                delete_preview_context = await self._try_build_delete_preview_context(
                    state,
                    runtime_context,
                    business_intent_code=write_intent_code,
                )
                if delete_preview_context is not None:
                    runtime_context.delete_preview_context = delete_preview_context
                    logger.info(
                        "%s delete intent routed to delete preview path before planner api_id=%s",
                        _build_api_query_log_prefix(
                            state["trace_id"],
                            state.get("interaction_id"),
                            state.get("conversation_id"),
                        ),
                        delete_preview_context.delete_entry.id,
                    )
                    return {"business_intent_codes": planning_intent_codes}

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
            expanded_candidates, predecessor_hints = await self._expand_candidates_with_predecessors(
                candidates,
                trace_id=state["trace_id"],
                interaction_id=state.get("interaction_id"),
                conversation_id=state.get("conversation_id"),
            )
            runtime_context.candidates = expanded_candidates
            runtime_context.predecessor_hints = predecessor_hints
            plan = await self._planner_getter().build_plan(
                request_body.query,
                expanded_candidates,
                runtime_context.user_context,
                route_hint,
                predecessor_hints=predecessor_hints,
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

        self._log_planner_dag_summary(state, plan)
        return {"plan": plan, "business_intent_codes": planning_intent_codes}

    async def _validate_plan(self, state: ApiQueryState) -> dict[str, Any]:
        """第三阶段：对白名单与依赖关系做确定性校验。

        功能：
            planner 的输出仍需经过执行前硬校验，确保步骤只引用已召回目录项、依赖图安全，
            并在必要时把失败改写为更适合用户确认的写快路。

        Returns:
            成功时返回空增量；失败时写入降级状态，或把 mutation/delete 上下文挂入 runtime_context。

        Edge Cases:
            - 删除写意图在 validate 失败时仍会尝试回退到 delete preview，而不是直接 Notice
            - `planner_unsafe_api` 之外的写意图错误同样允许转 mutation form，避免误伤可确认写请求
        """

        self._log_node_event(state, node="validate_plan", phase="stage3")
        runtime_context = self._get_runtime_context(state)
        try:
            runtime_context.step_entries = self._validate_plan_with_runtime_context(
                state["plan"],
                runtime_context.candidates,
                predecessor_hints=runtime_context.predecessor_hints,
                subgraph_result=runtime_context.subgraph_result,
                trace_id=state["trace_id"],
            )
        except DagPlanValidationError as exc:
            self._log_validate_plan_failure(state, runtime_context, exc)
            write_intent_code = _resolve_write_intent_code(list(state.get("business_intent_codes", [])))
            if write_intent_code == "deleteCustomer":
                delete_preview_context = await self._try_build_delete_preview_context(
                    state,
                    runtime_context,
                    business_intent_code=write_intent_code,
                )
                if delete_preview_context is not None:
                    runtime_context.delete_preview_context = delete_preview_context
                    logger.info(
                        "%s delete preview intercepted validate_plan failure — api_id=%s",
                        _build_api_query_log_prefix(
                            state["trace_id"],
                            state.get("interaction_id"),
                            state.get("conversation_id"),
                        ),
                        delete_preview_context.delete_entry.id,
                    )
                    return {}

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

        Edge Cases:
            - 若全候选路由已经稳定选中 mutation 接口，优先复用该结果，避免唯一 mutation 候选被误忽略
            - 全候选路由失败时才回退到“唯一 mutation 接口”启发式，降低误选概率
        """

        request_body = _require_request_body(runtime_context)
        query = request_body.query or ""
        extractor = self._get_extractor()

        candidates = runtime_context.candidates
        route_hint = runtime_context.route_hint

        # 1. 优先复用“在完整候选集上的最终选中结果”。
        # 多 mutation 候选是创建类写意图的常见场景；如果路由阶段已经稳定选中了某个
        # mutation 接口，就不应该再因为 `len(mutation_entries) != 1` 被打回 Notice。
        try:
            routing_result = await extractor.extract_routing_result(
                query,
                candidates,
                runtime_context.user_context,
                allowed_business_intents=self._allowed_business_intent_codes_getter(),
                routing_hints=route_hint,
                trace_id=state["trace_id"],
            )
            selected_entry = _find_selected_entry(candidates, routing_result)
            if selected_entry is not None and selected_entry.operation_safety == "mutation":
                planning_intent_codes = list(routing_result.business_intents or state.get("business_intent_codes", []))
                return ApiQueryMutationFormContext(
                    entry=selected_entry,
                    pre_fill_params=dict(routing_result.params),
                    business_intent_code=_resolve_write_intent_code(planning_intent_codes),
                )
        except Exception:
            logger.warning(
                "%s mutation candidate routing failed — fallback to unique mutation candidate",
                _build_api_query_log_prefix(
                    state["trace_id"],
                    state.get("interaction_id"),
                    state.get("conversation_id"),
                ),
            )

        mutation_entries = [candidate.entry for candidate in candidates if candidate.entry.operation_safety == "mutation"]
        if len(mutation_entries) != 1:
            return None
        mutation_entry = mutation_entries[0]

        # 2. 兼容旧策略：当候选里只有一个 mutation 接口时，即便全候选路由不稳定，
        # 仍然直接针对这条 mutation 接口做参数提取，避免写意图退化成 stage3 Notice。
        try:
            from app.services.api_catalog.schema import ApiCatalogSearchResult

            routing_result = await extractor.extract_routing_result(
                query,
                [ApiCatalogSearchResult(entry=mutation_entry, score=1.0)],
                runtime_context.user_context,
                trace_id=state["trace_id"],
            )
            pre_fill_params = dict(routing_result.params)
            planning_intent_codes = list(routing_result.business_intents or state.get("business_intent_codes", []))
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

    async def _try_build_delete_preview_context(
        self,
        state: ApiQueryState,
        runtime_context: ApiQueryRuntimeContext,
        *,
        selected_entry: ApiCatalogEntry | None = None,
        business_intent_code: str = "deleteCustomer",
        pre_fill_params: dict[str, Any] | None = None,
    ) -> ApiQueryDeletePreviewContext | None:
        """删除类 mutation 先查候选，再决定返回确认页还是候选列表。

        功能：
            删除接口往往没有稳定的 request_schema，直接生成空表单会把前端逼到“盲删”。
            这里统一把删除意图改成“只读预检”：

            1. 从 query 中提取待删实体名称
            2. 找到同资源的查询接口
            3. 执行一次只读查询拿候选
            4. 根据 0/1/N 条结果生成后续 UI

        Args:
            state: 当前工作流状态。
            runtime_context: 当前请求运行时上下文。
            selected_entry: 已经明确选中的删除接口；若为空则从候选集中再解析。
            business_intent_code: 当前删除业务意图编码。
            pre_fill_params: 上游已提取出的删除参数，可用于无查询候选时直接兜底。

        Returns:
            删除预检上下文；若无法稳定定位删除接口则返回 `None`。

        Edge Cases:
            - 找不到同资源查询接口时，会尝试基于 pre_fill/name 直接构造确认 payload，避免把简单删除全部打回
            - 删除前置查询失败或缺参时统一回 unresolved，强制人工补充信息，避免盲删
            - 单命中与多命中会返回不同 status，供响应层决定确认页还是候选列表
        """

        request_body = _require_request_body(runtime_context)
        query_text = request_body.query or ""

        delete_entry = selected_entry or await self._resolve_delete_mutation_entry(state, runtime_context)
        if delete_entry is None:
            return None

        target_name = _infer_delete_target_name(query_text)
        # if not target_name:
        #     return ApiQueryDeletePreviewContext(
        #         delete_entry=delete_entry,
        #         status="unresolved",
        #         business_intent_code=business_intent_code,
        #         message="当前无法从请求中稳定识别待删除角色名称，请补充更具体条件后重试。",
        #     )

        # 先基于当前候选集判断是否存在可用查询接口，再决定是否走“直接确认”兜底。
        candidate_lookup_entries = [
            candidate.entry
            for candidate in runtime_context.candidates
            if candidate.entry.id != delete_entry.id and _score_delete_lookup_entry(delete_entry, candidate.entry) > 0
        ]
        if not candidate_lookup_entries:
            direct_submit_payload = _build_direct_delete_submit_payload(
                delete_entry=delete_entry,
                pre_fill_params=pre_fill_params or {},
                target_name=target_name,
            )
            if not direct_submit_payload:
                return ApiQueryDeletePreviewContext(
                    delete_entry=delete_entry,
                    status="unresolved",
                    business_intent_code=business_intent_code,
                    target_name=target_name,
                    message=f"当前无法确认“{target_name}”的删除参数，请补充更具体条件后重试。",
                )

            direct_row = dict(direct_submit_payload)
            primary_field = next(iter(direct_submit_payload.keys()))
            return ApiQueryDeletePreviewContext(
                delete_entry=delete_entry,
                status="confirm",
                business_intent_code=business_intent_code,
                target_name=target_name,
                identifier_field=primary_field,
                matched_rows=[direct_row],
                submit_payload=direct_submit_payload,
            )

        lookup_entry = await self._find_delete_lookup_entry(delete_entry=delete_entry, runtime_context=runtime_context)
        if lookup_entry is None:
            return ApiQueryDeletePreviewContext(
                delete_entry=delete_entry,
                status="unresolved",
                business_intent_code=business_intent_code,
                target_name=target_name,
                message=f"当前无法在删除前定位“{target_name}”的角色查询接口，请稍后重试或补充更具体条件。",
            )

        # 删除预检必须先构造一笔安全、可复盘的只读查询，而不是直接把用户短句塞给删除接口。
        lookup_params = _build_delete_lookup_params(lookup_entry, target_name=target_name)
        missing_required_params = _find_missing_required_params(lookup_entry, lookup_params)
        if missing_required_params:
            return ApiQueryDeletePreviewContext(
                delete_entry=delete_entry,
                status="unresolved",
                business_intent_code=business_intent_code,
                target_name=target_name,
                lookup_entry=lookup_entry,
                lookup_params=lookup_params,
                message=(
                    "删除前置查询缺少必要条件，当前无法安全确认待删除角色："
                    f"{', '.join(missing_required_params)}"
                ),
            )

        _, _, executor, _, _ = self._services_getter()
        try:
            lookup_result = await executor.call(
                lookup_entry,
                lookup_params,
                user_token=runtime_context.user_token,
                user_id=_resolve_runtime_user_id(runtime_context.user_context),
                trace_id=state["trace_id"],
            )
        except Exception as exc:
            logger.warning(
                "%s delete preview lookup crashed api_id=%s error=%s",
                runtime_context.log_prefix,
                lookup_entry.id,
                exc,
            )
            return ApiQueryDeletePreviewContext(
                delete_entry=delete_entry,
                status="unresolved",
                business_intent_code=business_intent_code,
                target_name=target_name,
                lookup_entry=lookup_entry,
                lookup_params=lookup_params,
                message="删除前置查询失败，当前无法安全确认待删除角色，请稍后重试。",
            )

        if lookup_result.status == ApiQueryExecutionStatus.ERROR:
            return ApiQueryDeletePreviewContext(
                delete_entry=delete_entry,
                status="unresolved",
                business_intent_code=business_intent_code,
                target_name=target_name,
                lookup_entry=lookup_entry,
                lookup_params=lookup_params,
                message=lookup_result.error or "删除前置查询失败，当前无法安全确认待删除角色。",
            )

        matched_rows = _filter_delete_lookup_rows(_normalize_preview_rows(lookup_result.data), target_name=target_name)
        identifier_field = _resolve_delete_identifier_field(
            delete_entry=delete_entry,
            lookup_entry=lookup_entry,
            rows=matched_rows,
        )
        if not matched_rows:
            return ApiQueryDeletePreviewContext(
                delete_entry=delete_entry,
                status="missing",
                business_intent_code=business_intent_code,
                target_name=target_name,
                identifier_field=identifier_field,
                lookup_entry=lookup_entry,
                lookup_params=lookup_params,
                message=f"不存在名为“{target_name}”的角色，无需执行删除。",
            )

        return ApiQueryDeletePreviewContext(
            delete_entry=delete_entry,
            status="confirm" if len(matched_rows) == 1 else "candidates",
            business_intent_code=business_intent_code,
            target_name=target_name,
            identifier_field=identifier_field,
            matched_rows=matched_rows,
            submit_payload=(
                _build_delete_lookup_submit_payload(
                    delete_entry=delete_entry,
                    row=matched_rows[0],
                    identifier_field=identifier_field,
                )
                if len(matched_rows) == 1
                else {}
            ),
            lookup_entry=lookup_entry,
            lookup_params=lookup_params,
        )

    async def _resolve_delete_mutation_entry(
        self,
        state: ApiQueryState,
        runtime_context: ApiQueryRuntimeContext,
    ) -> ApiCatalogEntry | None:
        """在候选集中定位本次删除意图对应的 mutation 接口。

        功能：
            删除预检依赖一个明确的 delete mutation 作为最终提交目标。这里先尊重路由器
            的显式选中结果，再退回到删除语义启发式，尽量降低误把查询接口当成删除接口的风险。

        Returns:
            最匹配的删除 mutation 目录项；无法确定时返回 `None`。

        Edge Cases:
            - 路由失败不会直接终止，而是继续尝试唯一 mutation / 删除关键词启发式兜底
            - 多个 mutation 并存时只优先选择显著带删除语义的目录项，避免误删其他写接口
        """

        candidates = runtime_context.candidates
        if not candidates:
            return None

        route_hint = runtime_context.route_hint
        request_body = _require_request_body(runtime_context)
        extractor = self._get_extractor()

        try:
            routing_result = await extractor.extract_routing_result(
                request_body.query or "",
                candidates,
                runtime_context.user_context,
                allowed_business_intents=self._allowed_business_intent_codes_getter(),
                routing_hints=route_hint,
                trace_id=state["trace_id"],
            )
            selected_entry = _find_selected_entry(candidates, routing_result)
            if selected_entry is not None and selected_entry.operation_safety == "mutation":
                return selected_entry
        except Exception:
            logger.warning(
                "%s delete mutation routing failed — fallback to mutation candidate heuristic",
                runtime_context.log_prefix,
            )

        mutation_entries = [candidate.entry for candidate in candidates if candidate.entry.operation_safety == "mutation"]
        if len(mutation_entries) == 1:
            return mutation_entries[0]

        ranked_entries = [entry for entry in mutation_entries if _is_delete_mutation_entry(entry)]
        if len(ranked_entries) == 1:
            return ranked_entries[0]
        return ranked_entries[0] if ranked_entries else None

    async def _find_delete_lookup_entry(
        self,
        *,
        delete_entry: ApiCatalogEntry,
        runtime_context: ApiQueryRuntimeContext,
    ) -> ApiCatalogEntry | None:
        """为删除预检找到同资源的只读查询接口。"""

        candidate_entries = [candidate.entry for candidate in runtime_context.candidates if candidate.entry.id != delete_entry.id]

        ranked_candidates: list[tuple[int, ApiCatalogEntry]] = []
        for entry in candidate_entries:
            score = _score_delete_lookup_entry(delete_entry, entry)
            if score > 0:
                ranked_candidates.append((score, entry))

        if not ranked_candidates:
            return None
        ranked_candidates.sort(key=lambda item: item[0], reverse=True)
        return ranked_candidates[0][1]



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
            user_id=_resolve_runtime_user_id(runtime_context.user_context),
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

    async def _build_single_candidate_plan(
        self,
        *,
        state: ApiQueryState,
        runtime_context: ApiQueryRuntimeContext,
        selected_entry: ApiCatalogEntry,
        selected_params: dict[str, Any],
    ) -> ApiQueryExecutionPlan:
        """单候选路径下构建含前置步骤的执行计划。"""
        predecessors = list(selected_entry.predecessors)
        if not predecessors:
            return build_single_step_plan(
                selected_entry,
                selected_params,
                step_id=_build_step_id(selected_entry),
                plan_id=f"dag_{state['trace_id'][:8]}",
            )

        registry = self._registry_source_getter()
        predecessor_steps: list[tuple[str, ApiCatalogEntry, dict[str, Any], bool]] = []
        selected_context = runtime_context.selection_context if isinstance(runtime_context.selection_context, dict) else {}
        selected_values_by_binding = _parse_user_select_values(selected_context.get("user_select"))

        for predecessor in predecessors:
            predecessor_entry = await registry.get_entry_by_id(predecessor.predecessor_api_id)
            if predecessor_entry is None:
                if predecessor.required:
                    raise DagPlanValidationError(
                        "planner_missing_required_predecessor",
                        f"缺少必需前置接口: {predecessor.predecessor_api_id}",
                    )
                continue
            if predecessor_entry.id == selected_entry.id:
                raise DagPlanValidationError(
                    "planner_invalid_predecessor_self_dependency",
                    f"前置接口不能指向自身: {selected_entry.id}",
                )
            self._ensure_query_safe_entry(
                predecessor_entry,
                trace_id=state["trace_id"],
                interaction_id=state.get("interaction_id"),
                conversation_id=state.get("conversation_id"),
            )

            predecessor_step_id = _build_step_id(predecessor_entry)
            if predecessor_step_id not in {item[0] for item in predecessor_steps}:
                predecessor_steps.append((predecessor_step_id, predecessor_entry, {}, predecessor.required))
            for binding in predecessor.param_bindings:
                select_mode = binding.select_mode
                source_path = _normalize_predecessor_source_path(
                    binding.source_path,
                    response_data_path=predecessor_entry.response_data_path,
                )
                if not source_path:
                    continue

                binding_key = f"{predecessor_entry.id}:{binding.target_param}:{source_path}"
                if select_mode == "user_select" and binding_key in selected_values_by_binding:
                    selected_params[binding.target_param] = selected_values_by_binding[binding_key]
                    continue

                expression = _build_predecessor_binding_expression(
                    step_id=predecessor_step_id,
                    source_path=source_path,
                    select_mode=select_mode,
                )
                selected_params[binding.target_param] = expression

        from app.models.schemas import ApiQueryPlanStep

        main_step_id = _build_step_id(selected_entry)
        steps: list[ApiQueryPlanStep] = [
            ApiQueryPlanStep(
                step_id=step_id,
                api_id=entry.id,
                api_path=entry.path,
                params=dict(params),
                depends_on=[],
            )
            for step_id, entry, params, _required in predecessor_steps
        ]
        steps.append(
            ApiQueryPlanStep(
                step_id=main_step_id,
                api_id=selected_entry.id,
                api_path=selected_entry.path,
                params=dict(selected_params),
                depends_on=[item[0] for item in predecessor_steps],
            )
        )
        return ApiQueryExecutionPlan(
            plan_id=f"dag_{state['trace_id'][:8]}",
            steps=steps,
        )

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

        Returns:
            对最终 `ApiQueryResponse` 的 state 增量镜像，供 workflow state 保持一致。

        Edge Cases:
            - delete preview、mutation form、执行成功三条主路互斥，优先级必须固定
            - 如果没有 execution_state 且也不属于任一快路，会抛错暴露编排缺陷
        """

        self._log_node_event(state, node="build_response", phase="response", execution_status=state.get("execution_status"))
        runtime_context = self._get_runtime_context(state)
        builder = self._response_builder_getter()
        # 固定分支已经在 prepare_request 构造出完整响应，这里仍走统一出口以保持日志与 state 镜像一致。
        if state.get("response") is not None:
            response = state["response"]
        # 响应优先级按“降级 -> 删除预检 -> mutation 表单 -> 正常执行”固定，
        # 这样状态推进再复杂，最终出口也只有一套可预测决策。
        elif runtime_context.degrade_context is not None:
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
        elif runtime_context.delete_preview_context is not None:
            response = await builder.build_delete_preview_response(
                state=state,
                delete_preview_context=runtime_context.delete_preview_context,
                created_by=_resolve_runtime_user_id(runtime_context.user_context),
            )
        elif runtime_context.mutation_form_context is not None:
            mutation_ctx = runtime_context.mutation_form_context
            response = await builder.build_mutation_form_response(
                state=state,
                entry=mutation_ctx.entry,
                pre_fill_params=mutation_ctx.pre_fill_params,
                business_intent_code=mutation_ctx.business_intent_code,
                query_domains_hint=state.get("query_domains_hint", []),
                created_by=_resolve_runtime_user_id(runtime_context.user_context),
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

    def _after_prepare_request(self, state: ApiQueryState) -> str:
        """入口准备后的去向。"""

        return "build_response" if state.get("response") is not None else "route_query"

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
        if runtime_context.delete_preview_context is not None:
            return "build_response"
        if runtime_context.mutation_form_context is not None:
            return "build_mutation_form"
        return "validate_plan"

    def _after_validate_plan(self, state: ApiQueryState) -> str:
        """计划校验后的去向。"""

        if state.get("degrade_stage"):
            return "build_response"
        runtime_context = self._get_runtime_context(state)
        if runtime_context.delete_preview_context is not None:
            return "build_response"
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

    def _get_subgraph_result_for_trace(self, trace_id: str):
        """读取当前 trace 对应的 Stage 2 子图摘要。

        功能：
            Wave 2 已经把子图缓存在 hybrid retriever 里，但 workflow 还需要显式把这份
            事实接到 runtime context，Stage 3 才能基于同一次召回结果做确定性校验。
        """

        retriever = self._get_retriever()
        get_subgraph_result = getattr(retriever, "get_subgraph_result", None)
        if callable(get_subgraph_result):
            return get_subgraph_result(trace_id)
        return None

    def _validate_plan_with_runtime_context(
        self,
        plan: ApiQueryExecutionPlan,
        candidates: list[Any],
        *,
        predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]] | None,
        subgraph_result,
        trace_id: str,
    ) -> dict[str, ApiCatalogEntry]:
        """兼容新旧 planner seam 的 Stage 3 校验入口。

        功能：
            这次改动把 Stage 2 子图正式接进 Stage 3，但现有测试桩和少量旧注入对象还只实现了
            `validate_plan(plan, candidates)`。这里做一次兼容分发，避免过渡期把所有调用方一次性打碎。
        """

        planner = self._planner_getter()
        try:
            return planner.validate_plan(
                plan,
                candidates,
                predecessor_hints=predecessor_hints,
                subgraph_result=subgraph_result,
                trace_id=trace_id,
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            return planner.validate_plan(plan, candidates)

    async def _expand_candidates_with_predecessors(
        self,
        candidates: list[Any],
        *,
        trace_id: str,
        interaction_id: str | None,
        conversation_id: str | None,
    ) -> tuple[list[Any], dict[str, list[ApiCatalogPredecessorSpec]]]:
        """扩展多候选集合并补齐 predecessor hints。

        功能：
            多候选规划前，先把候选接口上的前置依赖补齐为可规划白名单，并输出结构化 hints
            给 Planner 提示词。required predecessor 缺失时在 Stage 3 直接失败，避免把不完整
            的图纸交给后续执行阶段。
        """

        expanded_candidates = list(candidates)
        seen_api_ids = {candidate.entry.id for candidate in expanded_candidates}
        predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]] = {}
        registry = self._registry_source_getter()

        for candidate in candidates:
            entry = candidate.entry
            specs = list(entry.predecessors)
            if not specs:
                continue
            predecessor_hints[entry.id] = specs
            for spec in specs:
                if spec.predecessor_api_id in seen_api_ids:
                    continue
                predecessor_entry = await registry.get_entry_by_id(spec.predecessor_api_id)
                if predecessor_entry is None:
                    if spec.required:
                        raise DagPlanValidationError(
                            "planner_missing_required_predecessor",
                            f"缺少必需前置接口: {spec.predecessor_api_id}",
                            metadata={
                                "target_api_id": entry.id,
                                "required_predecessor_api_id": spec.predecessor_api_id,
                            },
                        )
                    continue
                self._ensure_query_safe_entry(
                    predecessor_entry,
                    trace_id=trace_id,
                    interaction_id=interaction_id,
                    conversation_id=conversation_id,
                )
                from app.services.api_catalog.schema import ApiCatalogSearchResult

                expanded_candidates.append(ApiCatalogSearchResult(entry=predecessor_entry, score=candidate.score))
                seen_api_ids.add(predecessor_entry.id)
        return expanded_candidates, predecessor_hints

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

    def _log_routing_intent_summary(self, state: ApiQueryState, route_hint: ApiQueryRoutingResult) -> None:
        """输出路由阶段识别结果摘要。"""

        logger.info(
            "%s",
            format_workflow_observability_log(
                "api_query route intent summary",
                observability_fields=self._build_observability_fields(
                    trace_id=state["trace_id"],
                    interaction_id=state.get("interaction_id"),
                    conversation_id=state.get("conversation_id"),
                    phase="stage2",
                    node="route_query_summary",
                ),
                payload={
                    "query_domains": list(route_hint.query_domains),
                    "business_intent_codes": list(route_hint.business_intents),
                    "route_status": route_hint.route_status,
                },
            ),
        )

    def _log_retrieved_candidates(self, state: ApiQueryState, candidates: list[Any]) -> None:
        """输出召回接口摘要。"""

        candidate_items: list[dict[str, Any]] = []
        for candidate in candidates:
            entry = getattr(candidate, "entry", None)
            if entry is None:
                continue
            candidate_items.append(
                {
                    "api_id": entry.id,
                    "api_path": entry.path,
                    "domain": entry.domain,
                    "method": entry.method,
                    "score": getattr(candidate, "score", None),
                }
            )

        logger.info(
            "%s",
            format_workflow_observability_log(
                "api_query retrieved candidates",
                observability_fields=self._build_observability_fields(
                    trace_id=state["trace_id"],
                    interaction_id=state.get("interaction_id"),
                    conversation_id=state.get("conversation_id"),
                    phase="stage2",
                    node="retrieve_candidates_summary",
                ),
                payload={
                    "candidate_count": len(candidate_items),
                    "candidates": candidate_items,
                },
            ),
        )

    def _log_planner_dag_summary(self, state: ApiQueryState, plan: ApiQueryExecutionPlan) -> None:
        """输出 Planner 产出的 DAG 依赖图摘要。"""

        dag_edges: list[dict[str, Any]] = [
            {
                "step_id": step.step_id,
                "api_id": step.api_id,
                "api_path": step.api_path,
                "depends_on": list(step.depends_on),
            }
            for step in plan.steps
        ]

        logger.info(
            "%s",
            format_workflow_observability_log(
                "api_query planner dag summary",
                observability_fields=self._build_observability_fields(
                    trace_id=state["trace_id"],
                    interaction_id=state.get("interaction_id"),
                    conversation_id=state.get("conversation_id"),
                    phase="stage3",
                    node="build_plan_summary",
                ),
                payload={
                    "plan_id": plan.plan_id,
                    "step_count": len(plan.steps),
                    "steps": dag_edges,
                },
            ),
        )

    def _log_validate_plan_failure(
        self,
        state: ApiQueryState,
        runtime_context: ApiQueryRuntimeContext,
        exc: DagPlanValidationError,
    ) -> None:
        """输出 Stage 3 validate 失败的定位日志。"""

        plan = state.get("plan")
        plan_steps = []
        if isinstance(plan, ApiQueryExecutionPlan):
            plan_steps = [
                {
                    "step_id": step.step_id,
                    "api_id": step.api_id,
                    "api_path": step.api_path,
                    "depends_on": list(step.depends_on),
                    "param_keys": sorted(step.params.keys()),
                }
                for step in plan.steps
            ]

        candidate_items: list[dict[str, Any]] = []
        for candidate in runtime_context.candidates:
            entry = getattr(candidate, "entry", None)
            if entry is None:
                continue
            candidate_items.append(
                {
                    "api_id": entry.id,
                    "api_path": entry.path,
                    "method": entry.method,
                    "domain": entry.domain,
                    "operation_safety": entry.operation_safety,
                }
            )

        subgraph = runtime_context.subgraph_result
        subgraph_summary = {
            "available": subgraph is not None,
            "graph_degraded": bool(subgraph.graph_degraded) if subgraph is not None else None,
            "degraded_reason": subgraph.degraded_reason if subgraph is not None else None,
            "anchor_api_ids": list(subgraph.anchor_api_ids) if subgraph is not None else [],
            "support_api_ids": list(subgraph.support_api_ids) if subgraph is not None else [],
            "field_path_count": len(subgraph.field_paths) if subgraph is not None else 0,
        }

        logger.warning(
            "%s",
            format_workflow_observability_log(
                "api_query stage3 validate failure",
                observability_fields=self._build_observability_fields(
                    trace_id=state["trace_id"],
                    interaction_id=state.get("interaction_id"),
                    conversation_id=state.get("conversation_id"),
                    phase="stage3",
                    node="validate_plan_failure",
                ),
                payload={
                    "error_code": exc.code,
                    "error_message": exc.message,
                    "error_metadata": exc.metadata,
                    "query_domains_hint": list(state.get("query_domains_hint", [])),
                    "business_intent_codes": list(state.get("business_intent_codes", [])),
                    "plan_step_count": len(plan_steps),
                    "plan_steps": plan_steps,
                    "candidate_count": len(candidate_items),
                    "candidates": candidate_items,
                    "subgraph": subgraph_summary,
                },
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

    def _ensure_query_safe_entry(
        self,
        entry: ApiCatalogEntry,
        *,
        trace_id: str,
        interaction_id: str | None,
        conversation_id: str | None,
    ) -> None:
        """强制拦截非查询安全接口。

        功能：
            `/api-query` 的系统边界是“读链安全执行”。这里把 mutation 语义和非 GET/POST
            查询方法统一拦下，保证执行阶段不会触发写链路。

        Edge Cases:
            - operation_safety 只要是 mutation 就直接 422，不允许 method 侥幸穿透
            - POST 仍可视为查询安全，但前提是目录明确标记为非 mutation
        """

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


def _resolve_runtime_user_id(user_context: dict[str, Any]) -> str | None:
    """从请求级用户上下文提取最终用户主键。

    功能：
        `/api-query` 第二阶段到第四阶段都共享同一份 `user_context`。把“最终用于 runtime invoke
        的用户主键”集中收敛在这里，可以避免 workflow、delete preview、执行图分别手写
        `dict.get("userId")` 与空值判断，降低后续身份字段扩展时的遗漏风险。

    Args:
        user_context: route 层通过身份中间件注入的请求级用户事实。

    Returns:
        规范化后的最终用户主键；若上下文中不存在，则返回 `None`。

    Edge Cases:
        - 空字符串或纯空白 `userId` 会被视为缺失，避免污染 runtime invoke 的 `createdBy`
    """
    raw_user_id = user_context.get("userId")
    if raw_user_id is None:
        return None
    normalized_user_id = str(raw_user_id).strip()
    return normalized_user_id or None


def _summarize_request_query(request_body: ApiQueryRequest) -> str:
    """生成适合日志与审计的请求摘要。"""
    return request_body.query[:100]


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


def _parse_user_select_values(raw: Any) -> dict[str, Any]:
    """解析用户选择上下文为绑定键值映射。"""
    if not isinstance(raw, dict):
        return {}
    key = raw.get("key")
    if isinstance(key, str) and key.strip():
        return {key.strip(): raw.get("value")}

    values: dict[str, Any] = {}
    for binding_key, value in raw.items():
        if not isinstance(binding_key, str):
            continue
        normalized_key = binding_key.strip()
        if not normalized_key:
            continue
        values[normalized_key] = value
    return values


def _normalize_predecessor_source_path(source_path: str, *, response_data_path: str) -> str:
    """把 predecessor source_path 转换为绑定表达式可消费格式。

    约定：
        predecessor metadata 的 `source_path` 推荐始终写成相对 `execution_result.data`
        的路径（如 `$.idCard`）。为了兼容历史元数据，仍支持把原始响应根路径
        （如 `$.result.records[*].idCard`）自动折算到 `execution_result.data` 语义下。
    """
    raw = str(source_path or "").strip()
    if not raw:
        return ""
    raw = raw.removeprefix("$").lstrip(".").replace("[]", "[*]")
    normalized_response_data_path = (
        str(response_data_path or "").strip().removeprefix("$").lstrip(".").replace("[]", "[*]")
    )

    for prefix in (normalized_response_data_path, "data"):
        stripped = _strip_predecessor_source_prefix(raw, prefix)
        if stripped is not None:
            raw = stripped
            break

    raw = raw.lstrip(".")
    if raw.startswith("[*]."):
        raw = raw[len("[*].") :]
    elif raw == "[*]":
        return ""
    return raw


def _build_predecessor_binding_expression(*, step_id: str, source_path: str, select_mode: str) -> str:
    """构造受限 DAG 绑定表达式。"""
    normalized_mode = select_mode if select_mode in _PREDECESSOR_SELECT_MODE_TO_BINDING_TEMPLATE else "single"
    template = _PREDECESSOR_SELECT_MODE_TO_BINDING_TEMPLATE[normalized_mode]
    return template.format(step_id=step_id, source_path=source_path)


def _strip_predecessor_source_prefix(path: str, prefix: str) -> str | None:
    """剥离 `source_path` 中的上游响应根前缀。"""

    normalized_prefix = str(prefix or "").strip().removeprefix("$").lstrip(".").replace("[]", "[*]")
    if not normalized_prefix:
        return None

    if path == normalized_prefix or path == f"{normalized_prefix}[*]":
        return ""

    dotted_prefix = f"{normalized_prefix}."
    if path.startswith(dotted_prefix):
        return path[len(dotted_prefix) :]

    wildcard_prefix = f"{normalized_prefix}[*]."
    if path.startswith(wildcard_prefix):
        return path[len(wildcard_prefix) :]

    return None


def _find_missing_required_params(entry: ApiCatalogEntry, params: dict[str, Any]) -> list[str]:
    """找出当前请求缺失的必填参数。

    功能：
        删除预检和单步计划都需要一套一致的“缺参判定”语义。统一在这里做空值规则，
        避免不同调用链出现“有的把空字符串算有效、有的当缺失”的分歧。
    """

    missing: list[str] = []
    for field in entry.param_schema.required:
        value = params.get(field)
        if value in (None, "", [], {}):
            missing.append(field)
    return missing


def _infer_delete_target_name(query_text: str) -> str | None:
    """从“删除健管师角色”这类短句中抽取删除目标名称。"""

    normalized_query = " ".join(str(query_text or "").split())
    if not normalized_query:
        return None

    for pattern in _DELETE_NAME_PATTERNS:
        match = pattern.search(normalized_query)
        if not match:
            continue
        candidate = str(match.group("name") or "").strip().strip("“”\"'‘’：:，。,.;； ")
        candidate = re.sub(r"^(?:一个|一名|一条|名为|叫做|叫)\s*", "", candidate)
        candidate = candidate.strip()
        if candidate:
            return candidate
    return None


def _is_delete_mutation_entry(entry: ApiCatalogEntry) -> bool:
    """基于接口元数据判断当前 mutation 是否更像删除语义。"""

    if entry.operation_safety != "mutation":
        return False
    haystack = f"{entry.description} {entry.path}".lower()
    return any(keyword in haystack for keyword in _DELETE_ENTRY_KEYWORDS)


def _score_delete_lookup_entry(delete_entry: ApiCatalogEntry, candidate: ApiCatalogEntry) -> int:
    """为删除预检选择最匹配的只读查询接口。

    功能：
        删除预检需要一条“尽可能能查到待删对象”的只读接口。这里用确定性打分替代 LLM，
        保证删除前置查询的选择可审计、可复现。

    Returns:
        匹配分数；0 表示不适合作为删除预检查询接口。

    Edge Cases:
        - mutation 或删除语义接口直接记 0，防止预检链路误走到写接口
        - 路径同目录、共享资源词和名称筛选字段会叠加加分，优先选择可精确定位对象的查询接口
    """

    if candidate.operation_safety == "mutation" or candidate.method not in _QUERY_SAFE_METHODS:
        return 0
    if _is_delete_mutation_entry(candidate):
        return 0

    score = 0
    if candidate.operation_safety == "list":
        score += 6
    elif candidate.operation_safety == "query":
        score += 4

    if candidate.domain and delete_entry.domain and candidate.domain == delete_entry.domain:
        score += 3

    delete_dir = delete_entry.path.rsplit("/", 1)[0].lower()
    candidate_path = candidate.path.lower()
    if delete_dir and candidate_path.startswith(delete_dir):
        score += 10

    last_segment = candidate_path.rsplit("/", 1)[-1]
    if any(keyword in last_segment for keyword in _DELETE_LOOKUP_SEGMENT_KEYWORDS):
        score += 4

    shared_tokens = _extract_lookup_tokens(delete_entry.path, delete_entry.description) & _extract_lookup_tokens(
        candidate.path,
        candidate.description,
    )
    score += min(len(shared_tokens), 4) * 2

    if _find_delete_lookup_name_field(candidate):
        score += 3
    return score


def _extract_lookup_tokens(*texts: str) -> set[str]:
    """抽取路径与描述中的资源词，用于删除预检接口匹配。"""

    tokens: set[str] = set()
    for text in texts:
        for token in re.split(r"[^a-zA-Z0-9]+", str(text or "").lower()):
            normalized = token.strip()
            if len(normalized) < 3 or normalized in _DELETE_ENTRY_KEYWORDS or normalized in _DELETE_LOOKUP_SEGMENT_KEYWORDS:
                continue
            tokens.add(normalized)
    return tokens


def _find_delete_lookup_name_field(entry: ApiCatalogEntry) -> str | None:
    """找到最适合按名称筛选候选记录的查询字段。

    功能：
        删除前置查询最好按“实体名称”缩小候选范围。这里优先从 schema 字段名和标题里找到
        最像名称/关键字输入的字段，避免把状态、分页等控制字段误当成筛选主条件。

    Returns:
        最优名称筛选字段；若 schema 无合适字段则返回 `None`。

    Edge Cases:
        - 只考虑字符串字段，防止把数值型主键误用成模糊名称查询条件
        - 若没有明显 name-like 字段，会退回首个可用字符串字段，保证预检仍可尝试执行
    """

    properties = entry.param_schema.properties
    if not properties:
        return None

    preferred_fields = [
        field_name
        for field_name, schema in properties.items()
        if str(schema.get("type") or "string").lower() == "string"
        and field_name.lower() not in _DELETE_LOOKUP_EXCLUDED_FIELDS
    ]
    if not preferred_fields:
        return None

    for field_name in preferred_fields:
        lower_name = field_name.lower()
        if lower_name.endswith("name") or lower_name in {"name", "roleName".lower(), "realname"}:
            return field_name

    for field_name in preferred_fields:
        lower_name = field_name.lower()
        if any(keyword in lower_name for keyword in _DELETE_LOOKUP_NAME_FIELD_KEYWORDS):
            return field_name

    for field_name in preferred_fields:
        title = str(properties[field_name].get("title") or properties[field_name].get("label") or "").strip()
        if any(keyword in title for keyword in ("名称", "名字", "姓名", "关键字")):
            return field_name

    return preferred_fields[0]


def _build_delete_lookup_params(entry: ApiCatalogEntry, *, target_name: str) -> dict[str, Any]:
    """组装删除预检查询参数。"""

    lookup_field = _find_delete_lookup_name_field(entry)
    if not lookup_field:
        return {}

    params: dict[str, Any] = {lookup_field: target_name}
    properties = entry.param_schema.properties

    page_param = entry.pagination_hint.page_param or _find_first_existing_field(
        properties,
        ("pageNum", "pageNo", "page", "currentPage"),
    )
    page_size_param = entry.pagination_hint.page_size_param or _find_first_existing_field(
        properties,
        ("pageSize", "size", "limit"),
    )
    if page_param and page_param in properties:
        params[page_param] = 1
    if page_size_param and page_size_param in properties:
        params[page_size_param] = _DELETE_LOOKUP_PAGE_SIZE
    return params


def _find_first_existing_field(properties: dict[str, Any], field_names: tuple[str, ...]) -> str | None:
    """按优先级找到 schema 中存在的字段名。"""

    for field_name in field_names:
        if field_name in properties:
            return field_name
    return None


def _normalize_preview_rows(data: Any) -> list[dict[str, Any]]:
    """把删除预检查询结果统一压成行数组。"""

    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [dict(data)]
    return []


def _filter_delete_lookup_rows(rows: list[dict[str, Any]], *, target_name: str) -> list[dict[str, Any]]:
    """优先按名称精确匹配删除候选；找不到精确值时回退原结果。

    功能：
        删除预检的目标不是“尽可能返回更多数据”，而是帮助用户快速确认真正要删哪一条。
        因此这里优先做精确名命中，其次做包含匹配，最后才退回原始候选列表。

    Returns:
        过滤后的候选行列表。

    Edge Cases:
        - 若没有任何名称列命中，不会强行清空结果，而是回退原列表供用户人工确认
        - 同一行多个名称字段命中时只记一次，避免重复候选
    """

    if not rows:
        return []

    normalized_target = _normalize_delete_match_value(target_name)
    exact_matches: list[dict[str, Any]] = []
    fuzzy_matches: list[dict[str, Any]] = []

    for row in rows:
        row_hit = False
        for field_name, value in row.items():
            if not isinstance(value, str):
                continue
            if not _is_name_like_delete_field(field_name):
                continue

            normalized_value = _normalize_delete_match_value(value)
            if normalized_value == normalized_target:
                exact_matches.append(row)
                row_hit = True
                break
            if normalized_target and normalized_target in normalized_value:
                fuzzy_matches.append(row)
                row_hit = True
                break
        if row_hit:
            continue

    if exact_matches:
        return exact_matches
    if fuzzy_matches:
        return fuzzy_matches
    return rows


def _normalize_delete_match_value(value: str) -> str:
    """规整删除匹配值，减少空白和大小写噪声。"""

    return "".join(str(value or "").strip().lower().split())


def _is_name_like_delete_field(field_name: str) -> bool:
    """判断当前字段是否更像实体名称列。"""

    normalized = field_name.lower()
    return normalized.endswith("name") or normalized in {"name", "rolename", "realname"} or "name" in normalized


def _resolve_delete_identifier_field(
    *,
    delete_entry: ApiCatalogEntry,
    lookup_entry: ApiCatalogEntry | None,
    rows: list[dict[str, Any]],
) -> str:
    """决定删除动作应从候选记录里读取哪个主键字段。"""

    row_keys = list(rows[0].keys()) if rows else []

    preferred_keys: list[str] = []
    if lookup_entry is not None and lookup_entry.detail_hint.identifier_field:
        preferred_keys.append(lookup_entry.detail_hint.identifier_field)
    preferred_keys.extend(
        [field_name for field_name in delete_entry.param_schema.properties if field_name.lower().endswith("id")]
    )
    preferred_keys.extend(["id", "roleId", "role_id"])

    for field_name in preferred_keys:
        if field_name in row_keys:
            return field_name

    for field_name in row_keys:
        if field_name.lower().endswith("id"):
            return field_name
    return "id"


def _build_direct_delete_submit_payload(
    *,
    delete_entry: ApiCatalogEntry,
    pre_fill_params: dict[str, Any],
    target_name: str,
) -> dict[str, Any]:
    """在没有查询候选时，为删除确认页直接构造可提交 payload。"""

    payload = {
        field_name: value
        for field_name, value in dict(pre_fill_params).items()
        if value not in (None, "", [], {})
    }
    if payload:
        return payload

    name_field = _resolve_delete_name_payload_field(delete_entry)
    if target_name:
        return {name_field: target_name}
    return {}


def _resolve_delete_name_payload_field(delete_entry: ApiCatalogEntry) -> str:
    """为按名称删除场景推断最合适的名称入参字段。"""

    properties = delete_entry.param_schema.properties
    for field_name, schema in properties.items():
        if str(schema.get("type") or "string").lower() != "string":
            continue
        normalized_name = field_name.lower()
        title = str(schema.get("title") or schema.get("label") or "").strip()
        if normalized_name.endswith("name") or normalized_name in {"name", "rolename", "realname"}:
            return field_name
        if any(keyword in title for keyword in ("名称", "名字", "姓名")):
            return field_name

    haystack = f"{delete_entry.description} {delete_entry.path}".lower()
    if "role" in haystack or "角色" in haystack:
        return "roleName"
    return "name"


def _build_delete_lookup_submit_payload(
    *,
    delete_entry: ApiCatalogEntry,
    row: dict[str, Any],
    identifier_field: str,
) -> dict[str, Any]:
    """把查询命中的候选记录压成删除提交 payload。"""

    payload_key = _resolve_delete_lookup_payload_key(delete_entry, identifier_field=identifier_field)
    identifier_value = row.get(identifier_field)
    schema = delete_entry.param_schema.properties.get(payload_key, {})
    if str(schema.get("type") or "").lower() == "array":
        return {payload_key: [identifier_value]}
    return {payload_key: identifier_value}


def _resolve_delete_lookup_payload_key(delete_entry: ApiCatalogEntry, *, identifier_field: str) -> str:
    """为候选命中的删除动作选择主键入参。"""

    schema_properties = delete_entry.param_schema.properties
    preferred_keys = [field_name for field_name in schema_properties if field_name.lower() in {"id", "ids"}]
    preferred_keys.extend(
        [field_name for field_name in schema_properties if field_name.lower().endswith("id")]
    )
    if preferred_keys:
        return preferred_keys[0]
    return identifier_field or "id"


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
