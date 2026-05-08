from __future__ import annotations

import pytest

from app.models.schemas import ApiQueryExecutionPlan, ApiQueryPlanStep
from app.services.api_catalog.graph_models import ApiCatalogSubgraphResult, GraphFieldPath
from app.services.api_catalog.graph_plan_validator import GraphPlanValidationError, GraphPlanValidator
from app.services.api_catalog.schema import ApiCatalogEntry


def _make_entry(
    *,
    entry_id: str,
    path: str,
    method: str = "GET",
    required: list[str] | None = None,
    response_data_path: str = "data",
) -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id=entry_id,
        description=f"查询 {entry_id}",
        domain="iam",
        operation_safety="query",
        method=method,
        path=path,
        response_data_path=response_data_path,
        param_schema={
            "type": "object",
            "properties": {
                "roleId": {"type": "string"},
                "roleIds": {"type": "array"},
                "roleName": {"type": "string"},
            },
            "required": required or [],
        },
    )


def _make_dependency_plan(*, binding_expression: str, target_param: str = "roleId") -> ApiQueryExecutionPlan:
    return ApiQueryExecutionPlan(
        plan_id="dag_role_dependency",
        steps=[
            ApiQueryPlanStep(
                step_id="step_role_list",
                api_id="role_list_v1",
                api_path="/system/employee/sys-role/list",
                params={"pageNo": 1, "pageSize": 10},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_role_detail",
                api_id="role_detail_v1",
                api_path="/system/employee/sys-role/detail",
                params={target_param: binding_expression},
                depends_on=["step_role_list"],
            ),
        ],
    )


def _make_step_entries() -> dict[str, ApiCatalogEntry]:
    return {
        "step_role_list": _make_entry(
            entry_id="role_list_v1",
            path="/system/employee/sys-role/list",
            method="GET",
            response_data_path="data.records",
        ),
        "step_role_detail": _make_entry(
            entry_id="role_detail_v1",
            path="/system/employee/sys-role/detail",
            method="POST",
            required=["roleId"],
        ),
    }


def _make_identifier_path(
    *,
    source_extract_path: str = "data.records[].roleId",
    source_array_mode: bool = True,
    target_array_mode: bool = False,
) -> GraphFieldPath:
    return GraphFieldPath(
        consumer_api_id="role_detail_v1",
        producer_api_id="role_list_v1",
        semantic_key="Role.id",
        source_extract_path=source_extract_path,
        target_inject_path="body.roleId",
        is_identifier=True,
        source_array_mode=source_array_mode,
        target_array_mode=target_array_mode,
    )


def test_validator_rejects_missing_field_path_when_graph_has_no_supporting_edge() -> None:
    validator = GraphPlanValidator()
    plan = _make_dependency_plan(binding_expression="$[step_role_list.data][*].roleId")

    with pytest.raises(GraphPlanValidationError) as exc_info:
        validator.validate_plan(
            plan=plan,
            step_entries=_make_step_entries(),
            subgraph_result=ApiCatalogSubgraphResult(anchor_api_ids=["role_detail_v1"]),
        )

    assert exc_info.value.code == "planner_missing_field_path"


def test_validator_rejects_wrong_field_transfer_when_target_path_exists_but_source_field_is_wrong() -> None:
    validator = GraphPlanValidator()
    plan = _make_dependency_plan(binding_expression="$[step_role_list.data][*].roleName")

    with pytest.raises(GraphPlanValidationError) as exc_info:
        validator.validate_plan(
            plan=plan,
            step_entries=_make_step_entries(),
            subgraph_result=ApiCatalogSubgraphResult(
                anchor_api_ids=["role_detail_v1"],
                support_api_ids=["role_list_v1"],
                field_paths=[_make_identifier_path()],
            ),
        )

    assert exc_info.value.code == "planner_invalid_field_transfer"


def test_validator_rejects_missing_identifier_resolution_for_required_identifier_param() -> None:
    validator = GraphPlanValidator()
    plan = ApiQueryExecutionPlan(
        plan_id="dag_role_identifier_missing",
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
                params={},
                depends_on=["step_role_list"],
            ),
        ],
    )

    with pytest.raises(GraphPlanValidationError) as exc_info:
        validator.validate_plan(
            plan=plan,
            step_entries=_make_step_entries(),
            subgraph_result=ApiCatalogSubgraphResult(
                anchor_api_ids=["role_detail_v1"],
                support_api_ids=["role_list_v1"],
                field_paths=[_make_identifier_path()],
            ),
        )

    assert exc_info.value.code == "planner_missing_identifier_resolution"


def test_validator_rejects_graph_degraded_for_bound_dependency_chain() -> None:
    validator = GraphPlanValidator()
    plan = _make_dependency_plan(binding_expression="$[step_role_list.data][*].roleId")

    with pytest.raises(GraphPlanValidationError) as exc_info:
        validator.validate_plan(
            plan=plan,
            step_entries=_make_step_entries(),
            subgraph_result=ApiCatalogSubgraphResult(
                anchor_api_ids=["role_detail_v1"],
                graph_degraded=True,
                degraded_reason="neo4j_unavailable",
            ),
        )

    assert exc_info.value.code == "planner_graph_degraded_forbidden"


def test_validator_marks_array_to_scalar_transfer_as_wait_select_compatible_cardinality_mismatch() -> None:
    validator = GraphPlanValidator()
    plan = _make_dependency_plan(binding_expression="$[step_role_list.data][*].roleId")

    with pytest.raises(GraphPlanValidationError) as exc_info:
        validator.validate_plan(
            plan=plan,
            step_entries=_make_step_entries(),
            subgraph_result=ApiCatalogSubgraphResult(
                anchor_api_ids=["role_detail_v1"],
                support_api_ids=["role_list_v1"],
                field_paths=[_make_identifier_path()],
            ),
        )

    assert exc_info.value.code == "planner_cardinality_mismatch"
    assert exc_info.value.metadata["pause_type"] == "WAIT_SELECT"
    assert exc_info.value.metadata["selection_mode"] == "single"
    assert exc_info.value.metadata["source_step_id"] == "step_role_list"
    assert exc_info.value.metadata["target_step_id"] == "step_role_detail"


def test_validator_accepts_exact_graph_path_when_array_cardinality_is_aligned() -> None:
    validator = GraphPlanValidator()
    step_entries = {
        "step_role_list": _make_entry(
            entry_id="role_list_v1",
            path="/system/employee/sys-role/list",
            method="GET",
            response_data_path="data.records",
        ),
        "step_role_stats": _make_entry(
            entry_id="role_stats_v1",
            path="/system/employee/sys-role/stats",
            method="POST",
            required=["roleIds"],
        ),
    }
    plan = ApiQueryExecutionPlan(
        plan_id="dag_role_stats",
        steps=[
            ApiQueryPlanStep(
                step_id="step_role_list",
                api_id="role_list_v1",
                api_path="/system/employee/sys-role/list",
                params={"pageNo": 1},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_role_stats",
                api_id="role_stats_v1",
                api_path="/system/employee/sys-role/stats",
                params={"roleIds": "$[step_role_list.data][*].roleId"},
                depends_on=["step_role_list"],
            ),
        ],
    )

    validator.validate_plan(
        plan=plan,
        step_entries=step_entries,
        subgraph_result=ApiCatalogSubgraphResult(
            anchor_api_ids=["role_stats_v1"],
            support_api_ids=["role_list_v1"],
            field_paths=[
                GraphFieldPath(
                    consumer_api_id="role_stats_v1",
                    producer_api_id="role_list_v1",
                    semantic_key="Role.id",
                    source_extract_path="data.records[].roleId",
                    target_inject_path="body.roleIds",
                    is_identifier=True,
                    source_array_mode=True,
                    target_array_mode=True,
                )
            ],
        ),
    )
