"""`/api-query` 第四阶段 LangGraph 动态执行子图。

功能：
    把 Planner 产出的 `ApiQueryExecutionPlan.steps` 动态编译成 LangGraph 子图，替代
    原来写死在 `ApiDagExecutor` 里的 TopologicalSorter 调度逻辑，同时继续复用已有：

    - JSONPath 参数绑定
    - 空上游短路
    - 目录项必填参数校验
    - `ApiExecutor.call(...)` 的统一 HTTP 执行契约

设计约束：
    - `step_entries`、`user_token`、原始下游响应对象都只存在于运行时上下文，不进入 graph state
    - graph state 只保存聚合后的步骤记录与摘要，避免把敏感信息写进 LangGraph 快照
    - graph 编译/运行异常必须折叠成 synthetic report，不能把异常直接泄漏到 `/api-query` route
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from graphlib import TopologicalSorter
from time import perf_counter
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryPlanStep,
)
from app.services.api_catalog.dag_bindings import evaluate_binding_expression, is_dag_binding
from app.services.api_catalog.dag_runtime import DagExecutionReport, DagStepExecutionRecord
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.schema import ApiCatalogEntry
from app.services.workflows.graph_events import build_workflow_observability_fields, format_workflow_observability_log
from app.services.workflows.types import WorkflowRunContext, WorkflowTraceContext

logger = logging.getLogger(__name__)

_FINALIZE_NODE_NAME = "__execution_graph_finalize__"


class ApiQueryExecutionGraphState(TypedDict, total=False):
    """第四阶段内层执行图状态。

    功能：
        graph state 只保留执行图推进需要的轻量事实。重量级对象通过闭包运行时上下文传入，
        这样 LangGraph 的 state 快照里不会出现 `user_token`、目录实体全集或原始 HTTP 响应。
    """

    plan: ApiQueryExecutionPlan
    trace_id: str
    records_by_step_id: Annotated[dict[str, DagStepExecutionRecord], lambda left, right: _merge_record_maps(left, right)]
    execution_order: list[str]
    errors: list[str]
    aggregate_status: ApiQueryExecutionStatus | None


@dataclass(slots=True)
class ApiQueryExecutionBudget:
    """执行图预算配置。

    功能：
        统一收敛步骤级 timeout、整图 timeout 和最大步骤数，避免这些运行时护栏散落在
        节点逻辑里后难以审计或调参。
    """

    max_step_count: int
    step_timeout_seconds: float
    graph_timeout_seconds: float
    min_step_budget_seconds: float


@dataclass(slots=True)
class ApiQueryExecutionRuntime:
    """执行图请求期运行时上下文。

    入参业务含义：
        plan: 当前请求的 DAG 规划结果。
        step_entries: `step_id -> ApiCatalogEntry` 白名单，确保节点只执行校验后的接口。
        trace_id: 当前请求链路 Trace ID。
        interaction_id: 一次连续交互内的多请求聚合标识。
        conversation_id: 跨多轮查询共享的会话标识。
        user_token: 透传给业务系统或 runtime invoke 的认证头。
        user_id: 当前请求最终认定的用户主键，供 runtime invoke 落审计字段。
        step_timeout_seconds: 单节点外层保护超时。

    返回值约束：
        该对象只存在于一次 graph run 的闭包里，不会进入 LangGraph state。
    """

    plan: ApiQueryExecutionPlan
    step_entries: dict[str, ApiCatalogEntry]
    trace_id: str
    interaction_id: str | None
    conversation_id: str | None
    user_token: str | None
    user_id: str | None
    step_timeout_seconds: float


@dataclass(slots=True)
class ApiQueryExecutionGraphResult:
    """执行图对外输出的聚合摘要。"""

    report: DagExecutionReport
    aggregate_status: ApiQueryExecutionStatus
    error_summary: str | None
    anchor_step_id: str | None
    graph_failed: bool = False


class ApiQueryExecutionGraph:
    """第四阶段 LangGraph 动态执行子图。

    功能：
        根据 `plan.steps` 动态生成依赖图，并通过 LangGraph 执行。对外仍只暴露聚合后的
        `DagExecutionReport` 等价摘要，让第五阶段可以继续消费稳定报告结构。

    Edge Cases:
        - 规划步骤超限会在编译前被硬阻断，防止异常大图拖垮网关
        - 节点级 timeout 不会炸穿整图，而是折叠为该节点的标准化错误结果
        - graph compile / run 期异常会降级为 synthetic report，避免 route 直接抛 500
    """

    def __init__(
        self,
        api_executor: ApiExecutor,
        *,
        budget: ApiQueryExecutionBudget | None = None,
    ) -> None:
        self._api_executor = api_executor
        self._budget = budget or _build_execution_budget()

    async def run(
        self,
        plan: ApiQueryExecutionPlan,
        step_entries: dict[str, ApiCatalogEntry],
        *,
        user_token: str | None,
        user_id: str | None = None,
        trace_id: str,
        interaction_id: str | None = None,
        conversation_id: str | None = None,
    ) -> ApiQueryExecutionGraphResult:
        """执行一张动态 DAG。

        功能：
            该方法除了执行依赖图，还负责把 route 层已经确定好的 `user_token` / `user_id`
            绑定进一次 graph run 的闭包，确保每个节点看到的身份口径一致，避免某些节点
            继续从局部上下文二次猜测“当前是谁在发起查询”。

        Args:
            plan: 已通过第三阶段白名单与依赖校验的执行计划。
            step_entries: `step_id -> ApiCatalogEntry` 映射。
            user_token: 请求期认证头。
            user_id: 当前请求最终认定的用户主键。
            trace_id: 当前链路 Trace ID。

        Returns:
            聚合后的执行图摘要，兼容后续 `DagExecutionReport` 适配。

        Raises:
            该方法会吞掉 compile / run 异常并返回 synthetic report，因此正常情况下不向外抛错。

        Edge Cases:
            - graph compile 失败会直接降级成 synthetic report，而不会让 route 收到裸异常
            - 整图 timeout 会保留 plan 与 step 语义，确保第五阶段仍能构造结构化错误页面
            - LangGraph 最终 state 若缺失聚合字段，会回退本地汇总逻辑，避免执行摘要为空
        """

        runtime = ApiQueryExecutionRuntime(
            plan=plan,
            step_entries=step_entries,
            trace_id=trace_id,
            interaction_id=interaction_id,
            conversation_id=conversation_id,
            user_token=user_token,
            user_id=user_id,
            step_timeout_seconds=_resolve_step_timeout(self._budget),
        )
        build_started = perf_counter()
        try:
            # 每次请求按当前 planner 结果现编现用，避免跨请求复用错误的节点依赖关系。
            compiled_graph = self._build_graph(plan, runtime).compile()
        except Exception as exc:
            build_ms = (perf_counter() - build_started) * 1000
            logger.exception(
                "%s",
                format_workflow_observability_log(
                    "api_query execution graph compile failed",
                    observability_fields=_build_execution_observability_fields(
                        runtime,
                        phase="stage4",
                        node="execution_graph_compile",
                        execution_status="ERROR",
                    ),
                    payload={"plan_id": plan.plan_id, "step_count": len(plan.steps), "build_ms": round(build_ms, 2)},
                ),
            )
            return _build_synthetic_failure_result(
                plan=plan,
                step_entries=step_entries,
                trace_id=trace_id,
                error_code="EXECUTION_GRAPH_COMPILE_FAILED",
                message=f"执行图编译失败: {exc}",
            )

        build_ms = (perf_counter() - build_started) * 1000
        run_started = perf_counter()
        try:
            # graph state 只放轻量摘要，敏感运行时对象继续通过闭包透传。
            final_state = await asyncio.wait_for(
                compiled_graph.ainvoke(
                    {
                        "plan": plan,
                        "trace_id": trace_id,
                        "records_by_step_id": {},
                        "execution_order": [],
                        "errors": [],
                        "aggregate_status": None,
                    }
                ),
                timeout=_resolve_graph_timeout(self._budget, step_count=len(plan.steps)),
            )
        except asyncio.TimeoutError:
            run_ms = (perf_counter() - run_started) * 1000
            logger.warning(
                "%s",
                format_workflow_observability_log(
                    "api_query execution graph timeout",
                    observability_fields=_build_execution_observability_fields(
                        runtime,
                        phase="stage4",
                        node="execution_graph",
                        execution_status="ERROR",
                    ),
                    payload={
                        "plan_id": plan.plan_id,
                        "step_count": len(plan.steps),
                        "run_ms": round(run_ms, 2),
                        "timeout_seconds": _resolve_graph_timeout(self._budget, step_count=len(plan.steps)),
                    },
                ),
            )
            return _build_synthetic_failure_result(
                plan=plan,
                step_entries=step_entries,
                trace_id=trace_id,
                error_code="EXECUTION_GRAPH_TIMEOUT",
                message=f"执行图总超时（{_resolve_graph_timeout(self._budget, step_count=len(plan.steps))}s）",
                retryable=True,
            )
        except Exception as exc:
            run_ms = (perf_counter() - run_started) * 1000
            logger.exception(
                "%s",
                format_workflow_observability_log(
                    "api_query execution graph run failed",
                    observability_fields=_build_execution_observability_fields(
                        runtime,
                        phase="stage4",
                        node="execution_graph",
                        execution_status="ERROR",
                    ),
                    payload={"plan_id": plan.plan_id, "step_count": len(plan.steps), "run_ms": round(run_ms, 2)},
                ),
            )
            return _build_synthetic_failure_result(
                plan=plan,
                step_entries=step_entries,
                trace_id=trace_id,
                error_code="EXECUTION_GRAPH_RUN_FAILED",
                message=f"执行图运行失败: {exc}",
            )

        run_ms = (perf_counter() - run_started) * 1000
        # LangGraph 并发节点完成顺序不稳定，因此这里统一回退到 planner 顺序做最终收敛。
        records_by_step_id = dict(final_state.get("records_by_step_id") or {})
        execution_order = list(final_state.get("execution_order") or _build_execution_order(plan, records_by_step_id))
        aggregate_status = final_state.get("aggregate_status") or _summarize_execution_records(
            records_by_step_id,
            execution_order,
            plan=plan,
        )
        error_summary = _build_error_summary(records_by_step_id, execution_order)
        anchor_step_id = _select_anchor_step_id(records_by_step_id, execution_order)

        logger.info(
            "%s",
            format_workflow_observability_log(
                "api_query execution graph finished",
                observability_fields=_build_execution_observability_fields(
                    runtime,
                    phase="stage4",
                    node="execution_graph",
                    execution_status=aggregate_status.value,
                ),
                payload={
                    "plan_id": plan.plan_id,
                    "step_count": len(plan.steps),
                    "build_ms": round(build_ms, 2),
                    "run_ms": round(run_ms, 2),
                    "anchor_step_id": anchor_step_id,
                },
            ),
        )
        return ApiQueryExecutionGraphResult(
            report=DagExecutionReport(
                plan=plan,
                records_by_step_id=records_by_step_id,
                execution_order=execution_order,
            ),
            aggregate_status=aggregate_status,
            error_summary=error_summary,
            anchor_step_id=anchor_step_id,
        )

    def _build_graph(self, plan: ApiQueryExecutionPlan, runtime: ApiQueryExecutionRuntime) -> StateGraph:
        """动态编译当前请求的执行图。

        功能：
            这里不做跨请求缓存。第四阶段的 graph 形状由 LLM 规划结果决定，先优先保证
            正确性和隔离性，等拿到真实性能数据后再评估是否做签名缓存。

        Args:
            plan: 已通过第三阶段校验的执行计划。
            runtime: 当前请求的执行期闭包上下文。

        Returns:
            尚未 compile 的 `StateGraph`，由调用方决定何时编译与执行。

        Edge Cases:
            - 缺失 `step_entries` 或步骤数超限会在编译前硬失败，避免 LangGraph 才暴露晦涩错误
            - 叶子节点统一汇入 finalize 节点，确保多分支 DAG 也能稳定产出聚合摘要
        """

        _validate_execution_graph_inputs(plan, runtime.step_entries, self._budget)

        graph = StateGraph(ApiQueryExecutionGraphState)
        node_names: dict[str, str] = {}
        depended_step_ids: set[str] = set()

        for index, step in enumerate(plan.steps):
            node_name = f"execution_step__{index}"
            node_names[step.step_id] = node_name
            graph.add_node(node_name, self._build_step_node(step, runtime))
            if not step.depends_on:
                graph.add_edge(START, node_name)
            for upstream_step_id in step.depends_on:
                depended_step_ids.add(upstream_step_id)

        # 依赖边按 planner 的 step_id 建图，避免执行层再猜测业务依赖语义。
        for step in plan.steps:
            node_name = node_names[step.step_id]
            for upstream_step_id in step.depends_on:
                graph.add_edge(node_names[upstream_step_id], node_name)

        # 只把叶子节点接到 finalize，才能让多终点 DAG 在一个出口统一汇总状态。
        leaf_step_ids = [step.step_id for step in plan.steps if step.step_id not in depended_step_ids]
        graph.add_node(_FINALIZE_NODE_NAME, self._finalize_execution)
        for step_id in leaf_step_ids:
            graph.add_edge(node_names[step_id], _FINALIZE_NODE_NAME)
        graph.add_edge(_FINALIZE_NODE_NAME, END)
        return graph

    def _build_step_node(
        self,
        step: ApiQueryPlanStep,
        runtime: ApiQueryExecutionRuntime,
    ):
        """为单个规划步骤生成 LangGraph 节点函数。

        功能：
            每个步骤节点都统一遵循“先解析绑定，再决定是否可安全执行，最后调用业务接口”
            的顺序，避免不同 DAG 步骤出现各自一套缺参和短路语义。

        Args:
            step: 当前 planner 步骤定义。
            runtime: 当前请求的执行期闭包上下文。

        Returns:
            可直接注册到 LangGraph 的异步节点函数。

        Edge Cases:
            - 上游绑定为空时必须短路为 `SKIPPED`，不能继续调用业务接口
            - 必填参数缺失会折叠成标准化跳过结果，保持和旧执行器一致
            - 节点执行成功后仍会补写 planner 元数据，方便第五阶段审计与定位
        """

        async def _run_step(state: ApiQueryExecutionGraphState) -> dict[str, Any]:
            """执行单个 DAG 步骤并产出标准化记录。

            功能：
                节点函数既承担实际调用，也负责把“为什么没调下游”折叠成结构化结果，
                这样第五阶段无需区分是业务失败、超时还是前置短路。

            Args:
                state: 当前 LangGraph 轻量状态，只包含上游记录与计划摘要。

            Returns:
                只包含当前步骤记录增量的 state patch。

            Edge Cases:
                - 空绑定和缺参都走 `SKIPPED`，避免 UI 把这类安全短路误判成系统错误
                - 下游执行即使成功，也会把 resolved_params 写回记录，供响应层回溯
            """
            upstream_records = state.get("records_by_step_id") or {}
            step_data_by_id = {
                step_id: record.execution_result.data
                for step_id, record in upstream_records.items()
            }
            entry = runtime.step_entries[step.step_id]
            resolved_params, empty_bindings = _resolve_step_params(step.params, step_data_by_id)
            resolved_params = _coerce_single_item_array_params(
                params=resolved_params,
                entry=entry,
            )
            required_empty_bindings = _collect_required_empty_bindings(
                step=step,
                entry=entry,
                empty_bindings=empty_bindings,
            )
            logger.info(
                "%s",
                format_workflow_observability_log(
                    "api_query execution step started",
                    observability_fields=_build_execution_observability_fields(
                        runtime,
                        phase="stage4",
                        node=step.step_id,
                        execution_status=None,
                    ),
                    payload={
                        "api_id": step.api_id or entry.id,
                        "api_path": step.api_path or entry.path,
                        "depends_on": list(step.depends_on),
                        "param_keys": sorted(resolved_params.keys()),
                    },
                ),
            )

            # 1. 先做空上游短路，避免把无意义参数继续打到业务系统。
            if required_empty_bindings:
                logger.info(
                    "%s",
                    format_workflow_observability_log(
                        "api_query execution step failed",
                        observability_fields=_build_execution_observability_fields(
                            runtime,
                            phase="stage4",
                            node=step.step_id,
                            execution_status=ApiQueryExecutionStatus.ERROR.value,
                        ),
                        payload={
                            "reason": "required_binding_empty_upstream",
                            "depends_on": list(step.depends_on),
                            "required_empty_bindings": required_empty_bindings,
                        },
                    ),
                )
                execution_result = _build_required_empty_upstream_error_result(
                    trace_id=runtime.trace_id,
                    step=step,
                    required_empty_bindings=required_empty_bindings,
                )
                return {
                    "records_by_step_id": {
                        step.step_id: DagStepExecutionRecord(
                            step=step,
                            entry=entry,
                            resolved_params=resolved_params,
                            execution_result=execution_result,
                        )
                    }
                }

            if empty_bindings:
                logger.info(
                    "%s",
                    format_workflow_observability_log(
                        "api_query execution step skipped",
                        observability_fields=_build_execution_observability_fields(
                            runtime,
                            phase="stage4",
                            node=step.step_id,
                            execution_status=ApiQueryExecutionStatus.SKIPPED.value,
                        ),
                        payload={
                            "reason": "skipped_due_to_empty_upstream",
                            "depends_on": list(step.depends_on),
                            "empty_bindings": empty_bindings,
                        },
                    ),
                )
                execution_result = _build_empty_upstream_skip_result(
                    trace_id=runtime.trace_id,
                    step=step,
                    empty_bindings=empty_bindings,
                )
                return {
                    "records_by_step_id": {
                        step.step_id: DagStepExecutionRecord(
                            step=step,
                            entry=entry,
                            resolved_params=resolved_params,
                            execution_result=execution_result,
                        )
                    }
                }

            # 缺参短路发生在真正发起 HTTP 调用前，避免把“参数不成立”污染成下游错误。
            missing_required_params = _find_missing_required_params(entry, resolved_params)
            wait_select_result = _build_wait_select_required_result(
                trace_id=runtime.trace_id,
                step=step,
                depends_on_records=upstream_records,
            )
            if wait_select_result is not None:
                logger.info(
                    "%s",
                    format_workflow_observability_log(
                        "api_query execution step skipped",
                        observability_fields=_build_execution_observability_fields(
                            runtime,
                            phase="stage4",
                            node=step.step_id,
                            execution_status=ApiQueryExecutionStatus.SKIPPED.value,
                        ),
                        payload={"reason": "wait_select_required"},
                    ),
                )
                return {
                    "records_by_step_id": {
                        step.step_id: DagStepExecutionRecord(
                            step=step,
                            entry=entry,
                            resolved_params=resolved_params,
                            execution_result=wait_select_result,
                        )
                    }
                }
            if missing_required_params:
                logger.info(
                    "%s",
                    format_workflow_observability_log(
                        "api_query execution step skipped",
                        observability_fields=_build_execution_observability_fields(
                            runtime,
                            phase="stage4",
                            node=step.step_id,
                            execution_status=ApiQueryExecutionStatus.SKIPPED.value,
                        ),
                        payload={"reason": "missing_required_params", "missing_required_params": missing_required_params},
                    ),
                )
                execution_result = _build_missing_param_skip_result(
                    trace_id=runtime.trace_id,
                    step=step,
                    missing_required_params=missing_required_params,
                )
                return {
                    "records_by_step_id": {
                        step.step_id: DagStepExecutionRecord(
                            step=step,
                            entry=entry,
                            resolved_params=resolved_params,
                            execution_result=execution_result,
                        )
                    }
                }

            execution_result = await _call_entry_with_timeout(
                api_executor=self._api_executor,
                entry=entry,
                resolved_params=resolved_params,
                user_token=runtime.user_token,
                user_id=runtime.user_id,
                trace_id=runtime.trace_id,
                step=step,
                step_timeout_seconds=runtime.step_timeout_seconds,
                interaction_id=runtime.interaction_id,
                conversation_id=runtime.conversation_id,
            )
            logger.info(
                "%s",
                format_workflow_observability_log(
                    "api_query execution step finished",
                    observability_fields=_build_execution_observability_fields(
                        runtime,
                        phase="stage4",
                        node=step.step_id,
                        execution_status=execution_result.status.value,
                    ),
                    payload={
                        "api_id": step.api_id or entry.id,
                        "api_path": step.api_path or entry.path,
                        "status": execution_result.status.value,
                        "error_code": execution_result.error_code,
                    },
                ),
            )
            execution_result.meta.setdefault("planner_step_id", step.step_id)
            execution_result.meta.setdefault("depends_on", list(step.depends_on))
            execution_result.meta.setdefault("resolved_params", resolved_params)
            return {
                "records_by_step_id": {
                    step.step_id: DagStepExecutionRecord(
                        step=step,
                        entry=entry,
                        resolved_params=resolved_params,
                        execution_result=execution_result,
                    )
                }
            }

        return _run_step

    async def _finalize_execution(self, state: ApiQueryExecutionGraphState) -> dict[str, Any]:
        """在所有叶子步骤结束后汇总执行图摘要。"""

        plan = state["plan"]
        records_by_step_id = dict(state.get("records_by_step_id") or {})
        execution_order = _build_execution_order(plan, records_by_step_id)
        return {
            "execution_order": execution_order,
            "errors": [
                record.execution_result.error
                for step_id in execution_order
                if (record := records_by_step_id.get(step_id)) and record.execution_result.error
            ],
            "aggregate_status": _summarize_execution_records(records_by_step_id, execution_order, plan=plan),
        }


def _build_execution_budget() -> ApiQueryExecutionBudget:
    """从配置解析执行预算。

    功能：
        预算解析独立成纯函数，便于测试中按需 monkeypatch 配置值，而不是在构造函数里
        到处写死读取逻辑。
    """

    return ApiQueryExecutionBudget(
        max_step_count=settings.api_query_execution_max_step_count,
        step_timeout_seconds=settings.api_query_execution_step_timeout_seconds,
        graph_timeout_seconds=settings.api_query_execution_graph_timeout_seconds,
        min_step_budget_seconds=settings.api_query_execution_min_step_budget_seconds,
    )


def _build_execution_observability_fields(
    runtime: ApiQueryExecutionRuntime,
    *,
    phase: str,
    node: str,
    execution_status: str | None = None,
) -> dict[str, Any]:
    """构造内层执行图日志使用的统一观测字段。"""

    return build_workflow_observability_fields(
        run_context=WorkflowRunContext(
            workflow_name="api_query_execution_graph",
            trace_context=WorkflowTraceContext(
                trace_id=runtime.trace_id,
                interaction_id=runtime.interaction_id,
                conversation_id=runtime.conversation_id,
            ),
            phase=phase,
        ),
        node=node,
        execution_status=execution_status,
    )


def _resolve_step_timeout(budget: ApiQueryExecutionBudget) -> float:
    """解析单节点有效超时。

    功能：
        单节点预算不能比系统配置的最小预算更小，否则 Planner 多走一步就可能把 timeout
        调到几乎不可能成功的值，最终把偶发抖动误判成系统故障。
    """

    return max(budget.step_timeout_seconds, budget.min_step_budget_seconds)


def _resolve_graph_timeout(budget: ApiQueryExecutionBudget, *, step_count: int) -> float:
    """解析整图有效超时。

    功能：
        graph timeout 需要同时满足两个约束：

        1. 尊重显式配置的整图 SLA
        2. 至少给每个步骤一个最小预算，避免 `step_count` 稍大时总预算天然不成立
    """

    return max(
        budget.graph_timeout_seconds,
        max(step_count, 1) * budget.min_step_budget_seconds,
        _resolve_step_timeout(budget),
    )


def _validate_execution_graph_inputs(
    plan: ApiQueryExecutionPlan,
    step_entries: dict[str, ApiCatalogEntry],
    budget: ApiQueryExecutionBudget,
) -> None:
    """在编译前做一层运行时护栏。

    功能：
        Planner 理论上已经完成结构校验，但执行层仍然需要兜底。原因不是不信任 Planner，
        而是执行层要对 LangGraph 编译成本和目录实体完整性负责。
    """

    if len(plan.steps) > budget.max_step_count:
        raise RuntimeError(
            f"执行图步骤数超出上限: {len(plan.steps)} > {budget.max_step_count}"
        )

    missing_step_entries = [
        step.step_id
        for step in plan.steps
        if step.step_id not in step_entries
    ]
    if missing_step_entries:
        raise RuntimeError(f"缺少步骤目录实体映射: {', '.join(missing_step_entries)}")


async def _call_entry_with_timeout(
    *,
    api_executor: ApiExecutor,
    entry: ApiCatalogEntry,
    resolved_params: dict[str, Any],
    user_token: str | None,
    user_id: str | None,
    trace_id: str,
    step: ApiQueryPlanStep,
    step_timeout_seconds: float,
    interaction_id: str | None = None,
    conversation_id: str | None = None,
) -> ApiQueryExecutionResult:
    """执行单个业务接口并加上节点级超时保护。

    功能：
        runtime invoke 现在需要把请求级 `user_id` 一并写入请求壳；这里把用户主键和 token
        一起透传给执行器，是为了让“谁发起了这次查询”和“凭什么能调下游”继续在同一个
        节点执行上下文里闭环，而不是在 DAG 节点里再额外拼装一次身份信息。

    Args:
        api_executor: 统一业务接口执行器。
        entry: 当前步骤命中的目录项。
        resolved_params: 已完成上游绑定解析的最终参数。
        user_token: 透传给下游的认证头。
        user_id: 当前可信用户主键。
        trace_id: 当前请求 Trace ID。
        step: planner 里的当前步骤定义。
        step_timeout_seconds: 节点级超时阈值。
        interaction_id: 连续交互聚合 ID。
        conversation_id: 多轮会话 ID。

    Returns:
        标准化后的 `ApiQueryExecutionResult`；超时场景也返回结构化错误对象。

    Edge Cases:
        - 节点超时不会炸穿整图，而是折叠成单步骤 `ERROR`
        - 超时结果仍保留 `depends_on` 与 `resolved_params`，便于复盘到底卡在什么输入上
    """

    try:
        return await asyncio.wait_for(
            api_executor.call(
                entry,
                resolved_params,
                user_token=user_token,
                user_id=user_id,
                trace_id=trace_id,
            ),
            timeout=step_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "%s",
            format_workflow_observability_log(
                "api_query execution step timeout",
                observability_fields=build_workflow_observability_fields(
                    run_context=WorkflowRunContext(
                        workflow_name="api_query_execution_graph",
                        trace_context=WorkflowTraceContext(
                            trace_id=trace_id,
                            interaction_id=interaction_id,
                            conversation_id=conversation_id,
                        ),
                        phase="stage4",
                    ),
                    node=step.step_id,
                    execution_status=ApiQueryExecutionStatus.ERROR.value,
                ),
                payload={
                    "api_id": step.api_id or entry.id,
                    "timeout_seconds": step_timeout_seconds,
                },
            ),
        )
        return ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.ERROR,
            data=None,
            total=0,
            error=f"步骤执行超时（{step_timeout_seconds}s）",
            error_code="EXECUTION_STEP_TIMEOUT",
            retryable=True,
            trace_id=trace_id,
            meta={
                "planner_step_id": step.step_id,
                "depends_on": list(step.depends_on),
                "resolved_params": resolved_params,
            },
        )


def _build_synthetic_failure_result(
    *,
    plan: ApiQueryExecutionPlan,
    step_entries: dict[str, ApiCatalogEntry],
    trace_id: str,
    error_code: str,
    message: str,
    retryable: bool = False,
) -> ApiQueryExecutionGraphResult:
    """把 compile / run 失败折叠成 synthetic report。

    功能：
        `/api-query` 对外要保持“始终返回结构化执行报告”的契约，即使底层状态图本身失效，
        第五阶段也必须能拿到一个最小可消费的错误报告。

    Args:
        plan: 当前执行计划。
        step_entries: 已校验的步骤目录映射。
        trace_id: 当前请求 Trace ID。
        error_code: 结构化错误码。
        message: 对外可读的失败摘要。
        retryable: 当前错误是否允许前端提示用户重试。

    Returns:
        带 synthetic report 的执行图结果对象。

    Edge Cases:
        - 若目录映射异常缺失，仍会构造占位 entry，保证响应结构不塌陷
        - synthetic report 固定锚定首个步骤，确保第五阶段至少能拿到稳定 anchor
    """

    fallback_step = plan.steps[0]
    entry = step_entries.get(fallback_step.step_id) or _build_synthetic_entry(fallback_step)
    synthetic_result = ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.ERROR,
        data=None,
        total=0,
        error=message,
        error_code=error_code,
        retryable=retryable,
        trace_id=trace_id,
        meta={
            "planner_step_id": fallback_step.step_id,
            "depends_on": list(fallback_step.depends_on),
            "graph_failed": True,
        },
    )
    report = DagExecutionReport(
        plan=plan,
        records_by_step_id={
            fallback_step.step_id: DagStepExecutionRecord(
                step=fallback_step,
                entry=entry,
                resolved_params=dict(fallback_step.params),
                execution_result=synthetic_result,
            )
        },
        execution_order=[fallback_step.step_id],
    )
    return ApiQueryExecutionGraphResult(
        report=report,
        aggregate_status=ApiQueryExecutionStatus.ERROR,
        error_summary=message,
        anchor_step_id=fallback_step.step_id,
        graph_failed=True,
    )


def _build_synthetic_entry(step: ApiQueryPlanStep) -> ApiCatalogEntry:
    """为 synthetic report 构造占位目录项。

    功能：
        正常情况下第三阶段总能给出 `step_entries`。这里保留占位构造，只是为了保证
        图编译前置校验失效时，第五阶段仍能拿到 domain/path/method 等基础字段。
    """

    return ApiCatalogEntry(
        id=step.api_id or step.step_id,
        name="synthetic_failure",
        description="执行图 synthetic failure",
        domain="generic",
        operation_safety="query",
        method="GET",
        path=step.api_path,
    )


def _merge_record_maps(
    left: dict[str, DagStepExecutionRecord],
    right: dict[str, DagStepExecutionRecord],
) -> dict[str, DagStepExecutionRecord]:
    """合并并发节点写回的步骤记录。"""

    merged = dict(left)
    merged.update(right)
    return merged


def _resolve_step_params(
    params: dict[str, Any],
    step_data_by_id: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """解析步骤参数中的 JSONPath 绑定。"""

    resolved_params: dict[str, Any] = {}
    empty_bindings: list[str] = []

    for key, value in params.items():
        resolved_value, nested_empty_bindings = _resolve_param_value(value, step_data_by_id)
        resolved_params[key] = resolved_value
        empty_bindings.extend(nested_empty_bindings)

    return resolved_params, list(dict.fromkeys(empty_bindings))


def _resolve_param_value(
    value: Any,
    step_data_by_id: dict[str, Any],
) -> tuple[Any, list[str]]:
    """递归解析参数值中的绑定表达式。

    功能：
        planner 参数既可能是标量，也可能是深层对象/数组。这里统一做递归解析，确保
        所有 `$step_xxx...` 绑定都在执行前被还原成最终值，并顺手收集“哪些绑定解析为空”，
        供上层节点决定是否短路。

    Args:
        value: 待解析的参数片段。
        step_data_by_id: `step_id -> execution_result.data` 的上游数据视图。

    Returns:
        二元组 `(resolved_value, empty_bindings)`，后者用于上层短路判定。

    Edge Cases:
        - 绑定表达式即使解析为空，也要保留原始空值结果，避免下游参数形状失真
        - 嵌套 dict/list 会继续递归解析，防止局部绑定遗漏
    """

    if is_dag_binding(value):
        resolved_value = evaluate_binding_expression(value, step_data_by_id)
        if _is_empty_binding_value(resolved_value):
            return resolved_value, [value]
        return resolved_value, []

    if isinstance(value, dict):
        resolved_dict: dict[str, Any] = {}
        empty_bindings: list[str] = []
        for key, nested_value in value.items():
            resolved_item, nested_empty_bindings = _resolve_param_value(nested_value, step_data_by_id)
            resolved_dict[key] = resolved_item
            empty_bindings.extend(nested_empty_bindings)
        return resolved_dict, empty_bindings

    if isinstance(value, list):
        resolved_list: list[Any] = []
        empty_bindings: list[str] = []
        for item in value:
            resolved_item, nested_empty_bindings = _resolve_param_value(item, step_data_by_id)
            resolved_list.append(resolved_item)
            empty_bindings.extend(nested_empty_bindings)
        return resolved_list, empty_bindings

    return value, []


def _find_missing_required_params(entry: ApiCatalogEntry, params: dict[str, Any]) -> list[str]:
    """检查步骤执行前是否缺失接口声明的必填参数。"""

    missing_fields: list[str] = []
    for field_name in entry.param_schema.required:
        value = params.get(field_name)
        if value in (None, "", [], {}):
            missing_fields.append(field_name)
    return missing_fields


def _coerce_single_item_array_params(
    *,
    params: dict[str, Any],
    entry: ApiCatalogEntry,
) -> dict[str, Any]:
    """将单元素数组参数按 schema 降级为标量。

    功能：
        predecessor 绑定在 `select_mode=all/user_select` 下会产出数组；
        当目标字段 schema 明确声明为标量类型时，执行层做一次最小兼容：
        `[value] -> value`。这样不改 planner 语义，也能兼容下游 string 入参接口。

    约束：
        - 仅在数组长度为 1 且目标字段非 array/object 时降级
        - 字段 schema 不存在或本身为 array/object 时保持原样
    """

    properties = entry.param_schema.properties
    if not isinstance(properties, dict) or not properties:
        return params

    normalized: dict[str, Any] = dict(params)
    for field_name, value in params.items():
        if not isinstance(value, list) or len(value) != 1:
            continue
        schema = properties.get(field_name)
        if not isinstance(schema, dict):
            continue
        field_type = str(schema.get("type") or "").strip().lower()
        if field_type in {"array", "object"}:
            continue
        normalized[field_name] = value[0]
    return normalized


def _build_empty_upstream_skip_result(
    *,
    trace_id: str,
    step: ApiQueryPlanStep,
    empty_bindings: list[str],
) -> ApiQueryExecutionResult:
    """为“上游绑定为空”的场景构造短路结果。"""

    return ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.SKIPPED,
        data=[],
        total=0,
        error="上游步骤未返回可继续传递的数据，当前步骤已被安全跳过。",
        error_code="EMPTY_UPSTREAM_BINDING",
        trace_id=trace_id,
        skipped_reason="skipped_due_to_empty_upstream",
        meta={
            "planner_step_id": step.step_id,
            "depends_on": list(step.depends_on),
            "empty_bindings": empty_bindings,
        },
    )


def _build_required_empty_upstream_error_result(
    *,
    trace_id: str,
    step: ApiQueryPlanStep,
    required_empty_bindings: list[str],
) -> ApiQueryExecutionResult:
    """为“必填参数绑定为空”场景构造错误结果。"""

    return ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.ERROR,
        data=[],
        total=0,
        error="上游步骤未返回必填参数所需数据，当前步骤执行失败。",
        error_code="EMPTY_UPSTREAM_BINDING_REQUIRED",
        trace_id=trace_id,
        meta={
            "planner_step_id": step.step_id,
            "depends_on": list(step.depends_on),
            "required_empty_bindings": required_empty_bindings,
        },
    )


def _build_missing_param_skip_result(
    *,
    trace_id: str,
    step: ApiQueryPlanStep,
    missing_required_params: list[str],
) -> ApiQueryExecutionResult:
    """为步骤级缺参场景构造跳过结果。"""

    return ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.SKIPPED,
        data=[],
        total=0,
        error=f"缺少必要参数：{', '.join(missing_required_params)}",
        error_code="MISSING_REQUIRED_PARAMS",
        trace_id=trace_id,
        skipped_reason="missing_required_params",
        meta={
            "planner_step_id": step.step_id,
            "depends_on": list(step.depends_on),
            "missing_required_params": missing_required_params,
        },
    )


def _build_wait_select_required_result(
    *,
    trace_id: str,
    step: ApiQueryPlanStep,
    depends_on_records: dict[str, DagStepExecutionRecord],
) -> ApiQueryExecutionResult | None:
    """当存在数组上游绑定且缺少用户选择时，返回等待选择态。"""
    from app.services.api_catalog.dag_bindings import parse_binding_expression

    options_by_binding: dict[str, list[Any]] = {}
    option_rows_by_binding: dict[str, list[dict[str, Any]]] = {}
    for param_name, raw_value in step.params.items():
        if not is_dag_binding(raw_value):
            continue
        expression = str(raw_value)
        if "[*]" not in expression:
            continue
        try:
            parsed = parse_binding_expression(expression)
        except Exception:
            continue
        upstream_record = depends_on_records.get(parsed.step_id)
        if upstream_record is None:
            continue
        extracted = evaluate_binding_expression(expression, {parsed.step_id: upstream_record.execution_result.data})
        if not isinstance(extracted, list):
            continue
        normalized_options = [item for item in extracted if item not in (None, "")]
        if len(normalized_options) <= 1:
            continue
        source_path = _extract_binding_source_path(expression)
        binding_key = f"{upstream_record.entry.id}:{param_name}:{source_path}"
        options_by_binding[binding_key] = normalized_options

        upstream_data = upstream_record.execution_result.data
        if isinstance(upstream_data, list):
            upstream_rows = [row for row in upstream_data if isinstance(row, dict)]
        elif isinstance(upstream_data, dict):
            upstream_rows = [upstream_data]
        else:
            upstream_rows = []
        if upstream_rows:
            option_rows_by_binding[binding_key] = [dict(row) for row in upstream_rows]

    if not options_by_binding:
        return None

    return ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.SKIPPED,
        data=[],
        total=0,
        error="命中多个候选值，请先选择后继续。",
        error_code="WAIT_SELECT_REQUIRED",
        trace_id=trace_id,
        skipped_reason="wait_select_required",
        meta={
            "planner_step_id": step.step_id,
            "depends_on": list(step.depends_on),
            "pause_type": "WAIT_SELECT",
            "selection_mode": "single",
            "options_by_binding": options_by_binding,
            "option_rows_by_binding": option_rows_by_binding,
        },
    )


def _extract_binding_source_path(expression: str) -> str:
    """从受限绑定表达式中提取 source_path。"""
    marker = ".data]"
    if marker not in expression:
        return ""
    source = expression.split(marker, 1)[1]
    source = source.replace("[*]", "")
    source = source.lstrip(".")
    return source


def _collect_required_empty_bindings(
    *,
    step: ApiQueryPlanStep,
    entry: ApiCatalogEntry,
    empty_bindings: list[str],
) -> list[str]:
    """筛选落在接口必填参数上的空绑定。"""
    if not empty_bindings:
        return []
    required_params = set(entry.param_schema.required or [])
    if not required_params:
        return []
    required_binding_values = {
        str(value)
        for param_name, value in step.params.items()
        if param_name in required_params and is_dag_binding(value)
    }
    if not required_binding_values:
        return []
    return [expression for expression in empty_bindings if expression in required_binding_values]


def _is_empty_binding_value(value: Any) -> bool:
    """判断绑定结果是否为空。"""

    return value in (None, [], {})


def _build_execution_order(
    plan: ApiQueryExecutionPlan,
    records_by_step_id: dict[str, DagStepExecutionRecord],
) -> list[str]:
    """按旧执行器语义生成稳定的执行顺序。

    功能：
        LangGraph 允许同层节点并发执行，节点完成先后不稳定。第五阶段选 anchor 和构造
        `context_pool` 时依赖一份稳定顺序，因此这里继续按 planner 步骤顺序和拓扑层级
        生成确定性的 `execution_order`。
    """

    graph = {step.step_id: set(step.depends_on) for step in plan.steps}
    sorter = TopologicalSorter(graph)
    sorter.prepare()

    execution_order: list[str] = []
    while sorter.is_active():
        ready_step_ids = list(sorter.get_ready())
        for step_id in ready_step_ids:
            if step_id in records_by_step_id:
                execution_order.append(step_id)
            sorter.done(step_id)
    return execution_order


def _summarize_execution_records(
    records_by_step_id: dict[str, DagStepExecutionRecord],
    execution_order: list[str],
    *,
    plan: ApiQueryExecutionPlan | None = None,
) -> ApiQueryExecutionStatus:
    """把执行图结果折叠成对外主状态。"""

    statuses = [
        records_by_step_id[step_id].execution_result.status
        for step_id in execution_order
        if step_id in records_by_step_id
    ]
    if not statuses:
        return ApiQueryExecutionStatus.SKIPPED

    has_success = any(status == ApiQueryExecutionStatus.SUCCESS for status in statuses)
    has_error = any(status == ApiQueryExecutionStatus.ERROR for status in statuses)
    has_skipped = any(status == ApiQueryExecutionStatus.SKIPPED for status in statuses)

    if plan is not None and _has_wait_select_required(records_by_step_id, execution_order, plan):
        return ApiQueryExecutionStatus.SKIPPED
    if has_success and (has_error or has_skipped):
        return ApiQueryExecutionStatus.PARTIAL_SUCCESS
    if has_success:
        return ApiQueryExecutionStatus.SUCCESS
    if has_error:
        return ApiQueryExecutionStatus.ERROR
    if any(status == ApiQueryExecutionStatus.EMPTY for status in statuses):
        return ApiQueryExecutionStatus.EMPTY
    return ApiQueryExecutionStatus.SKIPPED


def _has_wait_select_required(
    records_by_step_id: dict[str, DagStepExecutionRecord],
    execution_order: list[str],
    plan: ApiQueryExecutionPlan,
) -> bool:
    """判断是否命中了 user_select 的等待态。"""
    step_map = {step.step_id: step for step in plan.steps}
    for step_id in execution_order:
        record = records_by_step_id.get(step_id)
        if record is None:
            continue
        result = record.execution_result
        if result.status != ApiQueryExecutionStatus.SKIPPED:
            continue
        if result.error_code != "WAIT_SELECT_REQUIRED":
            continue
        depends_on = step_map.get(step_id).depends_on if step_map.get(step_id) else []
        if any(dep in records_by_step_id for dep in depends_on):
            return True
    return False


def _build_error_summary(
    records_by_step_id: dict[str, DagStepExecutionRecord],
    execution_order: list[str],
) -> str | None:
    """汇总执行图中的第一批错误信息。"""

    errors = [
        record.execution_result.error
        for step_id in execution_order
        if (record := records_by_step_id.get(step_id)) and record.execution_result.error
    ]
    if not errors:
        return None
    return "；".join(dict.fromkeys(errors))


def _select_anchor_step_id(
    records_by_step_id: dict[str, DagStepExecutionRecord],
    execution_order: list[str],
) -> str | None:
    """选择对外响应锚点步骤。"""

    for candidate_status in (
        ApiQueryExecutionStatus.SUCCESS,
        ApiQueryExecutionStatus.EMPTY,
        ApiQueryExecutionStatus.SKIPPED,
        ApiQueryExecutionStatus.ERROR,
    ):
        for step_id in reversed(execution_order):
            record = records_by_step_id.get(step_id)
            if record and record.execution_result.status == candidate_status:
                return step_id
    return execution_order[-1] if execution_order else None
