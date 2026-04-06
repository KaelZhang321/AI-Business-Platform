from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import api_query as api_query_routes
from app.models.schemas import (
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryRoutingResult,
    ApiQueryUIAction,
)
from app.services.api_catalog.schema import (
    ApiCatalogDetailHint,
    ApiCatalogEntry,
    ApiCatalogPaginationHint,
    ApiCatalogSearchResult,
    ApiCatalogTemplateHint,
)
from app.services.dynamic_ui_service import UISpecBuildResult
from app.services.ui_spec_guard import UISpecValidationError, UISpecValidationResult


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
                root_props={"title": "查询失败", "subtitle": None},
                children=[
                    {"type": "PlannerNotice", "props": {"tone": "info", "text": context["error"]}},
                ],
            )

        if status == ApiQueryExecutionStatus.EMPTY:
            return _build_flat_stub_spec(
                root_props={"title": "暂无数据", "subtitle": None},
                children=[
                    {"type": "PlannerNotice", "props": {"tone": "info", "text": context["empty_message"]}},
                ],
            )

        if status == ApiQueryExecutionStatus.SKIPPED:
            return _build_flat_stub_spec(
                root_props={"title": context["title"], "subtitle": None},
                children=[
                    {"type": "PlannerNotice", "props": {"tone": "info", "text": context["skip_message"]}},
                ],
            )

        return _build_flat_stub_spec(
            root_props={
                "title": "查询结果",
                "subtitle": "当前展示 1 条",
            },
            children=[
                {
                    "type": "PlannerTable",
                    "props": {
                        "columns": [
                            {"key": "customerId", "title": "customerId", "dataIndex": "customerId"},
                            {"key": "customerName", "title": "customerName", "dataIndex": "customerName"},
                        ],
                        "dataSource": [{"customerId": "C001", "customerName": "张三"}],
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


class FrozenDynamicUI:
    """模拟第五阶段 Guard 命中后的冻结视图输出。"""

    async def generate_ui_spec_result(
        self, intent: str, data, context=None, *, status=None, runtime=None, trace_id=None
    ):
        return UISpecBuildResult(
            spec=_build_flat_stub_spec(
                root_props={"title": (context or {}).get("title", "界面已安全冻结"), "subtitle": None},
                children=[
                    {
                        "type": "PlannerNotice",
                        "props": {
                            "tone": "info",
                            "text": "界面渲染组件存在异常，为保障您的数据安全，已冻结当前操作视图。",
                        },
                    }
                ],
            ),
            validation=UISpecValidationResult(
                errors=[
                    UISpecValidationError(
                        code="unknown_action",
                        path="$.elements.child_1.props.action.type",
                        message="动作未注册",
                    )
                ]
            ),
            frozen=True,
        )


class StubUICatalogService:
    """用于验证 `runtime-metadata` 已切到目录服务主链路。"""

    def __init__(self) -> None:
        self.warmup_called = False

    async def warmup(self, *, force_refresh: bool = False) -> None:
        self.warmup_called = True

    def get_component_codes(self, *, intent: str | None = None, requested_codes=None) -> list[str]:
        if intent == "query":
            return ["PlannerCard", "PlannerNotice", "PlannerTable"]
        return ["Card"]

    def build_runtime_actions(self, action_codes=None) -> list[ApiQueryUIAction]:
        return [
            ApiQueryUIAction(
                code="remoteQuery",
                description="由目录服务提供的查询动作",
                enabled=True,
                params_schema={"type": "object"},
            ),
            ApiQueryUIAction(
                code="remoteMutation",
                description="由目录服务提供的写动作",
                enabled=False,
                params_schema={"type": "object"},
            ),
        ]

    def get_template_scenarios(self) -> list[dict[str, object]]:
        return [
            {
                "code": "custom_template",
                "description": "自定义模板快路",
                "enabled": True,
            }
        ]


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
            "type": "PlannerCard",
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
        headers={"X-Trace-Id": "trace-query-001", "X-Interaction-Id": "ia-query-001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"trace_id", "execution_status", "execution_plan", "ui_runtime", "ui_spec", "error"}
    assert body["trace_id"] == "trace-query-001"
    assert body["execution_status"] == "SUCCESS"
    assert body["execution_plan"]["steps"][0]["step_id"] == "step_customer_list"
    assert body["ui_runtime"]["mode"] == "read_only"
    assert set(body["ui_runtime"]["components"]) >= {"PlannerCard", "PlannerTable"}
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
    assert set(body.keys()) == {"trace_id", "execution_status", "execution_plan", "ui_runtime", "ui_spec", "error"}
    assert body["execution_plan"]["steps"][0]["step_id"] == "step_customer_list"
    assert body["ui_runtime"]["audit"]["enabled"] is True
    assert body["ui_runtime"]["audit"]["snapshot_required"] is True
    assert body["ui_runtime"]["audit"]["snapshot_id"] == "snap_test_001"
    assert body["ui_runtime"]["audit"]["risk_level"] == "high"


def test_api_query_soft_degrades_when_route_query_fails(monkeypatch, caplog) -> None:
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
    with caplog.at_level("INFO", logger=api_query_routes.logger.name):
        response = client.post(
            "/api/v1/api-query",
            json={"query": "帮我处理那个事情"},
            headers={"X-Trace-Id": "trace-degrade-001", "X-Interaction-Id": "ia-degrade-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"trace_id", "execution_status", "execution_plan", "ui_runtime", "ui_spec", "error"}
    assert body["trace_id"] == "trace-degrade-001"
    assert body["execution_status"] == "SKIPPED"
    assert body["execution_plan"] is None
    assert body["error"] == "抱歉，我没有完全理解您的意图，或系统中暂未开放相关查询能力，请尝试换种说法。"
    root_id = body["ui_spec"]["root"]
    assert body["ui_spec"]["elements"][root_id]["props"]["title"] == "未识别到可用业务域"
    assert "interaction=ia-degrade-001" in caplog.text


def test_runtime_metadata_endpoint_returns_contract(monkeypatch) -> None:
    stub_catalog_service = StubUICatalogService()
    monkeypatch.setattr(api_query_routes, "_get_ui_catalog_service", lambda: stub_catalog_service)

    client = TestClient(create_test_app())
    response = client.get("/api/v1/api-query/runtime-metadata")

    assert response.status_code == 200
    body = response.json()
    action_codes = {item["code"] for item in body["ui_runtime"]["ui_actions"]}
    assert action_codes == {"remoteQuery", "remoteMutation"}
    assert body["ui_runtime"]["components"] == ["PlannerCard", "PlannerNotice", "PlannerTable"]
    template_codes = {item["code"] for item in body["template_scenarios"]}
    assert template_codes == {"custom_template"}
    assert body["ui_runtime"]["template"]["fallback_mode"] == "dynamic_ui"
    assert stub_catalog_service.warmup_called is True


def test_api_query_returns_frozen_runtime_when_renderer_guard_rejects_spec(monkeypatch) -> None:
    entry = _make_entry()
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry, {"pageNum": 1, "pageSize": 1}),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "customerName": "张三"}],
                total=1,
            )
        ),
        FrozenDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询张三客户"})

    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "SUCCESS"
    assert body["ui_runtime"]["ui_actions"] == []
    assert body["ui_runtime"]["detail"]["enabled"] is False
    assert body["ui_runtime"]["pagination"]["enabled"] is False
    assert body["ui_runtime"]["template"]["enabled"] is False
    root_id = body["ui_spec"]["root"]
    notice = body["ui_spec"]["elements"]["child_1"]
    assert body["ui_spec"]["elements"][root_id]["type"] == "PlannerCard"
    assert notice["type"] == "PlannerNotice"
    assert "已冻结当前操作视图" in notice["props"]["text"]
