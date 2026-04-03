from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import api_query as api_query_routes
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult


class StubRetriever:
    def __init__(self, entry: ApiCatalogEntry) -> None:
        self._entry = entry

    async def search(self, query: str, top_k: int = 3):
        return [ApiCatalogSearchResult(entry=self._entry, score=0.91)]


class StubExtractor:
    def __init__(self, entry: ApiCatalogEntry, params: dict[str, object]) -> None:
        self._entry = entry
        self._params = params

    async def extract(self, query: str, candidates, user_context: dict[str, object]):
        return self._entry, dict(self._params)


class StubExecutor:
    def __init__(self, payload, total: int) -> None:
        self._payload = payload
        self._total = total

    async def call(self, entry: ApiCatalogEntry, params: dict[str, object], user_token: str | None = None):
        return self._payload, self._total


class StubDynamicUI:
    async def generate_ui_spec(self, intent: str, data, context=None):
        return {
            "type": "Card",
            "props": {
                "title": "查询结果",
                "actions": [{"type": "refresh", "label": "重新查询"}],
            },
            "children": [
                {
                    "type": "Table",
                    "props": {
                        "columns": ["customer_id", "name"],
                        "data": [["C001", "张三"]],
                        "actions": [{"type": "export", "label": "导出"}],
                    },
                }
            ],
        }


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_query_routes.router, prefix="/api/v1")
    return app


def test_api_query_returns_runtime_contract(monkeypatch) -> None:
    entry = ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        method="GET",
        path="/api/v1/customers",
    )
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry, {"page": 1, "size": 1}),
        StubExecutor([{"customer_id": "C001", "name": "张三"}], total=8),
        StubDynamicUI(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={"query": "查询张三客户"},
        headers={"X-Trace-Id": "trace-query-001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"] == "trace-query-001"
    assert body["api_id"] == "customer_list"
    assert body["business_intents"] == [
        {
            "code": "query_business_data",
            "name": "查询业务数据",
            "category": "read",
            "description": "仅允许读操作进入 api_query 执行链路。",
        }
    ]
    assert body["ui_runtime"]["mode"] == "read_only"
    assert body["ui_runtime"]["components"] == ["Card", "Table"]
    assert body["ui_runtime"]["detail"]["enabled"] is True
    assert body["ui_runtime"]["detail"]["identifier_field"] == "customer_id"
    assert body["ui_runtime"]["pagination"]["enabled"] is True
    assert body["ui_runtime"]["pagination"]["total"] == 8
    action_codes = {item["code"] for item in body["ui_runtime"]["ui_actions"]}
    assert {"refresh", "export", "remoteQuery", "view_detail"} <= action_codes


def test_api_query_blocks_non_read_method(monkeypatch) -> None:
    entry = ApiCatalogEntry(
        id="customer_update",
        description="更新客户信息",
        method="POST",
        path="/api/v1/customers/update",
    )
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry, {"customerId": "C001"}),
        StubExecutor({"ok": True}, total=1),
        StubDynamicUI(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={"query": "修改张三客户信息"},
        headers={"X-Trace-Id": "trace-block-001"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "[trace-block-001] api_query 仅支持只读接口，当前命中 POST /api/v1/customers/update"


def test_runtime_metadata_endpoint_returns_contract() -> None:
    client = TestClient(create_test_app())
    response = client.get("/api/v1/api-query/runtime-metadata")

    assert response.status_code == 200
    body = response.json()
    action_codes = {item["code"] for item in body["ui_runtime"]["ui_actions"]}
    assert {"view_detail", "refresh", "export", "trigger_task", "remoteQuery", "remoteMutation"} <= action_codes
    template_codes = {item["code"] for item in body["template_scenarios"]}
    assert {"list_detail_template", "pagination_patch", "wysiwyg_audit"} <= template_codes
