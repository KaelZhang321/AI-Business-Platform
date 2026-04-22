from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.schemas import (
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryRoutingResult,
    ApiQueryRequest,
)
from app.services.api_catalog.graph_models import ApiCatalogSubgraphResult, GraphFieldPath
from app.services.api_catalog.dag_planner import DagPlanValidationError
from app.services.api_catalog.schema import (
    ApiCatalogDetailHint,
    ApiCatalogEntry,
    ApiCatalogPaginationHint,
    ApiCatalogPredecessorParamBinding,
    ApiCatalogPredecessorSpec,
    ApiCatalogSearchResult,
    ApiCatalogTemplateHint,
)
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_workflow import ApiQueryWorkflow
from app.services.dynamic_ui_service import DynamicUIService, UISpecBuildResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.ui_spec_guard import UISpecValidationError, UISpecValidationResult


class StubRetriever:
    def __init__(self, entries: list[ApiCatalogEntry], *, subgraph_result: ApiCatalogSubgraphResult | None = None) -> None:
        self._entries = entries
        self._subgraph_result = subgraph_result
        self.calls = 0
        self.trace_ids: list[str] = []

    async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
        self.calls += 1
        trace_id = kwargs.get("trace_id")
        if trace_id is not None:
            self.trace_ids.append(trace_id)
        return [ApiCatalogSearchResult(entry=entry, score=0.9) for entry in self._entries]

    def get_subgraph_result(self, trace_id: str) -> ApiCatalogSubgraphResult | None:
        self.trace_ids.append(trace_id)
        return self._subgraph_result


class StubExtractor:
    def __init__(
        self,
        entry: ApiCatalogEntry,
        params: dict[str, object],
        *,
        business_intents: list[str] | None = None,
        route_status: str = "ok",
        route_error_code: str | None = None,
    ) -> None:
        self._entry = entry
        self._params = params
        self._business_intents = business_intents or ["none"]
        self._route_status = route_status
        self._route_error_code = route_error_code
        self.route_calls = 0
        self.extract_calls = 0

    async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
        self.route_calls += 1
        return ApiQueryRoutingResult(
            query_domains=[self._entry.domain] if self._route_status == "ok" else [],
            business_intents=list(self._business_intents),
            is_multi_domain=False,
            reasoning="stub route",
            route_status=self._route_status,
            route_error_code=self._route_error_code,
        )

    async def extract_routing_result(self, query: str, candidates, user_context: dict[str, object], **kwargs):
        self.extract_calls += 1
        return ApiQueryRoutingResult(
            selected_api_id=self._entry.id,
            query_domains=[self._entry.domain],
            business_intents=list(self._business_intents),
            params=dict(self._params),
        )


class StubExecutor:
    def __init__(self, result: ApiQueryExecutionResult) -> None:
        self._result = result
        self.calls = 0

    async def call(self, entry: ApiCatalogEntry, params: dict[str, object], user_token=None, trace_id=None, user_id=None):
        self.calls += 1
        return self._result.model_copy(update={"trace_id": trace_id or self._result.trace_id})


class StubPlanner:
    def __init__(self, *, step_entries: dict[str, ApiCatalogEntry] | None = None, validate_error: Exception | None = None):
        self._step_entries = step_entries or {}
        self._validate_error = validate_error
        self.validate_calls = 0
        self.build_calls = 0
        self.last_subgraph_result: ApiCatalogSubgraphResult | None = None
        self.last_trace_id: str | None = None
        self.last_predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]] | None = None

    async def build_plan(self, query, candidates, user_context, route_hint, predecessor_hints=None, *, trace_id=None):
        self.build_calls += 1
        self.last_predecessor_hints = predecessor_hints
        if not candidates:
            raise DagPlanValidationError("planner_candidates_empty", "no candidates")
        entry = candidates[0].entry
        from app.services.api_catalog.dag_planner import build_single_step_plan

        return build_single_step_plan(
            entry,
            {"customerId": "C001"},
            step_id=f"step_{entry.id}",
            plan_id=f"dag_{(trace_id or 'trace')[:8]}",
        )

    def validate_plan(self, plan, candidates, predecessor_hints=None, *, subgraph_result=None, trace_id=None):
        self.validate_calls += 1
        self.last_subgraph_result = subgraph_result
        self.last_trace_id = trace_id
        self.last_predecessor_hints = predecessor_hints
        if self._validate_error is not None:
            raise self._validate_error
        return dict(self._step_entries)


class PassThroughPlanner:
    """保持 workflow 生成的执行计划不变，仅执行基础校验。"""

    def __init__(self, entry_by_step_id: dict[str, ApiCatalogEntry] | None = None) -> None:
        self._entry_by_step_id = entry_by_step_id or {}
        self.validate_calls = 0
        self.build_calls = 0

    async def build_plan(  # pragma: no cover
        self,
        query,
        candidates,
        user_context,
        route_hint,
        predecessor_hints=None,
        *,
        trace_id=None,
    ):
        self.build_calls += 1
        raise AssertionError("single-candidate path should not call planner.build_plan")

    def validate_plan(self, plan, candidates, predecessor_hints=None, *, subgraph_result=None, trace_id=None):
        self.validate_calls += 1
        return {
            step.step_id: self._entry_by_step_id.get(step.step_id) or next(
                candidate.entry for candidate in candidates if candidate.entry.id == (step.api_id or "")
            )
            for step in plan.steps
        }


class StubRegistrySource:
    def __init__(self, entry: ApiCatalogEntry | list[ApiCatalogEntry] | None) -> None:
        self._entry = entry
        self.calls = 0

    async def get_entry_by_id(self, api_id: str):
        self.calls += 1
        if isinstance(self._entry, list):
            for entry in self._entry:
                if entry.id == api_id:
                    return entry
            return None
        return self._entry

    async def load_entries(self):
        self.calls += 1
        if isinstance(self._entry, list):
            return list(self._entry)
        if self._entry is None:
            return []
        return [self._entry]


def _build_predecessor_target_entry_with_source_path(source_path: str) -> ApiCatalogEntry:
    """构造包含前置依赖的目标接口，便于复用路径兼容性测试。"""

    return ApiCatalogEntry(
        id="stored_plan_v1",
        description="储值方案概览",
        domain="oms",
        method="GET",
        path="/leczcore-data-manage/dwCustomerArchive/planAssetOverview",
        status="active",
        operation_safety="query",
        param_schema={
            "type": "object",
            "properties": {"encryptedIdCard": {"type": "string", "title": "身份证号"}},
            "required": ["encryptedIdCard"],
        },
        predecessors=[
            ApiCatalogPredecessorSpec(
                predecessor_api_id="customer_info_v1",
                required=True,
                order=1,
                param_bindings=[
                    ApiCatalogPredecessorParamBinding(
                        target_param="encryptedIdCard",
                        source_path=source_path,
                        select_mode="all",
                    )
                ],
            )
        ],
    )


@dataclass(slots=True)
class FakeDynamicUI:
    result: UISpecBuildResult

    async def generate_ui_spec_result(self, **_: object) -> UISpecBuildResult:
        return self.result


def _build_entry(*, entry_id: str = "customer_list") -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id=entry_id,
        description="客户列表",
        domain="crm",
        method="GET",
        path="/api/customer/list",
        status="active",
        operation_safety="query",
        param_schema={
            "type": "object",
            "properties": {
                "customerId": {"type": "string", "title": "客户ID"},
                "pageNum": {"type": "integer", "title": "页码"},
                "pageSize": {"type": "integer", "title": "分页大小"},
            },
            "required": ["customerId"],
        },
        detail_hint=ApiCatalogDetailHint(enabled=True, identifier_field="customerId", query_param="customerId"),
        pagination_hint=ApiCatalogPaginationHint(
            enabled=True,
            page_param="pageNum",
            page_size_param="pageSize",
            mutation_target="report-table.props.dataSource",
        ),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )


def _build_flat_spec() -> dict[str, object]:
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
                    "dataSource": [{"customerId": "C001", "customerName": "张三"}],
                    "pagination": {"currentPage": 1, "pageSize": 20, "total": 1},
                },
            },
        },
    }


def _build_role_delete_entry() -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id="role_delete",
        description="删除角色",
        domain="iam",
        method="POST",
        path="/system/employee/sys-role/delete",
        status="active",
        operation_safety="mutation",
        param_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "roleName": {"type": "string"},
            },
            "required": [],
        },
        detail_hint=ApiCatalogDetailHint(enabled=False),
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )


def _build_role_list_entry() -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id="role_list",
        description="角色列表",
        domain="iam",
        method="POST",
        path="/system/employee/sys-role/list",
        status="active",
        operation_safety="list",
        param_schema={
            "type": "object",
            "properties": {
                "roleName": {"type": "string", "title": "角色名称"},
                "pageNo": {"type": "integer", "title": "页码"},
                "pageSize": {"type": "integer", "title": "分页大小"},
            },
            "required": [],
        },
        detail_hint=ApiCatalogDetailHint(enabled=False),
        pagination_hint=ApiCatalogPaginationHint(enabled=True, page_param="pageNo", page_size_param="pageSize"),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )


def _build_workflow(
    *,
    retriever: StubRetriever,
    extractor: StubExtractor,
    executor: StubExecutor,
    planner: StubPlanner,
    registry_source: StubRegistrySource,
    ui_result: UISpecBuildResult,
    dynamic_ui_override=None,
) -> ApiQueryWorkflow:
    dynamic_ui = dynamic_ui_override or FakeDynamicUI(result=ui_result)
    response_builder = ApiQueryResponseBuilder(
        dynamic_ui=dynamic_ui,
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=registry_source,
    )
    return ApiQueryWorkflow(
        services_getter=lambda: (retriever, extractor, executor, dynamic_ui, UISnapshotService()),
        planner_getter=lambda: planner,
        response_builder_getter=lambda: response_builder,
        registry_source_getter=lambda: registry_source,
        allowed_business_intent_codes_getter=lambda: {"none", "saveToServer", "deleteCustomer"},
    )


@pytest.mark.asyncio
async def test_workflow_passes_stage2_subgraph_into_stage3_validation() -> None:
    entry = _build_entry()
    subgraph = ApiCatalogSubgraphResult(
        anchor_api_ids=[entry.id],
        support_api_ids=["customer_detail"],
        field_paths=[
            GraphFieldPath(
                consumer_api_id=entry.id,
                producer_api_id="customer_detail",
                semantic_key="Customer.id",
                source_extract_path="data.customerId",
                target_inject_path="queryParams.customerId",
                is_identifier=True,
                source_array_mode=False,
                target_array_mode=False,
            )
        ],
    )
    retriever = StubRetriever([entry], subgraph_result=subgraph)
    extractor = StubExtractor(entry, {"customerId": "C001"})
    executor = StubExecutor(
        ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SUCCESS,
            data=[{"customerId": "C001", "customerName": "张三"}],
            total=1,
        )
    )
    planner = StubPlanner(step_entries={f"step_{entry.id}": entry})
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(entry),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询客户列表"}),
        trace_id="trace-subgraph-pass-through",
        interaction_id="interaction-subgraph-pass-through",
        conversation_id="conversation-subgraph-pass-through",
        user_context={},
        user_token="Bearer test-token",
    )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert planner.last_subgraph_result == subgraph
    assert planner.last_trace_id == "trace-subgraph-pass-through"


@pytest.mark.asyncio
async def test_workflow_stage3_does_not_degrade_when_graph_degraded_and_validation_flag_disabled() -> None:
    """图校验开关关闭时，Stage3 不应因 graph_degraded 被保守拦截。"""

    entry = _build_entry()
    subgraph = ApiCatalogSubgraphResult(
        anchor_api_ids=[entry.id],
        graph_degraded=True,
        degraded_reason="graph_disabled",
    )
    retriever = StubRetriever([entry], subgraph_result=subgraph)
    extractor = StubExtractor(entry, {"customerId": "C001"})
    executor = StubExecutor(
        ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SUCCESS,
            data=[{"customerId": "C001", "customerName": "张三"}],
            total=1,
        )
    )
    planner = StubPlanner(step_entries={f"step_{entry.id}": entry})
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(entry),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    from app.services.api_catalog import dag_planner as dag_planner_module

    original_enabled = dag_planner_module.settings.api_catalog_graph_validation_enabled
    dag_planner_module.settings.api_catalog_graph_validation_enabled = False
    try:
        response = await workflow.run(
            ApiQueryRequest.model_validate({"query": "查询张三客户"}),
            trace_id="trace-stage3-graph-degraded-but-disabled",
            interaction_id=None,
            conversation_id=None,
            user_context={},
            user_token=None,
        )
    finally:
        dag_planner_module.settings.api_catalog_graph_validation_enabled = original_enabled

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert response.error is None


@pytest.mark.asyncio
async def test_workflow_runs_nl_path_and_returns_success() -> None:
    entry = _build_entry()
    retriever = StubRetriever([entry])
    extractor = StubExtractor(entry, {"customerId": "C001"}, business_intents=["none"])
    executor = StubExecutor(
        ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SUCCESS,
            data=[{"customerId": "C001", "customerName": "张三"}],
            total=1,
        )
    )
    planner = StubPlanner(step_entries={f"step_{entry.id}": entry})
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(entry),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询张三客户"}),
        trace_id="trace-nl-001",
        interaction_id=None,
        conversation_id=None,
        user_context={"userId": "U001"},
        user_token=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert response.ui_runtime is not None
    assert response.ui_runtime.list.enabled is True
    assert retriever.calls == 1
    assert extractor.route_calls == 1
    assert extractor.extract_calls == 1
    assert planner.validate_calls == 1


@pytest.mark.asyncio
async def test_workflow_logs_route_candidates_and_dag_summary(caplog) -> None:
    entry = _build_entry()
    retriever = StubRetriever([entry])
    extractor = StubExtractor(entry, {"customerId": "C001"}, business_intents=["query_business_data"])
    executor = StubExecutor(
        ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SUCCESS,
            data=[{"customerId": "C001", "customerName": "张三"}],
            total=1,
        )
    )
    planner = StubPlanner(step_entries={f"step_{entry.id}": entry})
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(entry),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    with caplog.at_level("INFO", logger="app.services.api_query_workflow"):
        response = await workflow.run(
            ApiQueryRequest.model_validate({"query": "查询张三客户"}),
            trace_id="trace-log-summary-001",
            interaction_id=None,
            conversation_id=None,
            user_context={"userId": "U001"},
            user_token=None,
        )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert "api_query route intent summary" in caplog.text
    assert "api_query retrieved candidates" in caplog.text
    assert "api_query planner dag summary" in caplog.text
    assert "query_business_data" in caplog.text
    assert entry.id in caplog.text
    assert f"dag_{'trace-lo'}" in caplog.text


@pytest.mark.asyncio
async def test_workflow_multi_candidate_passes_predecessor_hints_to_planner() -> None:
    predecessor_entry = ApiCatalogEntry(
        id="role_list_v1",
        description="角色列表",
        domain="iam",
        method="GET",
        path="/api/roles/list",
        status="active",
        operation_safety="query",
    )
    target_entry = ApiCatalogEntry(
        id="role_detail_v1",
        description="角色详情",
        domain="iam",
        method="GET",
        path="/api/roles/detail",
        status="active",
        operation_safety="query",
        param_schema={
            "type": "object",
            "properties": {"roleId": {"type": "string"}},
            "required": ["roleId"],
        },
        predecessors=[
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
        ],
    )

    retriever = StubRetriever([target_entry, predecessor_entry])
    extractor = StubExtractor(target_entry, {"roleId": "S1001"}, business_intents=["none"])
    executor = StubExecutor(
        ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SUCCESS,
            data=[{"roleId": "S1001", "roleName": "健管师"}],
            total=1,
        )
    )
    planner = StubPlanner(
        step_entries={
            "step_role_list_v1": predecessor_entry,
            "step_role_detail_v1": target_entry,
        }
    )

    async def build_plan_with_predecessor(
        query, candidates, user_context, route_hint, predecessor_hints=None, *, trace_id=None
    ):
        planner.build_calls += 1
        planner.last_predecessor_hints = predecessor_hints
        from app.models.schemas import ApiQueryExecutionPlan, ApiQueryPlanStep

        return ApiQueryExecutionPlan(
            plan_id=f"dag_{(trace_id or 'trace')[:8]}",
            steps=[
                ApiQueryPlanStep(
                    step_id="step_role_list_v1",
                    api_id="role_list_v1",
                    api_path="/api/roles/list",
                    params={},
                    depends_on=[],
                ),
                ApiQueryPlanStep(
                    step_id="step_role_detail_v1",
                    api_id="role_detail_v1",
                    api_path="/api/roles/detail",
                    params={"roleId": "$[step_role_list_v1.data][*].id"},
                    depends_on=["step_role_list_v1"],
                ),
            ],
        )

    planner.build_plan = build_plan_with_predecessor  # type: ignore[method-assign]
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource([target_entry, predecessor_entry]),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询健管师角色详情"}),
        trace_id="trace-predecessor-hints-001",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.PARTIAL_SUCCESS
    assert planner.build_calls == 1
    assert planner.last_predecessor_hints is not None
    hints = planner.last_predecessor_hints.get("role_detail_v1")
    assert hints is not None
    assert len(hints) == 1
    assert hints[0].predecessor_api_id == "role_list_v1"


@pytest.mark.asyncio
async def test_workflow_multi_candidate_missing_required_predecessor_degrades() -> None:
    target_entry = ApiCatalogEntry(
        id="role_detail_v1",
        description="角色详情",
        domain="iam",
        method="GET",
        path="/api/roles/detail",
        status="active",
        operation_safety="query",
        param_schema={
            "type": "object",
            "properties": {"roleId": {"type": "string"}},
            "required": ["roleId"],
        },
        predecessors=[
            ApiCatalogPredecessorSpec(
                predecessor_api_id="role_list_v1",
                required=True,
                order=1,
                param_bindings=[],
            )
        ],
    )
    another_entry = ApiCatalogEntry(
        id="role_summary_v1",
        description="角色汇总",
        domain="iam",
        method="GET",
        path="/api/roles/summary",
        status="active",
        operation_safety="query",
    )

    retriever = StubRetriever([target_entry, another_entry])
    extractor = StubExtractor(target_entry, {"roleId": "S1001"}, business_intents=["none"])
    executor = StubExecutor(ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data=[], total=0))
    planner = StubPlanner(step_entries={})
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource([target_entry, another_entry]),  # 不包含 required predecessor
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询健管师角色详情"}),
        trace_id="trace-missing-required-predecessor-001",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error == "我找到了相关接口，但当前还无法稳定生成可执行的数据流，请补充更明确的查询链路后重试。"
    assert planner.build_calls == 0


@pytest.mark.asyncio
async def test_workflow_stage2_failure_goes_to_unified_degrade_response() -> None:
    entry = _build_entry()
    retriever = StubRetriever([entry])
    extractor = StubExtractor(entry, {}, route_status="fallback", route_error_code="routing_failed")
    executor = StubExecutor(ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data=[], total=0))
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=StubPlanner(step_entries={}),
        registry_source=StubRegistrySource(entry),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查一下未知对象"}),
        trace_id="trace-stage2-001",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error == "抱歉，我没有完全理解您的意图，或系统中暂未开放相关查询能力，请尝试换种说法。"
    assert retriever.calls == 0
    assert executor.calls == 0


@pytest.mark.asyncio
async def test_workflow_stage3_validation_failure_goes_to_unified_degrade_response() -> None:
    entry = _build_entry()
    retriever = StubRetriever([entry])
    extractor = StubExtractor(entry, {"customerId": "C001"})
    executor = StubExecutor(ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data=[], total=0))
    planner = StubPlanner(
        step_entries={},
        validate_error=DagPlanValidationError("planner_validation_failed", "invalid dag"),
    )
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(entry),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询张三客户"}),
        trace_id="trace-stage3-001",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error == "系统生成的数据依赖图存在安全风险，已终止执行以保护业务系统。"
    assert executor.calls == 0


@pytest.mark.asyncio
async def test_workflow_frozen_ui_still_returns_response_from_unified_exit() -> None:
    entry = _build_entry()
    retriever = StubRetriever([entry])
    extractor = StubExtractor(entry, {"customerId": "C001"})
    executor = StubExecutor(
        ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SUCCESS,
            data=[{"customerId": "C001", "customerName": "张三"}],
            total=1,
        )
    )
    planner = StubPlanner(step_entries={f"step_{entry.id}": entry})
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(entry),
        ui_result=UISpecBuildResult(
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
        ),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询张三客户"}),
        trace_id="trace-frozen-001",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert response.ui_runtime is not None
    assert response.ui_runtime.ui_actions == []
    assert response.ui_runtime.list.enabled is False
    assert response.ui_runtime.detail.enabled is False


@pytest.mark.asyncio
async def test_workflow_mutation_single_candidate_returns_form_response() -> None:
    """NL 模式下单候选 mutation 接口应走表单快路，不触发执行器。"""

    mutation_entry = ApiCatalogEntry(
        id="employee_update",
        description="修改员工信息",
        domain="iam",
        method="POST",
        path="/api/v1/employees/update",
        status="active",
        operation_safety="mutation",
        param_schema={
            "type": "object",
            "properties": {
                "employeeId": {"type": "string", "title": "员工ID"},
                "email": {"type": "string", "title": "邮箱"},
            },
            "required": ["employeeId", "email"],
        },
        detail_hint=ApiCatalogDetailHint(enabled=False),
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )
    retriever = StubRetriever([mutation_entry])
    extractor = StubExtractor(
        mutation_entry,
        {"employeeId": "8058", "email": "437462373467289@qq.com"},
        business_intents=["saveToServer"],
    )
    executor = StubExecutor(ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data=[], total=0))
    planner = StubPlanner()

    flat_form_spec = {
        "root": "root",
        "state": {"form": {"employeeId": "8058", "email": "437462373467289@qq.com"}},
        "elements": {
            "root": {"type": "PlannerCard", "props": {"title": "确认修改：修改员工信息"}, "children": ["form_1"]},
            "form_1": {"type": "PlannerForm", "props": {}},
        },
    }
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(mutation_entry),
        ui_result=UISpecBuildResult(spec=flat_form_spec, frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "修改员工8058的邮箱为437462373467289@qq.com"}),
        trace_id="trace-mutation-001",
        interaction_id=None,
        conversation_id=None,
        user_context={"userId": "U001"},
        user_token=None,
    )

    # 走表单快路：不执行变更
    assert executor.calls == 0
    assert planner.build_calls == 0

    # 返回 SKIPPED 而非 ERROR 或 SUCCESS
    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error is None

    # 表单运行时契约
    assert response.ui_runtime is not None
    assert response.ui_runtime.form.enabled is True
    assert response.ui_runtime.form.api_id == "employee_update"
    assert response.ui_runtime.form.route_url.endswith("/ui-builder/runtime/endpoints/employee_update/invoke")
    assert response.ui_runtime.form.mode == "edit"
    assert response.ui_runtime.form.submit.confirm_required is True
    assert response.ui_runtime.form.submit.business_intent == "saveToServer"
    assert response.ui_spec is not None
    assert response.ui_spec["state"]["form"]["employeeId"] == "8058"
    assert response.ui_spec["state"]["form"]["email"] == "437462373467289@qq.com"

    # execution_plan 携带 mutation 步骤，供前端确认后直接调用业务系统
    assert response.execution_plan is not None
    assert response.execution_plan.steps[0].api_id == "employee_update"
    assert response.execution_plan.steps[0].params["employeeId"] == "8058"
    assert response.execution_plan.steps[0].params["email"] == "437462373467289@qq.com"

    # 表单字段包含两个必填字段
    field_names = {f.name for f in response.ui_runtime.form.fields}
    assert "员工ID" in field_names or "employeeId" in field_names


@pytest.mark.asyncio
async def test_workflow_multi_candidate_mutation_validate_plan_intercept() -> None:
    """多候选场景：validate_plan 拦截 planner_unsafe_api 后转为表单快路。

    模拟 Milvus 返回两个候选（一个 query 接口 + 一个 mutation 接口），
    LLM planner 选出 mutation 接口放入执行计划，validate_plan 抛出
    DagPlanValidationError(planner_unsafe_api)，workflow 应转为表单响应
    而非降级到错误 Notice。
    """

    query_entry = _build_entry(entry_id="employee_list")
    mutation_entry = ApiCatalogEntry(
        id="employee_update",
        description="修改员工信息",
        domain="iam",
        method="POST",
        path="/api/v1/employees/update",
        status="active",
        operation_safety="mutation",
        param_schema={
            "type": "object",
            "properties": {
                "employeeId": {"type": "string", "title": "员工ID"},
                "email": {"type": "string", "title": "邮箱"},
            },
            "required": ["employeeId", "email"],
        },
        detail_hint=ApiCatalogDetailHint(enabled=False),
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )

    retriever = StubRetriever([query_entry, mutation_entry])
    # extractor 的 extract_routing_result 会被 _try_build_mutation_form_context 调用
    extractor = StubExtractor(
        mutation_entry,
        {"employeeId": "8058", "email": "437462373467289@qq.com"},
        business_intents=["saveToServer"],
    )
    executor = StubExecutor(ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data=[], total=0))
    # StubPlanner 在 validate_plan 时抛出 planner_unsafe_api
    planner = StubPlanner(
        step_entries={},
        validate_error=DagPlanValidationError("planner_unsafe_api", f"Planner 引入了非查询语义接口: {mutation_entry.id}"),
    )

    flat_form_spec = {
        "root": "root",
        "state": {},
        "elements": {
            "root": {"type": "PlannerCard", "props": {"title": "确认修改：修改员工信息"}, "children": ["f"]},
            "f": {"type": "PlannerForm", "props": {}},
        },
    }
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(mutation_entry),
        ui_result=UISpecBuildResult(spec=flat_form_spec, frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "修改员工8058的邮箱为437462373467289@qq.com"}),
        trace_id="trace-multi-mutation-001",
        interaction_id=None,
        conversation_id=None,
        user_context={"userId": "U001"},
        user_token=None,
    )

    # 不应降级为错误 Notice
    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error is None

    # 走表单快路，执行器未调用
    assert executor.calls == 0

    # 表单契约正确
    assert response.ui_runtime is not None
    assert response.ui_runtime.form.enabled is True
    assert response.ui_runtime.form.api_id == "employee_update"
    assert response.ui_runtime.form.route_url.endswith("/ui-builder/runtime/endpoints/employee_update/invoke")
    assert response.ui_runtime.form.submit.confirm_required is True

    # execution_plan 包含 mutation 步骤
    assert response.execution_plan is not None
    assert response.execution_plan.steps[0].api_id == "employee_update"


@pytest.mark.asyncio
async def test_workflow_multi_candidate_write_intent_bypasses_planner_and_returns_mutation_form() -> None:
    """多候选写意图：唯一 mutation 候选时应在 build_plan 前直达表单快路。"""

    query_entry = _build_entry(entry_id="employee_list")
    mutation_entry = ApiCatalogEntry(
        id="employee_update",
        description="修改员工信息",
        domain="iam",
        method="POST",
        path="/api/v1/employees/update",
        status="active",
        operation_safety="mutation",
        param_schema={
            "type": "object",
            "properties": {
                "employeeId": {"type": "string", "title": "员工ID"},
                "email": {"type": "string", "title": "邮箱"},
            },
            "required": ["employeeId", "email"],
        },
        detail_hint=ApiCatalogDetailHint(enabled=False),
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )
    retriever = StubRetriever([query_entry, mutation_entry])
    extractor = StubExtractor(
        mutation_entry,
        {"employeeId": "8058", "email": "437462373467289@qq.com"},
        business_intents=["saveToServer"],
    )
    executor = StubExecutor(ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data=[], total=0))
    planner = StubPlanner(
        step_entries={},
        validate_error=DagPlanValidationError("planner_unsafe_api", f"Planner 引入了非查询语义接口: {mutation_entry.id}"),
    )

    flat_form_spec = {
        "root": "root",
        "state": {},
        "elements": {
            "root": {"type": "PlannerCard", "props": {"title": "确认修改：修改员工信息"}, "children": ["f"]},
            "f": {"type": "PlannerForm", "props": {}},
        },
    }
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(mutation_entry),
        ui_result=UISpecBuildResult(spec=flat_form_spec, frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "修改员工8058的邮箱为437462373467289@qq.com"}),
        trace_id="trace-multi-write-001",
        interaction_id=None,
        conversation_id=None,
        user_context={"userId": "U001"},
        user_token=None,
    )

    # build_plan 前已完成 mutation 收敛，不应再调用 planner.build_plan / validate_plan。
    assert planner.build_calls == 0
    assert planner.validate_calls == 0
    assert executor.calls == 0

    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error is None
    assert response.ui_runtime is not None
    assert response.ui_runtime.form.enabled is True
    assert response.ui_runtime.form.api_id == "employee_update"
    assert response.ui_runtime.form.route_url.endswith("/ui-builder/runtime/endpoints/employee_update/invoke")
    assert response.execution_plan is not None
    assert response.execution_plan.steps[0].api_id == "employee_update"


@pytest.mark.asyncio
async def test_workflow_multi_mutation_candidates_uses_selected_create_entry_for_form() -> None:
    """多 mutation 候选时，只要路由已选中创建接口，也必须直接返回创建表单。"""

    update_entry = ApiCatalogEntry(
        id="role_update",
        description="修改角色",
        domain="iam",
        method="POST",
        path="/api/v1/roles/update",
        status="active",
        operation_safety="mutation",
        param_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "title": "ID"},
                "roleName": {"type": "string", "title": "角色名称"},
            },
            "required": ["id", "roleName"],
        },
        detail_hint=ApiCatalogDetailHint(enabled=False),
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )
    create_entry = ApiCatalogEntry(
        id="role_create",
        description="新增角色",
        domain="iam",
        method="POST",
        path="/api/v1/roles/create",
        status="active",
        operation_safety="mutation",
        param_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "title": "ID"},
                "roleName": {"type": "string", "title": "角色名称"},
                "createTime": {"type": "string", "title": "创建时间"},
                "updateTime": {"type": "string", "title": "更新时间"},
            },
            "required": ["roleName"],
        },
        detail_hint=ApiCatalogDetailHint(enabled=False),
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )
    retriever = StubRetriever([update_entry, create_entry])
    extractor = StubExtractor(
        create_entry,
        {},
        business_intents=["saveToServer"],
    )
    executor = StubExecutor(ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data=[], total=0))
    planner = StubPlanner(
        step_entries={},
        validate_error=DagPlanValidationError("planner_unsafe_api", f"Planner 引入了非查询语义接口: {create_entry.id}"),
    )

    flat_form_spec = {
        "root": "root",
        "state": {},
        "elements": {
            "root": {"type": "PlannerCard", "props": {"title": "确认新增：新增角色"}, "children": ["f"]},
            "f": {"type": "PlannerForm", "props": {}},
        },
    }
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=planner,
        registry_source=StubRegistrySource(create_entry),
        ui_result=UISpecBuildResult(spec=flat_form_spec, frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "新增一个健管师角色"}),
        trace_id="trace-multi-create-001",
        interaction_id=None,
        conversation_id=None,
        user_context={"userId": "U001"},
        user_token=None,
    )

    assert planner.build_calls == 0
    assert planner.validate_calls == 0
    assert executor.calls == 0
    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error is None
    assert response.ui_runtime is not None
    assert response.ui_runtime.form.enabled is True
    assert response.ui_runtime.form.api_id == "role_create"
    field_names = [field.submit_key for field in response.ui_runtime.form.fields]
    assert field_names == ["roleName"]
    assert response.ui_runtime.form.fields[0].source_kind == "context"
    assert response.execution_plan is not None
    assert response.execution_plan.steps[0].api_id == "role_create"
    assert response.execution_plan.steps[0].params["roleName"] == "健管师"


@pytest.mark.asyncio
async def test_workflow_delete_role_returns_confirm_form_when_single_match() -> None:
    delete_entry = _build_role_delete_entry()
    retriever = StubRetriever([delete_entry])
    extractor = StubExtractor(
        delete_entry,
        {},
        business_intents=["deleteCustomer"],
    )
    executor = StubExecutor(ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data=[], total=0))
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,
        planner=StubPlanner(),
        registry_source=StubRegistrySource([delete_entry]),
        ui_result=UISpecBuildResult(spec={}, frozen=False),
        dynamic_ui_override=DynamicUIService(catalog_service=UICatalogService()),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "删除健管师角色"}),
        trace_id="trace-delete-confirm-001",
        interaction_id=None,
        conversation_id=None,
        user_context={"userId": "U001"},
        user_token=None,
    )

    assert executor.calls == 0
    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.error is None
    assert response.ui_runtime is not None
    assert response.ui_runtime.form.enabled is True
    assert response.ui_runtime.form.mode == "confirm"
    assert response.ui_runtime.form.api_id == "role_delete"
    assert response.execution_plan is not None
    assert response.execution_plan.steps[0].params == {"roleName": "健管师"}
    assert response.ui_spec["state"]["form"]["roleName"] == "健管师"
    submit = response.ui_spec["elements"]["form_submit"]
    assert submit["on"]["press"]["params"]["body"] == {"roleName": "健管师"}


@pytest.mark.asyncio
async def test_workflow_delete_role_returns_notice_when_missing() -> None:
    delete_entry = _build_role_delete_entry()
    list_entry = _build_role_list_entry()
    retriever = StubRetriever([delete_entry, list_entry])
    extractor = StubExtractor(
        delete_entry,
        {},
        business_intents=["deleteCustomer"],
    )

    class MissingDeletePreviewExecutor:
        def __init__(self) -> None:
            self.calls = 0

        async def call(self, entry: ApiCatalogEntry, params: dict[str, object], user_token=None, trace_id=None, user_id=None):
            self.calls += 1
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[],
                total=0,
                trace_id=trace_id,
            )

    executor = MissingDeletePreviewExecutor()
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,  # type: ignore[arg-type]
        planner=StubPlanner(),
        registry_source=StubRegistrySource([delete_entry, list_entry]),
        ui_result=UISpecBuildResult(spec={}, frozen=False),
        dynamic_ui_override=DynamicUIService(catalog_service=UICatalogService()),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "删除健管师角色"}),
        trace_id="trace-delete-missing-001",
        interaction_id=None,
        conversation_id=None,
        user_context={"userId": "U001"},
        user_token=None,
    )

    assert executor.calls == 1
    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_workflow_single_candidate_with_predecessor_builds_multi_step_plan() -> None:
    predecessor_entry = ApiCatalogEntry(
        id="role_list_v1",
        description="角色列表",
        domain="iam",
        method="GET",
        path="/api/roles/list",
        status="active",
        operation_safety="list",
    )
    target_entry = ApiCatalogEntry(
        id="role_detail_v1",
        description="角色详情",
        domain="iam",
        method="GET",
        path="/api/roles/detail",
        status="active",
        operation_safety="query",
        param_schema={
            "type": "object",
            "properties": {"roleId": {"type": "string", "title": "角色ID"}},
            "required": ["roleId"],
        },
        predecessors=[
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
        ],
    )

    class MixedExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def call(self, entry, params, user_token=None, trace_id=None, user_id=None):
            self.calls.append((entry.id, dict(params)))
            if entry.id == "role_list_v1":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"id": "S1001"}, {"id": "S1002"}],
                    total=2,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"roleId": params.get("roleId"), "roleName": "健管师"}],
                total=1,
                trace_id=trace_id,
            )

    retriever = StubRetriever([target_entry])
    extractor = StubExtractor(target_entry, {})
    executor = MixedExecutor()
    planner = PassThroughPlanner(
        entry_by_step_id={
            "step_role_list_v1": predecessor_entry,
            "step_role_detail_v1": target_entry,
        }
    )
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,  # type: ignore[arg-type]
        planner=planner,  # type: ignore[arg-type]
        registry_source=StubRegistrySource([target_entry, predecessor_entry]),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询健管师角色详情"}),
        trace_id="trace-predecessor-001",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert response.execution_plan is not None
    assert len(response.execution_plan.steps) == 2
    step_map = {step.step_id: step for step in response.execution_plan.steps}
    assert step_map["step_role_detail_v1"].depends_on == ["step_role_list_v1"]
    # select_mode=first 应转为单值绑定表达式（非 user_select 暂停）
    assert step_map["step_role_detail_v1"].params["roleId"] == "$[step_role_list_v1.data].id"
    assert [item[0] for item in executor.calls] == ["role_list_v1", "role_detail_v1"]


@pytest.mark.asyncio
async def test_workflow_user_select_wait_and_resume() -> None:
    predecessor_entry = ApiCatalogEntry(
        id="role_list_v1",
        description="角色列表",
        domain="iam",
        method="GET",
        path="/api/roles/list",
        status="active",
        operation_safety="list",
    )
    target_entry = ApiCatalogEntry(
        id="role_detail_v1",
        description="角色详情",
        domain="iam",
        method="GET",
        path="/api/roles/detail",
        status="active",
        operation_safety="query",
        param_schema={
            "type": "object",
            "properties": {"roleId": {"type": "string", "title": "角色ID"}},
            "required": ["roleId"],
        },
        predecessors=[
            ApiCatalogPredecessorSpec(
                predecessor_api_id="role_list_v1",
                required=True,
                order=1,
                param_bindings=[
                    ApiCatalogPredecessorParamBinding(
                        target_param="roleId",
                        source_path="$.data[*].id",
                        select_mode="user_select",
                    )
                ],
            )
        ],
    )

    class SelectExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def call(self, entry, params, user_token=None, trace_id=None, user_id=None):
            self.calls.append((entry.id, dict(params)))
            if entry.id == "role_list_v1":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"id": "S1001"}, {"id": "S1002"}],
                    total=2,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"roleId": params.get("roleId"), "roleName": "健管师"}],
                total=1,
                trace_id=trace_id,
            )

    retriever = StubRetriever([target_entry])
    extractor = StubExtractor(target_entry, {})
    executor = SelectExecutor()
    planner = PassThroughPlanner(
        entry_by_step_id={
            "step_role_list_v1": predecessor_entry,
            "step_role_detail_v1": target_entry,
        }
    )
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,  # type: ignore[arg-type]
        planner=planner,  # type: ignore[arg-type]
        registry_source=StubRegistrySource([target_entry, predecessor_entry]),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    wait_response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询健管师角色详情"}),
        trace_id="trace-user-select-wait",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )
    assert wait_response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert wait_response.error == "命中多个候选值，请先选择后继续。"
    # 首次仅执行前置接口，主接口因 WAIT_SELECT_REQUIRED 跳过
    assert [item[0] for item in executor.calls] == ["role_list_v1"]

    resume_response = await workflow.run(
        ApiQueryRequest.model_validate(
            {
                "query": "查询健管师角色详情",
                "selection_context": {"user_select": {"role_list_v1:roleId:id": "S1001"}},
            }
        ),
        trace_id="trace-user-select-resume",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )
    assert resume_response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert [item[0] for item in executor.calls][-2:] == ["role_list_v1", "role_detail_v1"]
    assert executor.calls[-1][1]["roleId"] == "S1001"
    assert resume_response.execution_plan is not None
    assert resume_response.error is None


@pytest.mark.asyncio
@pytest.mark.parametrize("source_path", ["$.idCard", "$.result.records[*].idCard"])
async def test_workflow_predecessor_source_path_relative_or_legacy_root_both_supported(source_path: str) -> None:
    predecessor_entry = ApiCatalogEntry(
        id="customer_info_v1",
        description="客户信息查询",
        domain="oms",
        method="GET",
        path="/leczcore-crm/customerInquiry/getCustomerInfo",
        status="active",
        operation_safety="query",
        response_data_path="result.records",
    )
    target_entry = _build_predecessor_target_entry_with_source_path(source_path)

    class OmsExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def call(self, entry, params, user_token=None, trace_id=None, user_id=None):
            self.calls.append((entry.id, dict(params)))
            if entry.id == "customer_info_v1":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"idCard": "2512160009"}],
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"encryptedIdCard": params.get("encryptedIdCard")}],
                total=1,
                trace_id=trace_id,
            )

    retriever = StubRetriever([target_entry])
    extractor = StubExtractor(target_entry, {})
    executor = OmsExecutor()
    planner = PassThroughPlanner(
        entry_by_step_id={
            "step_customer_info_v1": predecessor_entry,
            "step_stored_plan_v1": target_entry,
        }
    )
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,  # type: ignore[arg-type]
        planner=planner,  # type: ignore[arg-type]
        registry_source=StubRegistrySource([target_entry, predecessor_entry]),
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "查询刘海坚的储值方案"}),
        trace_id="trace-predecessor-source-path-compat",
        interaction_id=None,
        conversation_id=None,
        user_context={},
        user_token=None,
    )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert [item[0] for item in executor.calls] == ["customer_info_v1", "stored_plan_v1"]
    assert executor.calls[-1][1]["encryptedIdCard"] == ["2512160009"]


@pytest.mark.asyncio
async def test_workflow_delete_role_returns_candidate_table_when_multiple_matches() -> None:
    delete_entry = _build_role_delete_entry()
    list_entry = _build_role_list_entry()
    retriever = StubRetriever([delete_entry, list_entry])
    extractor = StubExtractor(
        delete_entry,
        {},
        business_intents=["deleteCustomer"],
    )

    class CandidateDeletePreviewExecutor:
        def __init__(self) -> None:
            self.calls = 0

        async def call(self, entry: ApiCatalogEntry, params: dict[str, object], user_token=None, trace_id=None, user_id=None):
            self.calls += 1
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[
                    {
                        "id": "r001",
                        "roleName": "健管师",
                        "roleCode": "HEALTH_MANAGER_A",
                        "appCode": "employee",
                        "status": 1,
                    },
                    {
                        "id": "r002",
                        "roleName": "健管师",
                        "roleCode": "HEALTH_MANAGER_B",
                        "appCode": "medical",
                        "status": 1,
                    },
                ],
                total=2,
                trace_id=trace_id,
            )

    executor = CandidateDeletePreviewExecutor()
    workflow = _build_workflow(
        retriever=retriever,
        extractor=extractor,
        executor=executor,  # type: ignore[arg-type]
        planner=StubPlanner(),
        registry_source=StubRegistrySource([delete_entry, list_entry]),
        ui_result=UISpecBuildResult(spec={}, frozen=False),
        dynamic_ui_override=DynamicUIService(catalog_service=UICatalogService()),
    )

    response = await workflow.run(
        ApiQueryRequest.model_validate({"query": "删除健管师角色"}),
        trace_id="trace-delete-candidates-001",
        interaction_id=None,
        conversation_id=None,
        user_context={"userId": "U001"},
        user_token=None,
    )

    assert executor.calls == 1
    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert response.execution_plan is None
    table = response.ui_spec["elements"]["report-table"]
    assert table["type"] == "PlannerTable"
    assert len(table["props"]["dataSource"]) == 2
    row_action = table["props"]["rowActions"][0]
    assert row_action["action"] == "remoteMutation"
    assert row_action["label"] == "删除该角色"
    assert row_action["params"]["body"] == {"id": {"$bindRow": "id"}}
