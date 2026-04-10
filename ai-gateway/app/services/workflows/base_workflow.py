from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Generic, TypeVar

from app.services.workflows.graph_events import GraphEventEnvelope, build_graph_event_envelope
from app.services.workflows.types import WorkflowRunContext, WorkflowTraceContext

StateT = TypeVar("StateT")


class BaseStateGraphWorkflow(ABC, Generic[StateT]):
    """LangGraph 工作流公共基类。

    功能：
        统一封装 graph 的 build / compile / invoke 生命周期，让业务 workflow 只关心：

        1. 图怎么搭
        2. 初始状态怎么准备
        3. 业务节点如何推进状态

        这样后续 `/api-query`、聊天和其他链路都不需要再复制一份懒编译与事件信封样板。

    Edge Cases:
        - 图默认按单例缓存，避免每次请求重复 compile
        - 需要热切换或测试强制重建时，可调用 `reset_graph()`
    """

    def __init__(self) -> None:
        self._compiled_graph: Any | None = None

    @property
    @abstractmethod
    def workflow_name(self) -> str:
        """返回工作流稳定名称。"""

    @abstractmethod
    def build_graph(self) -> Any:
        """构建 LangGraph `StateGraph` 实例。"""

    def get_graph(self, *, force_recompile: bool = False) -> Any:
        """获取已编译 graph。

        功能：
            compile 通常比单次 ainvoke 更重，因此这里默认走懒加载缓存；只有测试或
            显式切图时才允许强制重编译。
        """

        if self._compiled_graph is None or force_recompile:
            self._compiled_graph = self.build_graph().compile()
        return self._compiled_graph

    def reset_graph(self) -> None:
        """清空已编译 graph 缓存。"""

        self._compiled_graph = None

    async def invoke(self, initial_state: StateT) -> StateT:
        """执行一次非流式 graph 调用。"""

        return await self.get_graph().ainvoke(initial_state)

    async def stream_events(
        self,
        initial_state: StateT,
        *,
        trace_id: str,
        interaction_id: str | None = None,
        conversation_id: str | None = None,
        phase: str | None = None,
    ) -> AsyncIterator[GraphEventEnvelope]:
        """流式输出统一事件信封。

        功能：
            业务 workflow 如果要接 SSE 或结构化日志，不应直接透传 LangGraph 原始事件；
            这里先把链路标识和 workflow 维度补齐，避免上层每次重复组装。
        """

        run_context = WorkflowRunContext(
            workflow_name=self.workflow_name,
            trace_context=WorkflowTraceContext(
                trace_id=trace_id,
                interaction_id=interaction_id,
                conversation_id=conversation_id,
            ),
            phase=phase,
        )
        async for event in self.get_graph().astream_events(initial_state, version="v1"):
            yield build_graph_event_envelope(event, run_context=run_context)
