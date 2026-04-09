from __future__ import annotations

import asyncio

import pytest

from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryPlanStep,
)
from app.services.api_catalog.schema import ApiCatalogEntry
from app.services.api_query_execution_graph import (
    ApiQueryExecutionBudget,
    ApiQueryExecutionGraph,
)


def _make_entry(
    *,
    entry_id: str,
    path: str,
    required: list[str] | None = None,
) -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id=entry_id,
        description=f"查询 {entry_id}",
        domain="crm",
        operation_safety="query",
        method="GET",
        path=path,
        param_schema={
            "type": "object",
            "properties": {
                "owner_id": {"type": "string"},
                "customer_ids": {"type": "array"},
            },
            "required": required or [],
        },
    )


@pytest.mark.asyncio
async def test_execution_graph_keeps_dependency_order_and_param_binding() -> None:
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    owner_entry = _make_entry(entry_id="owner_profile", path="/api/crm/owner")
    orders_entry = _make_entry(
        entry_id="orders_summary",
        path="/api/crm/orders/summary",
        required=["owner_id", "customer_ids"],
    )
    plan = ApiQueryExecutionPlan(
        plan_id="dag_dependency_order",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_id="customers",
                api_path=customers_entry.path,
                params={"owner_id": "E8899"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_owner",
                api_id="owner_profile",
                api_path=owner_entry.path,
                params={"owner_id": "E8899"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_orders",
                api_id="orders_summary",
                api_path=orders_entry.path,
                params={
                    "owner_id": "$[step_owner.data].owner_id",
                    "customer_ids": "$[step_customers.data][*].customerId",
                },
                depends_on=["step_customers", "step_owner"],
            ),
        ],
    )

    class StubExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def call(self, entry, params, user_token=None, trace_id=None):
            self.calls.append((entry.id, dict(params)))
            if entry.id == "customers":
                await asyncio.sleep(0.01)
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"customerId": "C001"}],
                    total=1,
                    trace_id=trace_id,
                )
            if entry.id == "owner_profile":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data={"owner_id": "E8899"},
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"ok": True}],
                total=1,
                trace_id=trace_id,
            )

    stub_executor = StubExecutor()
    graph = ApiQueryExecutionGraph(stub_executor)
    result = await graph.run(
        plan,
        {
            "step_customers": customers_entry,
            "step_owner": owner_entry,
            "step_orders": orders_entry,
        },
        user_token="Bearer test-token",
        trace_id="trace-execution-graph-order",
    )

    assert result.aggregate_status == ApiQueryExecutionStatus.SUCCESS
    assert result.report.execution_order == ["step_customers", "step_owner", "step_orders"]
    assert result.report.records_by_step_id["step_orders"].resolved_params == {
        "owner_id": "E8899",
        "customer_ids": ["C001"],
    }
    assert set(call[0] for call in stub_executor.calls[:2]) == {"customers", "owner_profile"}
    assert stub_executor.calls[-1][0] == "orders_summary"


@pytest.mark.asyncio
async def test_execution_graph_skips_downstream_when_upstream_binding_is_empty() -> None:
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    orders_entry = _make_entry(
        entry_id="orders_summary",
        path="/api/crm/orders/summary",
        required=["customer_ids"],
    )
    plan = ApiQueryExecutionPlan(
        plan_id="dag_empty_upstream_graph",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_id="customers",
                api_path=customers_entry.path,
                params={"owner_id": "E8899"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_orders",
                api_id="orders_summary",
                api_path=orders_entry.path,
                params={"customer_ids": "$[step_customers.data][*].customerId"},
                depends_on=["step_customers"],
            ),
        ],
    )

    class StubExecutor:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def call(self, entry, params, user_token=None, trace_id=None):
            self.calls.append(entry.id)
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.EMPTY,
                data=[],
                total=0,
                trace_id=trace_id,
            )

    stub_executor = StubExecutor()
    graph = ApiQueryExecutionGraph(stub_executor)
    result = await graph.run(
        plan,
        {
            "step_customers": customers_entry,
            "step_orders": orders_entry,
        },
        user_token=None,
        trace_id="trace-execution-graph-empty",
    )

    assert result.aggregate_status == ApiQueryExecutionStatus.EMPTY
    assert stub_executor.calls == ["customers"]
    downstream_result = result.report.records_by_step_id["step_orders"].execution_result
    assert downstream_result.status == ApiQueryExecutionStatus.SKIPPED
    assert downstream_result.skipped_reason == "skipped_due_to_empty_upstream"
    assert downstream_result.meta["empty_bindings"] == ["$[step_customers.data][*].customerId"]


@pytest.mark.asyncio
async def test_execution_graph_returns_partial_success_when_some_steps_fail() -> None:
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    orders_entry = _make_entry(entry_id="orders_summary", path="/api/crm/orders/summary")
    plan = ApiQueryExecutionPlan(
        plan_id="dag_partial_success_graph",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_id="customers",
                api_path=customers_entry.path,
                params={"owner_id": "E8899"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_orders",
                api_id="orders_summary",
                api_path=orders_entry.path,
                params={},
                depends_on=[],
            ),
        ],
    )

    class StubExecutor:
        async def call(self, entry, params, user_token=None, trace_id=None):
            if entry.id == "customers":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"customerId": "C001"}],
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.ERROR,
                data=None,
                total=0,
                error="ERP 服务超时",
                trace_id=trace_id,
            )

    graph = ApiQueryExecutionGraph(StubExecutor())
    result = await graph.run(
        plan,
        {
            "step_customers": customers_entry,
            "step_orders": orders_entry,
        },
        user_token=None,
        trace_id="trace-execution-graph-partial",
    )

    assert result.aggregate_status == ApiQueryExecutionStatus.PARTIAL_SUCCESS
    assert result.anchor_step_id == "step_customers"
    assert result.error_summary == "ERP 服务超时"
    assert result.report.records_by_step_id["step_orders"].execution_result.status == ApiQueryExecutionStatus.ERROR


@pytest.mark.asyncio
async def test_execution_graph_folds_step_timeout_into_error_result() -> None:
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    plan = ApiQueryExecutionPlan(
        plan_id="dag_step_timeout_graph",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_id="customers",
                api_path=customers_entry.path,
                params={"owner_id": "E8899"},
                depends_on=[],
            )
        ],
    )

    class SlowExecutor:
        async def call(self, entry, params, user_token=None, trace_id=None):
            await asyncio.sleep(0.05)
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001"}],
                total=1,
                trace_id=trace_id,
            )

    graph = ApiQueryExecutionGraph(
        SlowExecutor(),
        budget=ApiQueryExecutionBudget(
            max_step_count=4,
            step_timeout_seconds=0.01,
            graph_timeout_seconds=1.0,
            min_step_budget_seconds=0.01,
        ),
    )
    result = await graph.run(
        plan,
        {"step_customers": customers_entry},
        user_token=None,
        trace_id="trace-execution-step-timeout",
    )

    record = result.report.records_by_step_id["step_customers"].execution_result
    assert result.graph_failed is False
    assert result.aggregate_status == ApiQueryExecutionStatus.ERROR
    assert record.error_code == "EXECUTION_STEP_TIMEOUT"
    assert record.retryable is True


@pytest.mark.asyncio
async def test_execution_graph_folds_runtime_exception_into_synthetic_report() -> None:
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    plan = ApiQueryExecutionPlan(
        plan_id="dag_graph_failure",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_id="customers",
                api_path=customers_entry.path,
                params={"owner_id": "E8899"},
                depends_on=[],
            )
        ],
    )

    class BrokenExecutor:
        async def call(self, entry, params, user_token=None, trace_id=None):
            raise RuntimeError("executor exploded")

    graph = ApiQueryExecutionGraph(BrokenExecutor())
    result = await graph.run(
        plan,
        {"step_customers": customers_entry},
        user_token=None,
        trace_id="trace-execution-graph-failure",
    )

    record = result.report.records_by_step_id["step_customers"].execution_result
    assert result.graph_failed is True
    assert result.aggregate_status == ApiQueryExecutionStatus.ERROR
    assert result.report.execution_order == ["step_customers"]
    assert record.error_code == "EXECUTION_GRAPH_RUN_FAILED"
    assert record.meta["graph_failed"] is True
