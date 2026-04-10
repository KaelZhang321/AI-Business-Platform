"""第三阶段 DAG 执行兼容门面。

功能：
    对外继续暴露历史上的 `ApiDagExecutor.execute_plan()` 和 `DagExecutionReport`，
    但真实调度已经委托给 `ApiQueryExecutionGraph`。这样第五阶段、route 和测试仍然
    使用熟悉的报告结构，不需要感知第四阶段底层从 TopologicalSorter 切到了 LangGraph。
"""

from __future__ import annotations

from app.models.schemas import ApiQueryExecutionPlan
from app.services.api_catalog.dag_runtime import DagExecutionReport, DagStepExecutionRecord
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.schema import ApiCatalogEntry
from app.services.api_query_execution_graph import ApiQueryExecutionGraph

__all__ = ["ApiDagExecutor", "DagExecutionReport", "DagStepExecutionRecord"]


class ApiDagExecutor:
    """按历史接口执行第三阶段只读 DAG。

    功能：
        该类不再自己维护拓扑排序和并发层调度，而是作为 compatibility facade 调用
        `ApiQueryExecutionGraph`。保留这层的原因是：

        1. 外层 workflow 和 route 仍然依赖 `DagExecutionReport`
        2. 第五阶段渲染不应该被迫理解 LangGraph 内部状态结构
        3. 灰度期间如果需要回滚，只需要替换门面内部实现
    """

    def __init__(self, api_executor: ApiExecutor) -> None:
        self._execution_graph = ApiQueryExecutionGraph(api_executor)

    async def execute_plan(
        self,
        plan: ApiQueryExecutionPlan,
        step_entries: dict[str, ApiCatalogEntry],
        *,
        user_token: str | None,
        user_id: str | None = None,
        trace_id: str,
        interaction_id: str | None = None,
        conversation_id: str | None = None,
    ) -> DagExecutionReport:
        """执行只读 DAG 并返回兼容报告。

        功能：
            这一层继续维持旧的 `execute_plan` 契约，但把请求级 `user_id` 一并下传到
            `ApiQueryExecutionGraph`，确保 runtime invoke 场景也能拿到和 route 层一致的
            最终用户身份，而不是只剩 token。

        Args:
            plan: 已通过白名单校验的执行计划。
            step_entries: `step_id -> ApiCatalogEntry` 映射。
            user_token: 透传给下游的认证头。
            user_id: 当前请求最终认定的用户主键。
            trace_id: 当前请求链路 Trace ID。
            interaction_id: 多次追问共享的交互标识。
            conversation_id: 跨轮对话共享的会话标识。

        Returns:
            兼容历史 DAG 门面的执行报告。
        """

        graph_result = await self._execution_graph.run(
            plan,
            step_entries,
            user_token=user_token,
            user_id=user_id,
            trace_id=trace_id,
            interaction_id=interaction_id,
            conversation_id=conversation_id,
        )
        return graph_result.report
