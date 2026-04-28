from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.graph import END, StateGraph

from app.services.workflows.base_workflow import BaseStateGraphWorkflow
from app.services.workflows.graph_events import build_graph_event_envelope
from app.services.workflows.types import WorkflowRunContext, WorkflowTraceContext


class CounterState(TypedDict, total=False):
    """测试专用状态。"""

    value: int


class DummyWorkflow(BaseStateGraphWorkflow[CounterState]):
    """验证公共 workflow substrate 的最小替身。"""

    def __init__(self) -> None:
        super().__init__()
        self.build_count = 0

    @property
    def workflow_name(self) -> str:
        return "dummy_workflow"

    def build_graph(self):
        self.build_count += 1
        graph = StateGraph(CounterState)

        async def increment(state: CounterState) -> CounterState:
            return {"value": state.get("value", 0) + 1}

        graph.add_node("increment", increment)
        graph.set_entry_point("increment")
        graph.add_edge("increment", END)
        return graph


@pytest.mark.asyncio
async def test_base_workflow_reuses_compiled_graph() -> None:
    """同一 workflow 多次运行时应复用已编译 graph。"""

    workflow = DummyWorkflow()

    first_state = await workflow.invoke({"value": 1})
    second_state = await workflow.invoke({"value": 5})

    assert first_state["value"] == 2
    assert second_state["value"] == 6
    assert workflow.build_count == 1


@pytest.mark.asyncio
async def test_base_workflow_streams_normalized_event_envelopes() -> None:
    """公共层输出的事件必须带齐 workflow 和链路标识。"""

    workflow = DummyWorkflow()

    events = [
        event
        async for event in workflow.stream_events(
            {"value": 0},
            trace_id="trace-001",
            interaction_id="interaction-001",
            conversation_id="conversation-001",
            phase="wave1",
        )
    ]

    assert events
    assert any(event["node"] == "increment" for event in events)
    assert all(event["workflow"] == "dummy_workflow" for event in events)
    assert all(event["trace_id"] == "trace-001" for event in events)
    assert all(event["trace_context"]["trace_id"] == "trace-001" for event in events)
    assert all(event["phase"] == "wave1" for event in events)


def test_graph_event_envelope_normalizes_non_mapping_payload() -> None:
    """原始事件数据不是字典时，仍要输出稳定 payload 结构。"""

    envelope = build_graph_event_envelope(
        {
            "event": "on_graph_end",
            "name": "dummy_workflow",
            "data": "completed",
            "run_id": "run-001",
        },
        run_context=WorkflowRunContext(
            workflow_name="dummy_workflow",
            trace_context=WorkflowTraceContext(trace_id="trace-001"),
            phase="phase-test",
        ),
    )

    assert envelope == {
        "workflow": "dummy_workflow",
        "phase": "phase-test",
        "trace_id": "trace-001",
        "interaction_id": None,
        "conversation_id": None,
        "execution_status": None,
        "event": "on_graph_end",
        "node": "dummy_workflow",
        "trace_context": {
            "trace_id": "trace-001",
            "interaction_id": None,
            "conversation_id": None,
        },
        "run_id": "run-001",
        "tags": [],
        "payload": {"value": "completed"},
    }
