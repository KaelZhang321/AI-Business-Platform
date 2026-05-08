from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from app.services.workflows.types import WorkflowRunContext

GraphEventEnvelope = dict[str, Any]


def build_graph_event_envelope(
    event: Mapping[str, Any],
    *,
    run_context: WorkflowRunContext,
) -> GraphEventEnvelope:
    """把 LangGraph 原始事件压成统一信封。

    功能：
        LangGraph 事件原始结构更偏底层执行细节；这里提前把 workflow 名称、阶段名和
        三类链路标识补齐，后续日志与 SSE 都不必各自重新拼接一遍。

    Args:
        event: LangGraph 输出的原始事件。
        run_context: 当前工作流运行上下文。

    Returns:
        稳定的事件信封字典，至少包含 `workflow / event / node / trace_context / payload`。

    Edge Cases:
        - 部分 graph 级事件没有显式 node 名称，此时 `node` 允许为空
        - `data` 不是字典时，会自动包成 `{"value": ...}`，避免上层再做类型分支
    """

    trace_context = asdict(run_context.trace_context)
    observability_fields = build_workflow_observability_fields(
        run_context=run_context,
        node=_resolve_event_node(event),
        execution_status=_extract_execution_status(event.get("data")),
    )
    return {
        **observability_fields,
        "event": str(event.get("event") or ""),
        "trace_context": trace_context,
        "run_id": event.get("run_id"),
        "tags": list(event.get("tags") or []),
        "payload": _normalize_event_payload(event.get("data")),
    }


def build_workflow_observability_fields(
    *,
    run_context: WorkflowRunContext,
    node: str | None,
    execution_status: str | None = None,
) -> dict[str, Any]:
    """构造 workflow / graph 共享的最小观测字段。

    功能：
        LangGraph 迁移完成后，route、外层 workflow、内层执行图都需要共享同一份最小观测
        字段，避免日志、SSE 事件和未来指标各自再拼一次 `trace / interaction / conversation`。
    """

    trace_context = asdict(run_context.trace_context)
    return {
        "workflow": run_context.workflow_name,
        "phase": run_context.phase,
        "node": node,
        "trace_id": trace_context["trace_id"],
        "interaction_id": trace_context["interaction_id"],
        "conversation_id": trace_context["conversation_id"],
        "execution_status": execution_status,
    }


def format_workflow_observability_log(
    message: str,
    *,
    observability_fields: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
) -> str:
    """把最小观测字段格式化成统一日志文本。

    功能：
        当前阶段先统一日志文本口径，而不是立刻引入新的 metrics SDK。这样 route、workflow
        和执行图可以在不改现有 logging 基础设施的前提下共享同一套排障字段。
    """

    formatted = (
        f"{message} workflow={observability_fields.get('workflow') or '-'}"
        f" phase={observability_fields.get('phase') or '-'}"
        f" node={observability_fields.get('node') or '-'}"
        f" trace_id={observability_fields.get('trace_id') or '-'}"
        f" interaction_id={observability_fields.get('interaction_id') or '-'}"
        f" conversation_id={observability_fields.get('conversation_id') or '-'}"
        f" execution_status={observability_fields.get('execution_status') or '-'}"
    )
    if payload:
        formatted = f"{formatted} payload={dict(payload)}"
    return formatted


def _resolve_event_node(event: Mapping[str, Any]) -> str | None:
    """提取当前事件关联的节点名。"""
    name = event.get("name")
    if isinstance(name, str) and name.strip():
        return name
    metadata = event.get("metadata")
    if isinstance(metadata, Mapping):
        node = metadata.get("langgraph_node")
        if isinstance(node, str) and node.strip():
            return node
    return None


def _normalize_event_payload(payload: Any) -> dict[str, Any]:
    """把事件数据折叠成稳定字典形态。"""
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return dict(payload)
    return {"value": payload}


def _extract_execution_status(payload: Any) -> str | None:
    """从事件 payload 中提取最常用的执行状态字段。"""

    if isinstance(payload, Mapping):
        value = payload.get("execution_status")
        if value is None:
            return None
        return str(value)
    return None
