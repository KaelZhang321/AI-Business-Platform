"""第三阶段 DAG 运行时公共类型。

功能：
    `DagStepExecutionRecord` 和 `DagExecutionReport` 已经被第五阶段渲染、响应构造、
    route 回归测试共同依赖。随着第四阶段从自研拓扑执行器切到 LangGraph，这两个
    类型需要从具体执行实现中抽离，避免 compatibility facade 与新执行子图互相
    导入形成循环依赖。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.schemas.api_query import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryPlanStep,
)
from app.services.api_catalog.schema import ApiCatalogEntry


@dataclass
class DagStepExecutionRecord:
    """第三阶段单个步骤的执行记录。

    功能：
        统一封装“Planner 步骤定义 + 实际命中的目录项 + 运行期解析参数 + 标准化执行结果”，
        让第五阶段只消费稳定的步骤事实，而不用感知底层执行骨架是 TopologicalSorter
        还是 LangGraph。

    入参业务含义：
        step: 当前步骤的稳定规划定义，提供 `step_id / depends_on / api_path` 等上下文。
        entry: 执行阶段真正命中的目录项白名单实体，承载 method/domain/schema 等元数据。
        resolved_params: 已完成 JSONPath 绑定解析的实际请求参数。
        execution_result: 节点执行后的统一结果状态机对象。

    返回值约束：
        该对象只在网关内部流转，不直接暴露给前端。
    """

    step: ApiQueryPlanStep
    entry: ApiCatalogEntry
    resolved_params: dict[str, Any]
    execution_result: ApiQueryExecutionResult


@dataclass
class DagExecutionReport:
    """第三阶段 DAG 的完整执行报告。

    功能：
        对外保持 `plan + records_by_step_id + execution_order` 这一份兼容结构，保证
        第五阶段和历史测试无需知道第四阶段底层已经切换到 LangGraph 子图。
    """

    plan: ApiQueryExecutionPlan
    records_by_step_id: dict[str, DagStepExecutionRecord]
    execution_order: list[str]
