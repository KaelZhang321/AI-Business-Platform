from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import api_query as api_query_routes
from app.models.schemas import (
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryRoutingResult,
)
from app.services.api_catalog.schema import (
    ApiCatalogDetailHint,
    ApiCatalogEntry,
    ApiCatalogPaginationHint,
    ApiCatalogSearchResult,
    ApiCatalogTemplateHint,
)


class StubRetriever:
    def __init__(self, entry: ApiCatalogEntry) -> None:
        self._entry = entry
        self.last_filters = None

    async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
        self.last_filters = filters
        return [ApiCatalogSearchResult(entry=self._entry, score=0.91)]

    async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
        return await self.search(query, top_k=top_k, filters=filters)


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

    async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            query_domains=[self._entry.domain] if self._route_status == "ok" else [],
            business_intents=list(self._business_intents),
            is_multi_domain=False,
            reasoning="stub route",
            route_status=self._route_status,
            route_error_code=self._route_error_code,
        )

    async def extract_routing_result(self, query: str, candidates, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            selected_api_id=self._entry.id,
            query_domains=[self._entry.domain],
            business_intents=list(self._business_intents),
            params=dict(self._params),
        )


class StubExecutor:
    def __init__(self, result: ApiQueryExecutionResult) -> None:
        self._result = result

    async def call(
        self,
        entry: ApiCatalogEntry,
        params: dict[str, object],
        user_token: str | None = None,
        trace_id: str | None = None,
    ):
        return self._result.model_copy(update={"trace_id": trace_id or self._result.trace_id})


class StubDynamicUI:
    async def generate_ui_spec(self, intent: str, data, context=None, *, status=None, runtime=None):
        if status == ApiQueryExecutionStatus.ERROR:
            return _build_flat_stub_spec(
                root_props={"title": "查询失败", "actions": [{"type": "refresh", "label": "重试"}]},
                children=[
                    {"type": "Notice", "props": {"level": "warning", "message": context["error"]}},
                ],
            )

        if status == ApiQueryExecutionStatus.EMPTY:
            return _build_flat_stub_spec(
                root_props={"title": "暂无数据", "actions": [{"type": "refresh", "label": "重试"}]},
                children=[
                    {"type": "Notice", "props": {"level": "info", "message": context["empty_message"]}},
                ],
            )

        if status == ApiQueryExecutionStatus.SKIPPED:
            return _build_flat_stub_spec(
                root_props={"title": context["title"], "actions": [{"type": "refresh", "label": "重试"}]},
                children=[
                    {"type": "Notice", "props": {"level": "info", "message": context["skip_message"]}},
                ],
            )

        return _build_flat_stub_spec(
            root_props={
                "title": "查询结果",
                "actions": [{"type": "refresh", "label": "重新查询"}],
            },
            children=[
                {
                    "type": "Table",
                    "props": {
                        "columns": ["customerId", "customerName"],
                        "data": [["C001", "张三"]],
                        "actions": [{"type": "export", "label": "导出"}],
                        "rowActions": [
                            {
                                "type": "remoteQuery",
                                "label": "查看详情",
                                "params": {
                                    "api_id": runtime.detail.api_id if runtime else "unknown",
                                    "query_param": runtime.detail.query_param if runtime else "customerId",
                                },
                            }
                        ],
                    },
                }
            ],
        )


class StubSnapshotService:
    def __init__(self, should_capture: bool = False) -> None:
        self._should_capture = should_capture

    def should_capture(self, business_intents):
        return self._should_capture

    def create_snapshot(self, *, trace_id: str, business_intents, ui_spec, ui_runtime, metadata):
        class Snapshot:
            snapshot_id = "snap_test_001"

        return Snapshot()


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_query_routes.router, prefix="/api/v1")
    return app


def _build_flat_stub_spec(*, root_props: dict[str, object], children: list[dict[str, object]]) -> dict[str, object]:
    """为路由测试构造 flat spec。

    功能：
        任务 1 的目标是把 `api_query` 对外 Spec 契约统一为 `root/state/elements`。
        路由测试桩也必须跟着切到新协议，否则测试会继续把旧结构误当成正确行为。
    """
    elements: dict[str, object] = {
        "root": {
            "type": "Card",
            "props": root_props,
            "children": [],
        }
    }
    for index, child in enumerate(children, start=1):
        child_id = f"child_{index}"
        elements["root"]["children"].append(child_id)
        elements[child_id] = child
    return {
        "root": "root",
        "state": {},
        "elements": elements,
    }


def _make_entry(**overrides) -> ApiCatalogEntry:
    defaults = {
        "id": "customer_list",
        "description": "查询客户列表",
        "domain": "crm",
        "method": "GET",
        "path": "/api/v1/customers",
        "detail_hint": ApiCatalogDetailHint(
            enabled=True,
            api_id="customer_detail",
            identifier_field="customerId",
            query_param="customerId",
            template_code="customer_detail_template",
            fallback_mode="dynamic_ui",
        ),
        "pagination_hint": ApiCatalogPaginationHint(
            enabled=True,
            api_id="customer_list",
            page_param="pageNum",
            page_size_param="pageSize",
            mutation_target="report-table.props.dataSource",
        ),
        "template_hint": ApiCatalogTemplateHint(
            enabled=True,
            template_code="customer_list_template",
            render_mode="java_template",
            fallback_mode="dynamic_ui",
        ),
    }
    return ApiCatalogEntry(**{**defaults, **overrides})


def test_api_query_returns_runtime_contract(monkeypatch) -> None:
    entry = _make_entry()
    stub_retriever = StubRetriever(entry)
    stub_services = (
        stub_retriever,
        StubExtractor(entry, {"pageNum": 1, "pageSize": 1}),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "customerName": "张三"}],
                total=8,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(),
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
    assert body["query_domains"] == ["CRM"]
    assert body["execution_status"] == "SUCCESS"
    assert body["api_id"] == "customer_list"
    assert body["business_intents"] == [
        {
            "code": "none",
            "name": "纯查询",
            "category": "read",
            "description": "当前请求仅包含读取诉求，不携带写前确认意图。",
            "risk_level": None,
        }
    ]
    assert body["context_pool"]["step_customer_list"]["status"] == "SUCCESS"
    assert body["context_pool"]["step_customer_list"]["domain"] == "crm"
    assert body["context_pool"]["step_customer_list"]["api_id"] == "customer_list"
    assert body["context_pool"]["step_customer_list"]["meta"]["render_row_limit"] == 5
    assert body["ui_runtime"]["mode"] == "read_only"
    assert set(body["ui_runtime"]["components"]) >= {"Card", "Table"}
    assert body["ui_runtime"]["detail"]["enabled"] is True
    assert body["ui_runtime"]["detail"]["api_id"] == "customer_detail"
    assert body["ui_runtime"]["detail"]["identifier_field"] == "customerId"
    assert body["ui_runtime"]["pagination"]["enabled"] is True
    assert body["ui_runtime"]["pagination"]["total"] == 8
    assert body["ui_runtime"]["pagination"]["mutation_target"] == "report-table.props.dataSource"
    assert body["ui_runtime"]["template"]["enabled"] is True
    action_codes = {item["code"] for item in body["ui_runtime"]["ui_actions"]}
    assert {"refresh", "export", "remoteQuery", "view_detail"} <= action_codes
    assert stub_retriever.last_filters.model_dump() == {
        "domains": [],
        "envs": [],
        "statuses": ["active"],
        "tag_names": [],
    }


def test_api_query_passes_env_and_tag_filters_to_retriever(monkeypatch) -> None:
    entry = _make_entry()
    stub_retriever = StubRetriever(entry)
    stub_services = (
        stub_retriever,
        StubExtractor(entry, {"pageNum": 1}),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "customerName": "张三"}],
                total=1,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={
            "query": "查询张三客户",
            "envs": ["PROD", "prod", ""],
            "tag_names": ["合同管理", "合同管理", " "],
        },
    )

    assert response.status_code == 200
    assert stub_retriever.last_filters.model_dump() == {
        "domains": [],
        "envs": ["prod"],
        "statuses": ["active"],
        "tag_names": ["合同管理"],
    }


def test_api_query_blocks_non_read_method(monkeypatch) -> None:
    entry = _make_entry(id="customer_update", method="POST", path="/api/v1/customers/update")
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry, {"customerId": "C001"}),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data={"ok": True},
                total=1,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={"query": "修改张三客户信息"},
        headers={"X-Trace-Id": "trace-block-001"},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "[trace-block-001] api_query 仅支持只读接口，当前命中 POST /api/v1/customers/update"
    )


def test_api_query_attaches_snapshot_for_high_risk_write_intent(monkeypatch) -> None:
    entry = _make_entry()
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry, {"customerId": "C001"}, business_intents=["prepare_high_risk_change"]),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "customerName": "张三"}],
                total=1,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(should_capture=True),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "准备修改高风险合同"})

    assert response.status_code == 200
    body = response.json()
    assert body["business_intents"][0]["code"] == "saveToServer"
    assert body["business_intents"][0]["risk_level"] == "high"
    assert body["ui_runtime"]["audit"]["enabled"] is True
    assert body["ui_runtime"]["audit"]["snapshot_required"] is True
    assert body["ui_runtime"]["audit"]["snapshot_id"] == "snap_test_001"
    assert body["ui_runtime"]["audit"]["risk_level"] == "high"


def test_api_query_soft_degrades_when_route_query_fails(monkeypatch) -> None:
    entry = _make_entry()
    stub_services = (
        StubRetriever(entry),
        StubExtractor(
            entry,
            {"customerId": "C001"},
            route_status="fallback",
            route_error_code="routing_parse_failed",
        ),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "customerName": "张三"}],
                total=1,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "帮我处理那个事情"})

    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "SKIPPED"
    assert body["query_domains"] == []
    assert body["context_pool"]["stage2_routing"]["status"] == "SKIPPED"
    assert body["context_pool"]["stage2_routing"]["error"]["code"] == "routing_parse_failed"
    assert body["business_intents"][0]["code"] == "none"
    root_id = body["ui_spec"]["root"]
    assert body["ui_spec"]["elements"][root_id]["props"]["title"] == "未识别到可用业务域"


def test_runtime_metadata_endpoint_returns_contract() -> None:
    client = TestClient(create_test_app())
    response = client.get("/api/v1/api-query/runtime-metadata")

    assert response.status_code == 200
    body = response.json()
    action_codes = {item["code"] for item in body["ui_runtime"]["ui_actions"]}
    assert {"view_detail", "refresh", "export", "trigger_task", "remoteQuery", "remoteMutation"} <= action_codes
    template_codes = {item["code"] for item in body["template_scenarios"]}
    assert {"list_detail_template", "pagination_patch", "wysiwyg_audit"} <= template_codes
    assert body["ui_runtime"]["template"]["fallback_mode"] == "dynamic_ui"
