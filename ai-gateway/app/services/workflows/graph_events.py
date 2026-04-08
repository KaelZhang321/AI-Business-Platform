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

    return {
        "workflow": run_context.workflow_name,
        "phase": run_context.phase,
        "event": str(event.get("event") or ""),
        "node": _resolve_event_node(event),
        "trace_context": asdict(run_context.trace_context),
        "run_id": event.get("run_id"),
        "tags": list(event.get("tags") or []),
        "payload": _normalize_event_payload(event.get("data")),
    }


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
