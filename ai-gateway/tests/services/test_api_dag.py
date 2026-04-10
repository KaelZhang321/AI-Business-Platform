from __future__ import annotations

import pytest

from app.models.schemas import ApiQueryExecutionPlan, ApiQueryExecutionResult, ApiQueryExecutionStatus, ApiQueryPlanStep
from app.services.api_catalog.dag_executor import ApiDagExecutor
from app.services.api_catalog.dag_planner import ApiDagPlanner, DagPlanValidationError
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult


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
            "properties": {"customer_ids": {"type": "array"}, "owner_id": {"type": "string"}},
            "required": required or [],
        },
    )


def test_validate_plan_rejects_cycle() -> None:
    planner = ApiDagPlanner()
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    orders_entry = _make_entry(entry_id="orders", path="/api/orders/stats", required=["customer_ids"])
    candidates = [
        ApiCatalogSearchResult(entry=customers_entry, score=0.9),
        ApiCatalogSearchResult(entry=orders_entry, score=0.88),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_cycle",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_path="/api/crm/customers",
                depends_on=["step_orders"],
            ),
            ApiQueryPlanStep(
                step_id="step_orders",
                api_path="/api/orders/stats",
                params={"customer_ids": "$[step_customers.data][*].id"},
                depends_on=["step_customers"],
            ),
        ],
    )

    with pytest.raises(DagPlanValidationError) as exc_info:
        planner.validate_plan(plan, candidates)

    assert exc_info.value.code == "planner_cycle_detected"


def test_validate_plan_rejects_mutation_entry() -> None:
    planner = ApiDagPlanner()
    unsafe_entry = ApiCatalogEntry(
        id="customer_update",
        description="更新客户",
        domain="crm",
        operation_safety="mutation",
        method="POST",
        path="/api/crm/customers/update",
    )
    plan = ApiQueryExecutionPlan(
        plan_id="dag_mutation_block",
        steps=[
            ApiQueryPlanStep(
                step_id="step_update",
                api_id="customer_update",
                api_path="/api/crm/customers/update",
                params={"customerId": "C001"},
                depends_on=[],
            )
        ],
    )

    with pytest.raises(DagPlanValidationError) as exc_info:
        planner.validate_plan(plan, [ApiCatalogSearchResult(entry=unsafe_entry, score=0.9)])

    assert exc_info.value.code == "planner_unsafe_api"


@pytest.mark.asyncio
async def test_execute_plan_skips_downstream_when_json_binding_is_empty() -> None:
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    orders_entry = _make_entry(entry_id="orders", path="/api/orders/stats", required=["customer_ids"])
    plan = ApiQueryExecutionPlan(
        plan_id="dag_empty_upstream",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_path="/api/crm/customers",
                params={"owner_id": "E8899"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_orders",
                api_path="/api/orders/stats",
                params={"customer_ids": "$[step_customers.data][*].id"},
                depends_on=["step_customers"],
            ),
        ],
    )

    class StubApiExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def call(self, entry, params, user_token=None, trace_id=None):
            self.calls.append((entry.id, dict(params)))
            if entry.id == "customers":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.EMPTY,
                    data=[],
                    total=0,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"ok": True}],
                total=1,
                trace_id=trace_id,
            )

    stub_executor = StubApiExecutor()
    dag_executor = ApiDagExecutor(stub_executor)
    report = await dag_executor.execute_plan(
        plan,
        {
            "step_customers": customers_entry,
            "step_orders": orders_entry,
        },
        user_token=None,
        trace_id="trace-dag-empty",
    )

    assert [call[0] for call in stub_executor.calls] == ["customers"]
    assert report.records_by_step_id["step_customers"].execution_result.status == ApiQueryExecutionStatus.EMPTY
    downstream_result = report.records_by_step_id["step_orders"].execution_result
    assert downstream_result.status == ApiQueryExecutionStatus.SKIPPED
    assert downstream_result.skipped_reason == "skipped_due_to_empty_upstream"
    assert downstream_result.meta["empty_bindings"] == ["$[step_customers.data][*].id"]


@pytest.mark.asyncio
async def test_execute_plan_keeps_partial_success_report_shape_after_graph_cutover() -> None:
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    orders_entry = _make_entry(entry_id="orders", path="/api/orders/stats")
    plan = ApiQueryExecutionPlan(
        plan_id="dag_partial_success_facade",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_path="/api/crm/customers",
                params={"owner_id": "E8899"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_orders",
                api_path="/api/orders/stats",
                params={},
                depends_on=[],
            ),
        ],
    )

    class StubApiExecutor:
        async def call(self, entry, params, user_token=None, trace_id=None):
            if entry.id == "customers":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"id": "C001"}],
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.ERROR,
                data=None,
                total=0,
                error="订单系统不可用",
                trace_id=trace_id,
            )

    report = await ApiDagExecutor(StubApiExecutor()).execute_plan(
        plan,
        {
            "step_customers": customers_entry,
            "step_orders": orders_entry,
        },
        user_token=None,
        trace_id="trace-dag-partial",
    )

    assert report.execution_order == ["step_customers", "step_orders"]
    assert report.records_by_step_id["step_customers"].execution_result.status == ApiQueryExecutionStatus.SUCCESS
    assert report.records_by_step_id["step_orders"].execution_result.status == ApiQueryExecutionStatus.ERROR


@pytest.mark.asyncio
async def test_execute_plan_returns_synthetic_report_when_graph_runtime_crashes() -> None:
    customers_entry = _make_entry(entry_id="customers", path="/api/crm/customers")
    plan = ApiQueryExecutionPlan(
        plan_id="dag_graph_failed_facade",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_path="/api/crm/customers",
                params={"owner_id": "E8899"},
                depends_on=[],
            )
        ],
    )

    class BrokenApiExecutor:
        async def call(self, entry, params, user_token=None, trace_id=None):
            raise RuntimeError("executor crashed")

    report = await ApiDagExecutor(BrokenApiExecutor()).execute_plan(
        plan,
        {"step_customers": customers_entry},
        user_token=None,
        trace_id="trace-dag-graph-failed",
    )

    synthetic_result = report.records_by_step_id["step_customers"].execution_result
    assert report.execution_order == ["step_customers"]
    assert synthetic_result.status == ApiQueryExecutionStatus.ERROR
    assert synthetic_result.error_code == "EXECUTION_GRAPH_RUN_FAILED"
    assert synthetic_result.meta["graph_failed"] is True
