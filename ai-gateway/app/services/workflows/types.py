from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowTraceContext:
    """工作流链路标识。

    功能：
        把 `trace / interaction / conversation` 三类标识固定成统一载体，后续不同
        workflow 在打日志、做 SSE 信封和构造审计事件时都只消费这一份事实。

    入参业务含义：
        - `trace_id`：单次请求级链路追踪 ID
        - `interaction_id`：同一次连续交互内的多请求聚合标识
        - `conversation_id`：跨多轮对话保留的会话 ID
    """

    trace_id: str
    interaction_id: str | None = None
    conversation_id: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowRunContext:
    """单次工作流运行的轻量上下文。

    功能：
        公共工作流层只保留“当前是哪条 workflow、归属哪个阶段、挂着哪组链路标识”
        这类轻量事实，避免在 substrate 阶段就把业务状态污染进通用层。

    入参业务含义：
        - `workflow_name`：当前工作流的稳定标识，便于日志聚合
        - `trace_context`：当前运行共享的链路标识
        - `phase`：业务方可选传入的阶段名，用于把同一 workflow 再细分到子阶段
    """

    workflow_name: str
    trace_context: WorkflowTraceContext
    phase: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowDegradeMetadata:
    """公共降级元信息。

    功能：
        工作流节点失败后，外层图最终要统一折叠为响应或事件。把降级码、原因和是否可重试
        抽成轻量对象，是为了避免每条链路各自发明一套错误壳。
    """

    code: str
    reason: str
    retryable: bool = False
