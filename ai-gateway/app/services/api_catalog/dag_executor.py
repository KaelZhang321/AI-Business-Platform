"""第三阶段 DAG 执行总线。

功能：
    负责按拓扑顺序执行 Planner 生成的只读 DAG，并在运行时处理：

    - JSONPath 参数绑定
    - 空上游短路
    - 多步骤并发执行
    - 步骤级执行结果聚合
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from graphlib import TopologicalSorter
from typing import Any

from app.models.schemas import ApiQueryExecutionResult, ApiQueryExecutionStatus, ApiQueryExecutionPlan, ApiQueryPlanStep
from app.services.api_catalog.dag_bindings import evaluate_binding_expression, is_dag_binding
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.schema import ApiCatalogEntry

logger = logging.getLogger(__name__)


@dataclass
class DagStepExecutionRecord:
    """第三阶段单个步骤的执行记录。

    Args:
        step: 当前执行的 Planner 步骤定义。
        entry: 与步骤绑定的注册表接口实体。
        resolved_params: 实际发给执行器的参数，已经完成 JSONPath 解析。
        execution_result: 统一执行结果状态机对象。

    Returns:
        该对象仅在网关内部流转，用于构造 `context_pool` 和响应摘要。
    """

    step: ApiQueryPlanStep
    entry: ApiCatalogEntry
    resolved_params: dict[str, Any]
    execution_result: ApiQueryExecutionResult


@dataclass
class DagExecutionReport:
    """第三阶段 DAG 的完整执行报告。"""

    plan: ApiQueryExecutionPlan
    records_by_step_id: dict[str, DagStepExecutionRecord]
    execution_order: list[str]


class ApiDagExecutor:
    """按拓扑层执行第三阶段只读 DAG。

    功能：
        让无依赖步骤并发执行，同时保证带依赖的步骤只有在前置层完成后才会启动。

    Edge Cases:
        - JSONPath 绑定为空时，会把当前步骤标记为 `skipped_due_to_empty_upstream`
        - 缺少必填参数时也会主动跳过，避免把宽查询风险下沉给业务系统
    """

    def __init__(self, api_executor: ApiExecutor) -> None:
        self._api_executor = api_executor

    async def execute_plan(
        self,
        plan: ApiQueryExecutionPlan,
        step_entries: dict[str, ApiCatalogEntry],
        *,
        user_token: str | None,
        trace_id: str,
    ) -> DagExecutionReport:
        """执行只读 DAG。

        Args:
            plan: 已完成白名单和依赖校验的 DAG。
            step_entries: `step_id -> ApiCatalogEntry` 映射。
            user_token: 透传给 business-server 的用户 Token。
            trace_id: 当前请求链路 Trace ID。

        Returns:
            `DagExecutionReport`，包含步骤记录和执行顺序。

        Edge Cases:
            - 单层内步骤会并发执行；层与层之间仍按依赖顺序推进
            - 任一步骤失败不会中断整张图，只有依赖它且绑定为空的步骤会被短路
        """
        graph = {step.step_id: set(step.depends_on) for step in plan.steps}
        plan_steps_by_id = {step.step_id: step for step in plan.steps}
        sorter = TopologicalSorter(graph)
        sorter.prepare()

        records_by_step_id: dict[str, DagStepExecutionRecord] = {}
        execution_order: list[str] = []

        while sorter.is_active():
            ready_step_ids = list(sorter.get_ready())
            layer_records = await asyncio.gather(
                *(
                    self._execute_single_step(
                        plan_steps_by_id[step_id],
                        step_entries[step_id],
                        records_by_step_id,
                        user_token=user_token,
                        trace_id=trace_id,
                    )
                    for step_id in ready_step_ids
                )
            )

            for record in layer_records:
                records_by_step_id[record.step.step_id] = record
                execution_order.append(record.step.step_id)
                sorter.done(record.step.step_id)

        return DagExecutionReport(
            plan=plan,
            records_by_step_id=records_by_step_id,
            execution_order=execution_order,
        )

    async def _execute_single_step(
        self,
        step: ApiQueryPlanStep,
        entry: ApiCatalogEntry,
        upstream_records: dict[str, DagStepExecutionRecord],
        *,
        user_token: str | None,
        trace_id: str,
    ) -> DagStepExecutionRecord:
        """执行单个 DAG 步骤。"""
        step_data_by_id = {step_id: record.execution_result.data for step_id, record in upstream_records.items()}
        resolved_params, empty_bindings = _resolve_step_params(step.params, step_data_by_id)

        if empty_bindings:
            logger.info(
                "stage3 dag step skipped trace_id=%s step_id=%s reason=%s depends_on=%s empty_bindings=%s",
                trace_id,
                step.step_id,
                "skipped_due_to_empty_upstream",
                list(step.depends_on),
                empty_bindings,
            )
            execution_result = _build_empty_upstream_skip_result(
                trace_id=trace_id,
                step=step,
                empty_bindings=empty_bindings,
            )
            return DagStepExecutionRecord(
                step=step,
                entry=entry,
                resolved_params=resolved_params,
                execution_result=execution_result,
            )

        missing_required_params = _find_missing_required_params(entry, resolved_params)
        if missing_required_params:
            logger.info(
                "stage3 dag step skipped trace_id=%s step_id=%s reason=%s missing_required_params=%s",
                trace_id,
                step.step_id,
                "missing_required_params",
                missing_required_params,
            )
            execution_result = _build_missing_param_skip_result(
                trace_id=trace_id,
                step=step,
                missing_required_params=missing_required_params,
            )
            return DagStepExecutionRecord(
                step=step,
                entry=entry,
                resolved_params=resolved_params,
                execution_result=execution_result,
            )

        execution_result = await self._api_executor.call(
            entry,
            resolved_params,
            user_token=user_token,
            trace_id=trace_id,
        )
        execution_result.meta.setdefault("planner_step_id", step.step_id)
        execution_result.meta.setdefault("depends_on", list(step.depends_on))
        execution_result.meta.setdefault("resolved_params", resolved_params)
        return DagStepExecutionRecord(
            step=step,
            entry=entry,
            resolved_params=resolved_params,
            execution_result=execution_result,
        )


def _resolve_step_params(
    params: dict[str, Any],
    step_data_by_id: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """解析步骤参数中的 JSONPath 绑定。

    功能：
        执行阶段不再相信 Planner 输出的参数已经是可直接执行的最终态，而是逐个
        解析绑定表达式，并把“空上游”显式提取成短路信号。
    """
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
    """递归解析参数值中的绑定表达式。"""
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


def _is_empty_binding_value(value: Any) -> bool:
    """判断绑定结果是否为空。

    设计说明：
        第三阶段这里采用偏保守的定义：`None / [] / {}` 一律视为空上游。
        这样做的目的是宁可少查，也不把“无意义参数”继续打给底层核心系统。
    """
    return value in (None, [], {})
