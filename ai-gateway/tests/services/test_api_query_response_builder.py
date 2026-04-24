from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryPlanStep,
)
from app.services.api_catalog.dag_executor import DagStepExecutionRecord
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogPaginationHint, ParamSchema
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_state import ApiQueryRuntimeContext, ApiQueryState
from app.services.dynamic_ui_service import DynamicUIService, UISpecBuildResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.ui_spec_guard import UISpecValidationError, UISpecValidationResult
from app.core.config import settings


@dataclass(slots=True)
class FakeDynamicUIService:
    """测试专用第五阶段替身。"""

    result: UISpecBuildResult

    async def generate_ui_spec_result(self, **_: object) -> UISpecBuildResult:
        return self.result


@dataclass(slots=True)
class CaptureDynamicUIService:
    """可捕获 generate_ui_spec_result 入参的测试替身。"""

    result: UISpecBuildResult
    captured_data: Any = None
    captured_context: dict[str, Any] | None = None

    async def generate_ui_spec_result(self, **kwargs: object) -> UISpecBuildResult:
        self.captured_data = kwargs.get("data")
        context = kwargs.get("context")
        self.captured_context = context if isinstance(context, dict) else None
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
    dynamic_ui = CaptureDynamicUIService(result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False))
    builder = ApiQueryResponseBuilder(
        dynamic_ui=dynamic_ui,
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=FakeRegistrySource(),
    )
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

    dynamic_ui = CaptureDynamicUIService(result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False))
    builder = ApiQueryResponseBuilder(
        dynamic_ui=dynamic_ui,
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=FakeRegistrySource(),
    )
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
async def test_build_mutation_form_response_exposes_full_schema_except_audit_time_fields() -> None:
    """mutation form 应按 request_schema 全量展示，但隐藏系统时间字段。"""

    builder = ApiQueryResponseBuilder(
        dynamic_ui=DynamicUIService(catalog_service=UICatalogService()),
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=FakeRegistrySource(),
    )
    entry = ApiCatalogEntry(
        id="employee_update",
        description="修改员工信息",
        domain="iam",
        operation_safety="mutation",
        method="POST",
        path="/api/v1/employees/update",
        param_schema=ParamSchema(
            properties={
                "id": {"type": "string", "title": "员工ID"},
                "email": {"type": "string", "title": "邮箱"},
                "realName": {"type": "string", "title": "姓名"},
                "mobile": {"type": "string", "title": "手机号"},
                "createTime": {"type": "string", "title": "创建时间"},
                "updateTime": {"type": "string", "title": "更新时间"},
                "deleteTime": {"type": "string", "title": "删除时间"},
            },
            required=["id", "email", "realName"],
        ),
    )
    state: ApiQueryState = {
        "request_mode": "nl",
        "query_text": "修改员工8058的邮箱为437462373467289@qq.com",
        "trace_id": "trace-mutation-full-fields",
    }

    response = await builder.build_mutation_form_response(
        state=state,
        entry=entry,
        pre_fill_params={"id": "8058", "email": "437462373467289@qq.com"},
        business_intent_code="saveToServer",
        query_domains_hint=["iam"],
    )

    field_names = [field.submit_key for field in response.ui_runtime.form.fields]
    assert field_names == ["id", "email", "realName", "mobile"]
    assert "createTime" not in field_names
    assert "updateTime" not in field_names
    assert "deleteTime" not in field_names

    elements = response.ui_spec["elements"]
    assert elements["form_field_1"]["props"]["required"] is True
    assert elements["form_field_2"]["props"]["required"] is True
    assert elements["form_field_3"]["props"]["required"] is True
    assert elements["form_field_4"]["props"]["required"] is False


@pytest.mark.asyncio
async def test_build_mutation_form_response_hides_id_for_create_style_queries() -> None:
    """新增类 mutation 表单应隐藏服务端生成的主键字段。"""

    builder = ApiQueryResponseBuilder(
        dynamic_ui=DynamicUIService(catalog_service=UICatalogService()),
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=FakeRegistrySource(),
    )
    entry = ApiCatalogEntry(
        id="role_create",
        description="新增角色",
        domain="iam",
        operation_safety="mutation",
        method="POST",
        path="/api/v1/roles/create",
        param_schema=ParamSchema(
            properties={
                "id": {"type": "string", "title": "ID"},
                "roleName": {"type": "string", "title": "角色名称"},
                "roleCode": {"type": "string", "title": "角色编码"},
                "createTime": {"type": "string", "title": "创建时间"},
                "updateTime": {"type": "string", "title": "更新时间"},
            },
            required=["roleName", "roleCode"],
        ),
    )
    state: ApiQueryState = {
        "request_mode": "nl",
        "query_text": "新增一个健管师角色",
        "trace_id": "trace-create-role-form",
    }

    response = await builder.build_mutation_form_response(
        state=state,
        entry=entry,
        pre_fill_params={},
        business_intent_code="saveToServer",
        query_domains_hint=["iam"],
    )

    field_names = [field.submit_key for field in response.ui_runtime.form.fields]
    assert field_names == ["roleName", "roleCode"]
    assert "id" not in field_names
    assert "createTime" not in field_names
    assert "updateTime" not in field_names
    assert response.ui_spec["state"]["form"]["roleName"] == "健管师"
    assert response.execution_plan.steps[0].params["roleName"] == "健管师"


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
        "request_mode": "nl",
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
    )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert response.ui_runtime is not None
    assert response.ui_runtime.ui_actions == []
    assert response.ui_runtime.list.enabled is False
    assert response.ui_runtime.detail.enabled is False
    assert response.ui_runtime.form.enabled is False


@pytest.mark.asyncio
async def test_build_execution_response_multi_step_defaults_to_terminal_result(monkeypatch) -> None:
    """多步骤查询默认应返回终态业务数据而非步骤汇总。"""

    customer_entry = ApiCatalogEntry(
        id="customer_list",
        description="客户列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/customer/list",
        param_schema=ParamSchema(
            properties={"ownerId": {"type": "string"}},
            required=["ownerId"],
        ),
    )
    order_entry = ApiCatalogEntry(
        id="order_stats",
        description="订单统计",
        domain="erp",
        operation_safety="query",
        method="GET",
        path="/api/order/stats",
        param_schema=ParamSchema(
            properties={"customerIds": {"type": "array"}},
            required=["customerIds"],
        ),
    )
    plan = ApiQueryExecutionPlan(
        plan_id="plan_terminal_001",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_id="customer_list",
                api_path=customer_entry.path,
                params={"ownerId": "E001"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_orders",
                api_id="order_stats",
                api_path=order_entry.path,
                params={"customerIds": "$[step_customers.data][*].id"},
                depends_on=["step_customers"],
            ),
        ],
    )
    records = {
        "step_customers": DagStepExecutionRecord(
            step=plan.steps[0],
            entry=customer_entry,
            resolved_params={"ownerId": "E001"},
            execution_result=ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"id": "C001", "name": "张三"}],
                total=1,
                trace_id="trace-terminal",
            ),
        ),
        "step_orders": DagStepExecutionRecord(
            step=plan.steps[1],
            entry=order_entry,
            resolved_params={"customerIds": ["C001"]},
            execution_result=ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "orderCount": 3}],
                total=1,
                trace_id="trace-terminal",
            ),
        ),
    }
    dynamic_ui = CaptureDynamicUIService(result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False))
    builder = ApiQueryResponseBuilder(
        dynamic_ui=dynamic_ui,
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=FakeRegistrySource(),
    )
    state: ApiQueryState = {
        "request_mode": "nl",
        "query_text": "查客户订单",
        "trace_id": "trace-terminal",
        "interaction_id": None,
        "conversation_id": None,
        "plan": plan,
    }

    response = await builder.build_execution_response(
        state=state,
        runtime_context=ApiQueryRuntimeContext(
            step_entries={"step_customers": customer_entry, "step_orders": order_entry},
            log_prefix="api_query[trace=trace-terminal]",
        ),
        execution_state={
            "plan": plan,
            "trace_id": "trace-terminal",
            "records_by_step_id": records,
            "execution_order": ["step_customers", "step_orders"],
            "errors": [],
            "aggregate_status": None,
        },
        query_domains_hint=["crm", "erp"],
        business_intent_codes=["none"],
    )

    assert dynamic_ui.captured_data == [{"customerId": "C001", "orderCount": 3}]
    assert dynamic_ui.captured_context is not None
    assert dynamic_ui.captured_context["query_render_mode"] == "table"
    assert response.ui_runtime is not None
    assert response.ui_runtime.list.enabled is True
    assert response.ui_runtime.list.api_id == "order_stats"


@pytest.mark.asyncio
async def test_build_execution_response_multi_step_can_use_summary_policy(monkeypatch) -> None:
    """多步骤策略切到 summary_table 时应回退步骤汇总表。"""

    monkeypatch.setattr(settings, "api_query_multi_step_render_policy", "summary_table")
    customer_entry = ApiCatalogEntry(
        id="customer_list",
        description="客户列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/customer/list",
        param_schema=ParamSchema(
            properties={"ownerId": {"type": "string"}},
            required=["ownerId"],
        ),
    )
    order_entry = ApiCatalogEntry(
        id="order_stats",
        description="订单统计",
        domain="erp",
        operation_safety="query",
        method="GET",
        path="/api/order/stats",
        param_schema=ParamSchema(
            properties={"customerIds": {"type": "array"}},
            required=["customerIds"],
        ),
    )
    plan = ApiQueryExecutionPlan(
        plan_id="plan_summary_001",
        steps=[
            ApiQueryPlanStep(
                step_id="step_customers",
                api_id="customer_list",
                api_path=customer_entry.path,
                params={"ownerId": "E001"},
                depends_on=[],
            ),
            ApiQueryPlanStep(
                step_id="step_orders",
                api_id="order_stats",
                api_path=order_entry.path,
                params={"customerIds": "$[step_customers.data][*].id"},
                depends_on=["step_customers"],
            ),
        ],
    )
    records = {
        "step_customers": DagStepExecutionRecord(
            step=plan.steps[0],
            entry=customer_entry,
            resolved_params={"ownerId": "E001"},
            execution_result=ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"id": "C001", "name": "张三"}],
                total=1,
                trace_id="trace-summary",
            ),
        ),
        "step_orders": DagStepExecutionRecord(
            step=plan.steps[1],
            entry=order_entry,
            resolved_params={"customerIds": ["C001"]},
            execution_result=ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "orderCount": 3}],
                total=1,
                trace_id="trace-summary",
            ),
        ),
    }
    dynamic_ui = CaptureDynamicUIService(result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False))
    builder = ApiQueryResponseBuilder(
        dynamic_ui=dynamic_ui,
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=FakeRegistrySource(),
    )
    state: ApiQueryState = {
        "request_mode": "nl",
        "query_text": "查客户订单",
        "trace_id": "trace-summary",
        "interaction_id": None,
        "conversation_id": None,
        "plan": plan,
    }

    await builder.build_execution_response(
        state=state,
        runtime_context=ApiQueryRuntimeContext(
            step_entries={"step_customers": customer_entry, "step_orders": order_entry},
            log_prefix="api_query[trace=trace-summary]",
        ),
        execution_state={
            "plan": plan,
            "trace_id": "trace-summary",
            "records_by_step_id": records,
            "execution_order": ["step_customers", "step_orders"],
            "errors": [],
            "aggregate_status": None,
        },
        query_domains_hint=["crm", "erp"],
        business_intent_codes=["none"],
    )

    assert dynamic_ui.captured_data[0]["stepId"] == "step_customers"
    assert dynamic_ui.captured_context is not None
    assert dynamic_ui.captured_context["query_render_mode"] == "summary_table"
