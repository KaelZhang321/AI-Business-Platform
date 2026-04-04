from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import api_query as api_query_routes
from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryPlanStep,
    ApiQueryRoutingResult,
)
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult


class StubRetriever:
    def __init__(self, entry: ApiCatalogEntry) -> None:
        self._entry = entry
        self.last_filters = None

    async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
        self.last_filters = filters
        return [ApiCatalogSearchResult(entry=self._entry, score=0.95)]

    async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
        return await self.search(query, top_k=top_k, score_threshold=0.3, filters=filters)


class StubExtractor:
    def __init__(self, entry: ApiCatalogEntry) -> None:
        self._entry = entry

    async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            query_domains=[self._entry.domain],
            business_intents=["none"],
            is_multi_domain=False,
            reasoning="runtime test route",
            route_status="ok",
        )

    async def extract_routing_result(self, query: str, candidates, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            selected_api_id=self._entry.id,
            query_domains=[self._entry.domain],
            business_intents=["none"],
            params={"pageNum": 1, "pageSize": 20},
        )


class StubExecutor:
    def __init__(self, result: ApiQueryExecutionResult) -> None:
        self._result = result

    async def call(self, entry, params, user_token=None, trace_id: str | None = None):
        return self._result.model_copy(update={"trace_id": trace_id})


class PassThroughSnapshotService:
    def should_capture(self, business_intents):
        return False


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_query_routes.router, prefix="/api/v1")
    return app


def _make_entry() -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        method="GET",
        path="/api/v1/customers",
    )


def test_api_query_returns_empty_notice_for_empty_execution(monkeypatch) -> None:
    entry = _make_entry()
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.EMPTY,
                data=[],
                total=0,
            )
        ),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询不存在的客户"})

    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "EMPTY"
    assert body["data_count"] == 0
    assert body["ui_runtime"]["audit"]["enabled"] is False
    assert body["ui_spec"]["children"][0]["type"] == "Notice"
    assert body["ui_spec"]["children"][0]["props"]["level"] == "info"


def test_api_query_returns_error_notice_for_error_execution(monkeypatch) -> None:
    entry = _make_entry()
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.ERROR,
                data=None,
                total=0,
                error="业务接口超时",
            )
        ),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询客户"})

    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "ERROR"
    assert body["error"] == "业务接口超时"
    assert body["context_pool"]["step_customer_list"]["error"]["message"] == "业务接口超时"
    assert body["ui_spec"]["children"][0]["type"] == "Notice"
    assert body["ui_spec"]["children"][0]["props"]["level"] == "warning"


def test_api_query_returns_skipped_notice_for_missing_required_params(monkeypatch) -> None:
    entry = _make_entry()
    entry.param_schema.required = ["customerId"]
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001"}],
                total=1,
            )
        ),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询客户详情"})

    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "SKIPPED"
    assert body["error"] == "缺少必要参数：customerId"
    assert body["context_pool"]["step_customer_list"]["skipped_reason"] == "missing_required_params"
    assert body["ui_spec"]["children"][0]["type"] == "Notice"
    assert body["ui_spec"]["children"][0]["props"]["message"] == "由于缺少必要参数 customerId，当前查询未被执行。"


def test_api_query_truncates_context_pool_and_ui_rows(monkeypatch) -> None:
    entry = _make_entry()
    rows = [{"customerId": f"C{i:03d}", "customerName": f"客户{i}"} for i in range(1, 8)]
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=rows,
                total=20,
            )
        ),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询客户列表"})

    assert response.status_code == 200
    body = response.json()
    assert body["data_count"] == 7
    assert body["total"] == 20
    assert body["context_pool"]["step_customer_list"]["meta"]["truncated"] is True
    assert body["context_pool"]["step_customer_list"]["meta"]["render_row_count"] == 5
    assert body["context_pool"]["step_customer_list"]["meta"]["truncated_count"] == 2
    assert len(body["ui_spec"]["children"][-1]["props"]["data"]) == 5


def test_api_query_executes_multi_step_plan_and_returns_multi_step_context_pool(monkeypatch) -> None:
    customer_entry = ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        method="GET",
        path="/api/v1/customers",
        param_schema={
            "type": "object",
            "properties": {"owner_id": {"type": "string"}},
            "required": ["owner_id"],
        },
    )
    order_entry = ApiCatalogEntry(
        id="order_stats",
        description="查询客户订单统计",
        domain="erp",
        method="GET",
        path="/api/v1/orders/stats",
        param_schema={
            "type": "object",
            "properties": {"customer_ids": {"type": "array"}},
            "required": ["customer_ids"],
        },
    )

    class MultiRetriever:
        async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
            return [
                ApiCatalogSearchResult(entry=customer_entry, score=0.95),
                ApiCatalogSearchResult(entry=order_entry, score=0.93),
            ]

        async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
            return await self.search(query, top_k=top_k, score_threshold=0.3, filters=filters)

    class RouteOnlyExtractor:
        async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
            return ApiQueryRoutingResult(
                query_domains=["crm", "erp"],
                business_intents=["none"],
                is_multi_domain=True,
                reasoning="multi-domain runtime test",
                route_status="ok",
            )

    class PlannerStub:
        async def build_plan(self, query, candidates, user_context, route_hint):
            return ApiQueryExecutionPlan(
                plan_id="dag_customer_orders",
                steps=[
                    ApiQueryPlanStep(
                        step_id="step_customers",
                        api_path="/api/v1/customers",
                        params={"owner_id": "E8899"},
                        depends_on=[],
                    ),
                    ApiQueryPlanStep(
                        step_id="step_orders",
                        api_path="/api/v1/orders/stats",
                        params={"customer_ids": "$[step_customers.data][*].customerId"},
                        depends_on=["step_customers"],
                    ),
                ],
            )

        def validate_plan(self, plan, candidates):
            return {
                "step_customers": customer_entry,
                "step_orders": order_entry,
            }

    class MultiStepExecutor:
        async def call(self, entry, params, user_token=None, trace_id: str | None = None):
            if entry.id == "customer_list":
                assert params == {"owner_id": "E8899"}
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"customerId": "C001", "customerName": "张三"}],
                    total=1,
                    trace_id=trace_id,
                )

            assert params == {"customer_ids": ["C001"]}
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "orderCount": 3}],
                total=1,
                trace_id=trace_id,
            )

    stub_services = (
        MultiRetriever(),
        RouteOnlyExtractor(),
        MultiStepExecutor(),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_planner", lambda: PlannerStub())

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查我的客户，并看他们的订单统计"})

    assert response.status_code == 200
    body = response.json()
    assert body["execution_plan"]["plan_id"] == "dag_customer_orders"
    assert [step["step_id"] for step in body["execution_plan"]["steps"]] == ["step_customers", "step_orders"]
    assert body["execution_status"] == "SUCCESS"
    assert set(body["context_pool"]) == {"step_customers", "step_orders"}
    assert body["context_pool"]["step_orders"]["meta"]["resolved_params"] == {"customer_ids": ["C001"]}
    assert body["query_domains"] == ["CRM", "ERP"]
