from __future__ import annotations

import pytest

from app.models.schemas import ApiQueryExecutionPlan, ApiQueryExecutionResult, ApiQueryExecutionStatus, ApiQueryPlanStep
from app.services.api_catalog.graph_models import ApiCatalogSubgraphResult, GraphFieldPath
from app.services.api_catalog.dag_executor import ApiDagExecutor
from app.services.api_catalog.dag_planner import (
    ApiDagPlanner,
    DagPlanValidationError,
    _build_allowed_entries_by_id,
)
from app.services.api_catalog.schema import (
    ApiCatalogEntry,
    ApiCatalogPredecessorParamBinding,
    ApiCatalogPredecessorSpec,
    ApiCatalogSearchResult,
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


def test_validate_plan_normalizes_zero_index_binding() -> None:
    planner = ApiDagPlanner()
    customer_entry = _make_entry(entry_id="customer_info", path="/api/customer/info")
    stored_plan_entry = _make_entry(
        entry_id="stored_plan",
        path="/api/customer/stored-plan",
        required=["encryptedIdCard"],
    )
    candidates = [
        ApiCatalogSearchResult(entry=customer_entry, score=0.95),
        ApiCatalogSearchResult(entry=stored_plan_entry, score=0.9),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_zero_index_binding",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customer_info",
                api_id="customer_info",
                api_path="/api/customer/info",
                params={"customerInfo": "刘海坚"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_stored_plan",
                api_id="stored_plan",
                api_path="/api/customer/stored-plan",
                params={"encryptedIdCard": "$[step_customer_info.data][0].idCard"},
                depends_on=["step_customer_info"],
            ),
        ],
    )

    step_entries = planner.validate_plan(plan, candidates)

    assert step_entries["step_stored_plan"].id == "stored_plan"
    assert plan.steps[1].params["encryptedIdCard"] == "$[step_customer_info.data].idCard"


def test_validate_plan_rejects_non_zero_index_binding() -> None:
    planner = ApiDagPlanner()
    customer_entry = _make_entry(entry_id="customer_info", path="/api/customer/info")
    stored_plan_entry = _make_entry(
        entry_id="stored_plan",
        path="/api/customer/stored-plan",
        required=["encryptedIdCard"],
    )
    candidates = [
        ApiCatalogSearchResult(entry=customer_entry, score=0.95),
        ApiCatalogSearchResult(entry=stored_plan_entry, score=0.9),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_non_zero_index_binding",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customer_info",
                api_id="customer_info",
                api_path="/api/customer/info",
                params={"customerInfo": "刘海坚"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_stored_plan",
                api_id="stored_plan",
                api_path="/api/customer/stored-plan",
                params={"encryptedIdCard": "$[step_customer_info.data][1].idCard"},
                depends_on=["step_customer_info"],
            ),
        ],
    )

    with pytest.raises(DagPlanValidationError) as exc_info:
        planner.validate_plan(plan, candidates)

    assert exc_info.value.code == "planner_binding_syntax_invalid"


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


def test_validate_plan_preserves_cardinality_mismatch_error_code_and_wait_select_metadata() -> None:
    planner = ApiDagPlanner()
    role_list_entry = _make_entry(entry_id="role_list_v1", path="/system/employee/sys-role/list")
    role_list_entry.response_data_path = "data.records"
    role_detail_entry = _make_entry(
        entry_id="role_detail_v1",
        path="/system/employee/sys-role/detail",
        required=["roleId"],
    )
    role_detail_entry.method = "POST"
    candidates = [
        ApiCatalogSearchResult(entry=role_list_entry, score=0.95),
        ApiCatalogSearchResult(entry=role_detail_entry, score=0.92),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_role_detail",
        steps=[
            ApiQueryPlanStep(
                step_id="step_role_list",
                api_id="role_list_v1",
                api_path="/system/employee/sys-role/list",
                params={"pageNo": 1},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_role_detail",
                api_id="role_detail_v1",
                api_path="/system/employee/sys-role/detail",
                params={"roleId": "$[step_role_list.data][*].roleId"},
                depends_on=["step_role_list"],
            ),
        ],
    )
    subgraph = ApiCatalogSubgraphResult(
        anchor_api_ids=["role_detail_v1"],
        support_api_ids=["role_list_v1"],
        field_paths=[
            GraphFieldPath(
                consumer_api_id="role_detail_v1",
                producer_api_id="role_list_v1",
                semantic_key="Role.id",
                source_extract_path="data.records[].roleId",
                target_inject_path="body.roleId",
                is_identifier=True,
                source_array_mode=True,
                target_array_mode=False,
            )
        ],
    )

    from app.services.api_catalog import dag_planner as dag_planner_module

    original_enabled = dag_planner_module.settings.api_catalog_graph_validation_enabled
    dag_planner_module.settings.api_catalog_graph_validation_enabled = True
    try:
        with pytest.raises(DagPlanValidationError) as exc_info:
            planner.validate_plan(plan, candidates, subgraph_result=subgraph)
    finally:
        dag_planner_module.settings.api_catalog_graph_validation_enabled = original_enabled

    assert exc_info.value.code == "planner_cardinality_mismatch"
    assert exc_info.value.metadata["pause_type"] == "WAIT_SELECT"
    assert exc_info.value.metadata["source_step_id"] == "step_role_list"


def test_validate_plan_skips_graph_validation_when_feature_flag_disabled() -> None:
    planner = ApiDagPlanner()
    role_list_entry = _make_entry(entry_id="role_list_v1", path="/system/employee/sys-role/list")
    role_list_entry.response_data_path = "data.records"
    role_detail_entry = _make_entry(
        entry_id="role_detail_v1",
        path="/system/employee/sys-role/detail",
        required=["roleId"],
    )
    role_detail_entry.method = "POST"
    candidates = [
        ApiCatalogSearchResult(entry=role_list_entry, score=0.95),
        ApiCatalogSearchResult(entry=role_detail_entry, score=0.92),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_role_detail_graph_validation_disabled",
        steps=[
            ApiQueryPlanStep(
                step_id="step_role_list",
                api_id="role_list_v1",
                api_path="/system/employee/sys-role/list",
                params={"pageNo": 1},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_role_detail",
                api_id="role_detail_v1",
                api_path="/system/employee/sys-role/detail",
                params={"roleId": "$[step_role_list.data][*].roleId"},
                depends_on=["step_role_list"],
            ),
        ],
    )
    subgraph = ApiCatalogSubgraphResult(
        anchor_api_ids=["role_detail_v1"],
        support_api_ids=["role_list_v1"],
        graph_degraded=True,
        degraded_reason="graph_disabled",
        field_paths=[
            GraphFieldPath(
                consumer_api_id="role_detail_v1",
                producer_api_id="role_list_v1",
                semantic_key="Role.id",
                source_extract_path="data.records[].roleId",
                target_inject_path="body.roleId",
                is_identifier=True,
                source_array_mode=True,
                target_array_mode=False,
            )
        ],
    )

    from app.services.api_catalog import dag_planner as dag_planner_module

    original_enabled = dag_planner_module.settings.api_catalog_graph_validation_enabled
    dag_planner_module.settings.api_catalog_graph_validation_enabled = False
    try:
        step_entries = planner.validate_plan(plan, candidates, subgraph_result=subgraph)
    finally:
        dag_planner_module.settings.api_catalog_graph_validation_enabled = original_enabled

    assert step_entries["step_role_list"].id == "role_list_v1"
    assert step_entries["step_role_detail"].id == "role_detail_v1"


def test_validate_plan_rejects_missing_required_predecessor_step() -> None:
    planner = ApiDagPlanner()
    detail_entry = _make_entry(entry_id="role_detail_v1", path="/api/roles/detail", required=["roleId"])
    predecessor_entry = _make_entry(entry_id="role_list_v1", path="/api/roles/list")
    candidates = [
        ApiCatalogSearchResult(entry=detail_entry, score=0.95),
        ApiCatalogSearchResult(entry=predecessor_entry, score=0.93),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_missing_required_predecessor_step",
        steps=[
            ApiQueryPlanStep(
                step_id="step_role_detail",
                api_id="role_detail_v1",
                api_path="/api/roles/detail",
                params={"roleId": "S1001"},
                depends_on=[],
            )
        ],
    )
    predecessor_hints = {
        "role_detail_v1": [
            ApiCatalogPredecessorSpec(
                predecessor_api_id="role_list_v1",
                required=True,
                order=1,
                param_bindings=[
                    ApiCatalogPredecessorParamBinding(
                        target_param="roleId",
                        source_path="$.data[*].id",
                        select_mode="first",
                    )
                ],
            )
        ]
    }

    with pytest.raises(DagPlanValidationError) as exc_info:
        planner.validate_plan(plan, candidates, predecessor_hints=predecessor_hints)

    assert exc_info.value.code == "planner_missing_required_predecessor"


def test_validate_plan_rejects_required_predecessor_without_binding() -> None:
    planner = ApiDagPlanner()
    detail_entry = _make_entry(entry_id="role_detail_v1", path="/api/roles/detail", required=["roleId"])
    predecessor_entry = _make_entry(entry_id="role_list_v1", path="/api/roles/list")
    candidates = [
        ApiCatalogSearchResult(entry=detail_entry, score=0.95),
        ApiCatalogSearchResult(entry=predecessor_entry, score=0.93),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_required_predecessor_without_binding",
        steps=[
            ApiQueryPlanStep(
                step_id="step_role_list",
                api_id="role_list_v1",
                api_path="/api/roles/list",
                params={},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_role_detail",
                api_id="role_detail_v1",
                api_path="/api/roles/detail",
                params={"roleId": "S1001"},
                depends_on=["step_role_list"],
            ),
        ],
    )
    predecessor_hints = {
        "role_detail_v1": [
            ApiCatalogPredecessorSpec(
                predecessor_api_id="role_list_v1",
                required=True,
                order=1,
                param_bindings=[
                    ApiCatalogPredecessorParamBinding(
                        target_param="roleId",
                        source_path="$.data[*].id",
                        select_mode="first",
                    )
                ],
            )
        ]
    }

    with pytest.raises(DagPlanValidationError) as exc_info:
        planner.validate_plan(plan, candidates, predecessor_hints=predecessor_hints)

    assert exc_info.value.code == "planner_missing_required_predecessor"


def test_validate_plan_allows_optional_predecessor_omission() -> None:
    planner = ApiDagPlanner()
    detail_entry = _make_entry(entry_id="role_detail_v1", path="/api/roles/detail", required=["roleId"])
    predecessor_entry = _make_entry(entry_id="role_list_v1", path="/api/roles/list")
    candidates = [
        ApiCatalogSearchResult(entry=detail_entry, score=0.95),
        ApiCatalogSearchResult(entry=predecessor_entry, score=0.93),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_optional_predecessor_omitted",
        steps=[
            ApiQueryPlanStep(
                step_id="step_role_detail",
                api_id="role_detail_v1",
                api_path="/api/roles/detail",
                params={"roleId": "S1001"},
                depends_on=[],
            )
        ],
    )
    predecessor_hints = {
        "role_detail_v1": [
            ApiCatalogPredecessorSpec(
                predecessor_api_id="role_list_v1",
                required=False,
                order=1,
                param_bindings=[
                    ApiCatalogPredecessorParamBinding(
                        target_param="roleId",
                        source_path="$.data[*].id",
                        select_mode="first",
                    )
                ],
            )
        ]
    }

    step_entries = planner.validate_plan(plan, candidates, predecessor_hints=predecessor_hints)
    assert step_entries["step_role_detail"].id == "role_detail_v1"


def test_validate_plan_allows_step_when_predecessor_is_only_declared_in_companion_specs() -> None:
    planner = ApiDagPlanner()
    detail_entry = _make_entry(entry_id="role_detail_v1", path="/api/roles/detail", required=["roleId"])
    predecessor_entry = _make_entry(entry_id="role_list_v1", path="/api/roles/list")
    detail_entry.predecessors = [
        ApiCatalogPredecessorSpec(
            predecessor_api_id="role_list_v1",
            required=True,
            order=1,
            param_bindings=[
                ApiCatalogPredecessorParamBinding(
                    target_param="roleId",
                    source_path="$.data[*].id",
                    select_mode="first",
                )
            ],
        )
    ]
    # 模拟召回仅命中 detail，前置只作为“伴生信息”挂在 detail.predecessors 中。
    candidates = [
        ApiCatalogSearchResult(entry=detail_entry, score=0.95),
        ApiCatalogSearchResult(entry=predecessor_entry, score=0.93),
    ]
    plan = ApiQueryExecutionPlan(
        plan_id="dag_predecessor_companion_allowlist",
        steps=[
            ApiQueryPlanStep(
                step_id="step_role_list",
                api_id="role_list_v1",
                api_path="/api/roles/list",
                params={},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_role_detail",
                api_id="role_detail_v1",
                api_path="/api/roles/detail",
                params={"roleId": "$[step_role_list.data].id"},
                depends_on=["step_role_list"],
            ),
        ],
    )

    step_entries = planner.validate_plan(
        plan,
        candidates,
        predecessor_hints={"role_detail_v1": detail_entry.predecessors},
        subgraph_result=ApiCatalogSubgraphResult(
            degraded_reason="",
            field_paths=[
                GraphFieldPath(
                    consumer_api_id="role_detail_v1",
                    producer_api_id="role_list_v1",
                    semantic_key="Role.id",
                    source_extract_path="data.id",
                    target_inject_path="queryParams.roleId",
                    is_identifier=True,
                    source_array_mode=False,
                    target_array_mode=False,
                )
            ],
        ),
    )
    assert step_entries["step_role_list"].id == "role_list_v1"
    assert step_entries["step_role_detail"].id == "role_detail_v1"


def test_build_allowed_entries_by_id_supports_predecessor_entry_objects() -> None:
    detail_entry = _make_entry(entry_id="role_detail_v1", path="/api/roles/detail")
    predecessor_entry = _make_entry(entry_id="role_list_v1", path="/api/roles/list")
    # 新形态：predecessor 直接携带 ApiCatalogEntry，不依赖 predecessor_api_id 查表。
    detail_entry.predecessors = [predecessor_entry]  # type: ignore[list-item]

    allowed_entries = _build_allowed_entries_by_id([ApiCatalogSearchResult(entry=detail_entry, score=0.95)])

    assert allowed_entries["role_detail_v1"] is detail_entry
    assert allowed_entries["role_list_v1"] is predecessor_entry


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

        async def call(self, entry, params, user_token=None, trace_id=None, user_id=None):
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
        async def call(self, entry, params, user_token=None, trace_id=None, user_id=None):
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
        async def call(self, entry, params, user_token=None, trace_id=None, user_id=None):
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
