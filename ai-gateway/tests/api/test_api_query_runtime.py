from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import api_query as api_query_routes
from app.models.schemas import ApiQueryExecutionResult, ApiQueryExecutionStatus, ApiQueryRoutingResult
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult


class StubRetriever:
    def __init__(self, entry: ApiCatalogEntry) -> None:
        self._entry = entry

    async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
        return [ApiCatalogSearchResult(entry=self._entry, score=0.95)]


class StubExtractor:
    def __init__(self, entry: ApiCatalogEntry) -> None:
        self._entry = entry

    async def extract_routing_result(self, query: str, candidates, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            selected_api_id=self._entry.id,
            query_domains=[self._entry.domain],
            business_intents=["query_business_data"],
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
    assert body["ui_spec"]["children"][0]["type"] == "Notice"
    assert body["ui_spec"]["children"][0]["props"]["level"] == "warning"
