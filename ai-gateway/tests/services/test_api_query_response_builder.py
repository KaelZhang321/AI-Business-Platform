from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryPatchTrigger,
    ApiQueryResponseMode,
    ApiQueryPlanStep,
)
from app.services.api_catalog.dag_executor import DagStepExecutionRecord
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogPaginationHint, ParamSchema
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_state import ApiQueryRuntimeContext, ApiQueryState
from app.services.dynamic_ui_service import UISpecBuildResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.ui_spec_guard import UISpecValidationError, UISpecValidationResult


@dataclass(slots=True)
class FakeDynamicUIService:
    """测试专用第五阶段替身。"""

    result: UISpecBuildResult

    async def generate_ui_spec_result(self, **_: object) -> UISpecBuildResult:
        return self.result


class FakeRegistrySource:
    """测试专用目录源替身。"""

    async def get_entry_by_id(self, _: str):
        return None


def _build_flat_spec() -> dict[str, object]:
    """构造最小 flat spec。"""

    return {
        "root": "page",
        "state": {},
        "elements": {
            "page": {
                "id": "page",
                "type": "PlannerCard",
                "props": {"title": "客户列表"},
                "children": ["report-table"],
            },
            "report-table": {
                "id": "report-table",
                "type": "PlannerTable",
                "props": {
                    "dataSource": [],
                    "pagination": {"currentPage": 1, "pageSize": 20, "total": 1},
                },
            },
        },
    }


def _build_test_entry() -> ApiCatalogEntry:
    """构造查询安全列表接口。"""

    return ApiCatalogEntry(
        id="customer_list",
        description="客户列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/customer/list",
        param_schema=ParamSchema(
            properties={
                "ownerId": {"type": "string", "title": "负责人"},
                "pageNum": {"type": "integer", "title": "页码"},
                "pageSize": {"type": "integer", "title": "分页大小"},
            },
            required=["ownerId"],
        ),
        pagination_hint=ApiCatalogPaginationHint(
            enabled=True,
            page_param="pageNum",
            page_size_param="pageSize",
            mutation_target="report-table.props.dataSource",
        ),
    )


def _build_test_plan(step_id: str) -> ApiQueryExecutionPlan:
    """构造单步执行计划。"""

    return ApiQueryExecutionPlan(
        plan_id="plan_001",
        steps=[
            ApiQueryPlanStep(
                step_id=step_id,
                api_id=None,
                api_path="/api/customer/list",
                params={"ownerId": "E001", "pageNum": 1, "pageSize": 20},
                depends_on=[],
            )
        ],
    )


def _build_execution_record() -> tuple[str, ApiQueryExecutionPlan, DagStepExecutionRecord]:
    """构造单步执行记录。"""

    entry = _build_test_entry()
    step_id = f"step_{entry.id}"
    plan = _build_test_plan(step_id)
    record = DagStepExecutionRecord(
        step=plan.steps[0],
        entry=entry,
        resolved_params={"ownerId": "E001", "pageNum": 1, "pageSize": 20},
        execution_result=ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SUCCESS,
            data=[{"id": "27", "name": "测试客户"}],
            total=1,
            trace_id="trace-001",
            meta={},
        ),
    )
    return step_id, plan, record


def _build_builder(result: UISpecBuildResult) -> ApiQueryResponseBuilder:
    """构造待测 response builder。"""

    return ApiQueryResponseBuilder(
        dynamic_ui=FakeDynamicUIService(result=result),
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=FakeRegistrySource(),
    )


@pytest.mark.asyncio
async def test_build_execution_response_returns_full_spec() -> None:
    """成功执行时应返回完整响应，并把状态回写到 control state。"""

    step_id, plan, record = _build_execution_record()
    builder = _build_builder(UISpecBuildResult(spec=_build_flat_spec(), frozen=False))
    state: ApiQueryState = {
        "request_mode": "nl",
        "query_text": "查询测试客户",
        "trace_id": "trace-001",
        "interaction_id": None,
        "conversation_id": None,
        "plan": plan,
    }
    response = await builder.build_execution_response(
        state=state,
        runtime_context=ApiQueryRuntimeContext(
            step_entries={step_id: record.entry},
            log_prefix="api_query[trace=trace-001]",
        ),
        execution_state={
            "plan": plan,
            "trace_id": "trace-001",
            "records_by_step_id": {step_id: record},
            "execution_order": [step_id],
            "errors": [],
            "aggregate_status": None,
        },
        query_domains_hint=["crm"],
        business_intent_codes=["none"],
        response_mode=ApiQueryResponseMode.FULL_SPEC,
        patch_context=None,
    )

    assert response.trace_id == "trace-001"
    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert response.execution_plan is not None
    assert response.execution_plan.steps[0].api_id == "customer_list"
    assert response.ui_runtime is not None
    assert response.ui_runtime.list.enabled is True
    assert response.ui_runtime.list.param_source == "queryParams"
    assert response.ui_runtime.ui_actions
    assert response.ui_spec == _build_flat_spec()
    assert state["execution_status"] == ApiQueryExecutionStatus.SUCCESS
    assert state["response"] == response


@pytest.mark.asyncio
async def test_stage2_degrade_response_returns_skipped_notice() -> None:
    """第二阶段降级应返回稳定 SKIPPED 响应，而不是抛裸错误。"""

    builder = _build_builder(UISpecBuildResult(spec=_build_flat_spec(), frozen=False))
    state: ApiQueryState = {
        "request_mode": "nl",
        "query_text": "查一下未知对象",
        "trace_id": "trace-stage2",
        "interaction_id": "interaction-001",
        "conversation_id": "conversation-001",
    }

    response = await builder.build_stage2_degrade_response(
        state=state,
        title="未识别到可用业务域",
        message="抱歉，我没有完全理解您的意图。",
        error_code="routing_failed",
        query_domains=["crm"],
        business_intent_codes=["none"],
        reasoning="未命中任何开放域",
    )

    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error == "抱歉，我没有完全理解您的意图。"
    assert response.ui_runtime is not None
    assert any(action.code == "refresh" for action in response.ui_runtime.ui_actions)
    assert state["error_code"] == "routing_failed"
    assert state["degrade_reason"] == "抱歉，我没有完全理解您的意图。"


@pytest.mark.asyncio
async def test_build_execution_response_clears_runtime_when_ui_is_frozen() -> None:
    """执行成功但 UI Guard 冻结时，必须主动清空交互能力。"""

    step_id, plan, record = _build_execution_record()
    frozen_result = UISpecBuildResult(
        spec=_build_flat_spec(),
        validation=UISpecValidationResult(
            errors=[
                UISpecValidationError(
                    code="action_missing",
                    path="$.elements.page",
                    message="缺少动作定义",
                )
            ]
        ),
        frozen=True,
    )
    builder = _build_builder(frozen_result)
    state: ApiQueryState = {
        "request_mode": "direct",
        "query_text": "direct customer_list",
        "trace_id": "trace-frozen",
        "interaction_id": None,
        "conversation_id": None,
        "plan": plan,
    }

    response = await builder.build_execution_response(
        state=state,
        runtime_context=ApiQueryRuntimeContext(
            step_entries={step_id: record.entry},
            log_prefix="api_query[trace=trace-frozen]",
        ),
        execution_state={
            "plan": plan,
            "trace_id": "trace-frozen",
            "records_by_step_id": {step_id: record},
            "execution_order": [step_id],
            "errors": [],
            "aggregate_status": None,
        },
        query_domains_hint=["crm"],
        business_intent_codes=["none"],
        response_mode=ApiQueryResponseMode.FULL_SPEC,
        patch_context=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert response.ui_runtime is not None
    assert response.ui_runtime.ui_actions == []
    assert response.ui_runtime.list.enabled is False
    assert response.ui_runtime.detail.enabled is False
    assert response.ui_runtime.form.enabled is False
