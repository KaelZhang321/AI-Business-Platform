from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.schemas import (
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryRoutingResult,
    ApiQueryRequest,
)
from app.services.api_catalog.dag_planner import DagPlanValidationError
from app.services.api_catalog.schema import (
    ApiCatalogDetailHint,
    ApiCatalogEntry,
    ApiCatalogPaginationHint,
    ApiCatalogSearchResult,
    ApiCatalogTemplateHint,
)
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_workflow import ApiQueryWorkflow
from app.services.dynamic_ui_service import UISpecBuildResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.ui_spec_guard import UISpecValidationError, UISpecValidationResult


class StubRetriever:
    def __init__(self, entries: list[ApiCatalogEntry]) -> None:
        self._entries = entries
        self.calls = 0

    async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
        self.calls += 1
        return [ApiCatalogSearchResult(entry=entry, score=0.9) for entry in self._entries]


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

    async def call(self, entry: ApiCatalogEntry, params: dict[str, object], user_token=None, trace_id=None):
        self.calls += 1
        return self._result.model_copy(update={"trace_id": trace_id or self._result.trace_id})


class StubPlanner:
    def __init__(self, *, step_entries: dict[str, ApiCatalogEntry] | None = None, validate_error: Exception | None = None):
        self._step_entries = step_entries or {}
        self._validate_error = validate_error
        self.validate_calls = 0
        self.build_calls = 0

    async def build_plan(self, query, candidates, user_context, route_hint, *, trace_id=None):
        self.build_calls += 1
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

    def validate_plan(self, plan, candidates):
        self.validate_calls += 1
        if self._validate_error is not None:
            raise self._validate_error
        return dict(self._step_entries)


class StubRegistrySource:
    def __init__(self, entry: ApiCatalogEntry | None) -> None:
        self._entry = entry
        self.calls = 0

    async def get_entry_by_id(self, api_id: str):
        self.calls += 1
        return self._entry


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


def _build_workflow(
    *,
    retriever: StubRetriever,
    extractor: StubExtractor,
    executor: StubExecutor,
    planner: StubPlanner,
    registry_source: StubRegistrySource,
    ui_result: UISpecBuildResult,
) -> ApiQueryWorkflow:
    response_builder = ApiQueryResponseBuilder(
        dynamic_ui=FakeDynamicUI(result=ui_result),
        snapshot_service=UISnapshotService(),
        ui_catalog_service=UICatalogService(),
        registry_source=registry_source,
    )
    return ApiQueryWorkflow(
        services_getter=lambda: (retriever, extractor, executor, FakeDynamicUI(result=ui_result), UISnapshotService()),
        planner_getter=lambda: planner,
        response_builder_getter=lambda: response_builder,
        registry_source_getter=lambda: registry_source,
        allowed_business_intent_codes_getter=lambda: {"none", "saveToServer"},
    )


@pytest.mark.asyncio
async def test_workflow_runs_direct_path_without_routing(caplog) -> None:
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
        ui_result=UISpecBuildResult(spec=_build_flat_spec(), frozen=False),
    )

    with caplog.at_level("INFO", logger="app.services.api_query_workflow"):
        response = await workflow.run(
            ApiQueryRequest.model_validate(
                {
                    "mode": "direct",
                    "direct_query": {
                        "api_id": entry.id,
                        "params": {"customerId": "C001", "pageNum": 1, "pageSize": 20},
                    },
                }
            ),
            trace_id="trace-direct-001",
            interaction_id="interaction-001",
            conversation_id="conversation-001",
            user_context={},
            user_token="Bearer test-token",
        )

    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert response.execution_plan is not None
    assert response.execution_plan.steps[0].api_id == entry.id
    assert response.ui_runtime is not None
    assert response.ui_runtime.list.enabled is True
    assert retriever.calls == 0
    assert extractor.route_calls == 0
    assert executor.calls == 1
    assert "phase=stage4" in caplog.text
    assert "node=execute_plan" in caplog.text
    assert "conversation_id=conversation-001" in caplog.text
    assert "execution_status=SUCCESS" in caplog.text


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
