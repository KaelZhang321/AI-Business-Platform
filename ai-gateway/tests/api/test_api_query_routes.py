from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import api_query as api_query_routes
from app.models.schemas import (
    ApiQueryResponse,
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
            # mutation_form 快路：context 有 api_id 字段
            if intent == "mutation_form":
                return _build_flat_stub_spec(
                    root_props={"title": context.get("title", "确认修改"), "subtitle": None},
                    children=[
                        {"type": "PlannerForm", "props": {"formCode": context.get("form_code", "form")}},
                    ],
                )
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
                                    "request": (
                                        runtime.detail.request.model_dump(exclude_none=True)
                                        if runtime
                                        else {"identifier_param": "customerId"}
                                    ),
                                    "source": (
                                        runtime.detail.source.model_dump(exclude_none=True)
                                        if runtime
                                        else {"identifier_field": "customerId"}
                                    ),
                                },
                            }
                        ],
                    },
                }
            ],
        )


class FormRuntimeDynamicUI:
    """模拟 Renderer 返回带表单提交动作的最终 Spec。"""

    async def generate_ui_spec(self, intent: str, data, context=None, *, status=None, runtime=None):
        return _build_flat_stub_spec(
            root_props={"title": "客户编辑", "subtitle": "请确认后提交"},
            state={
                "form": {
                    "customerId": "C001",
                    "industry": "medical",
                }
            },
            children=[
                {"type": "PlannerMetric", "props": {"label": "客户ID", "value": "C001"}},
                {
                    "type": "PlannerSelect",
                    "props": {
                        "label": "所属行业",
                        "value": {"$bindState": "/form/industry"},
                        "options": {"type": "dict", "dict_code": "industry"},
                    },
                },
                {
                    "type": "PlannerButton",
                    "props": {"label": "确认保存"},
                    "on": {
                        "press": {
                            "action": "remoteMutation",
                            "params": {
                                "api_id": "customer_update",
                                "payload": {
                                    "customerId": {"$bindState": "/form/customerId"},
                                    "industry": {"$bindState": "/form/industry"},
                                },
                            },
                        }
                    },
                },
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


class StubRegistrySource:
    """模拟 `direct` 模式按 api_id 精确查目录的主链路。"""

    def __init__(self, entry: ApiCatalogEntry | dict[str, ApiCatalogEntry] | None) -> None:
        self._entry = entry
        self.last_api_id: str | None = None

    async def get_entry_by_id(self, api_id: str) -> ApiCatalogEntry | None:
        self.last_api_id = api_id
        if isinstance(self._entry, dict):
            return self._entry.get(api_id)
        return self._entry


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
            return [
                "PlannerCard",
                "PlannerMetric",
                "PlannerTable",
                "PlannerDetailCard",
                "PlannerForm",
                "PlannerInput",
                "PlannerSelect",
                "PlannerButton",
                "PlannerNotice",
            ]
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


def test_api_query_route_delegates_to_workflow(monkeypatch) -> None:
    """路由层应只做 HTTP 适配，并把上下文交给 workflow。"""

    captured: dict[str, object] = {}

    class FakeWorkflow:
        async def run(
            self,
            request_body,
            *,
            trace_id: str,
            interaction_id: str | None,
            conversation_id: str | None,
            user_context: dict[str, object],
            user_token: str | None,
        ):
            captured.update(
                {
                    "request_body": request_body.model_dump(mode="json", exclude_none=True),
                    "trace_id": trace_id,
                    "interaction_id": interaction_id,
                    "conversation_id": conversation_id,
                    "user_context": user_context,
                    "user_token": user_token,
                }
            )
            return ApiQueryResponse(
                trace_id=trace_id,
                execution_status=ApiQueryExecutionStatus.SUCCESS,
                execution_plan=None,
                ui_runtime=None,
                ui_spec={"root": "page", "state": {}, "elements": {"page": {"id": "page", "type": "PlannerCard"}}},
                error=None,
            )

    monkeypatch.setattr(api_query_routes, "_get_workflow", lambda: FakeWorkflow())

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={"query": "查询张三客户", "conversation_id": "conv-route-001"},
        headers={
            "X-Trace-Id": "trace-route-001",
            "X-Interaction-Id": "ia-route-001",
            "Authorization": "Bearer route-token",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "request_body": {"mode": "nl", "response_mode": "full_spec", "query": "查询张三客户", "conversation_id": "conv-route-001", "top_k": 3, "envs": [], "tag_names": []},
        "trace_id": "trace-route-001",
        "interaction_id": "ia-route-001",
        "conversation_id": "conv-route-001",
        "user_context": {},
        "user_token": "Bearer route-token",
    }


def _build_flat_stub_spec(
    *,
    root_props: dict[str, object],
    children: list[dict[str, object]],
    state: dict[str, object] | None = None,
) -> dict[str, object]:
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
        child_id = str(child.get("id") or f"child_{index}")
        child_payload = dict(child)
        child_payload.pop("id", None)
        elements["root"]["children"].append(child_id)
        elements[child_id] = child_payload
    return {
        "root": "root",
        "state": state or {},
        "elements": elements,
    }


def _make_entry(**overrides) -> ApiCatalogEntry:
    defaults = {
        "id": "customer_list",
        "description": "查询客户列表",
        "domain": "crm",
        "operation_safety": "query",
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
    assert body["execution_plan"]["steps"][0]["api_id"] == "customer_list"
    assert body["ui_runtime"]["mode"] == "read_only"
    assert set(body["ui_runtime"]["components"]) >= {"PlannerCard", "PlannerTable"}
    assert body["ui_runtime"]["list"]["enabled"] is True
    assert body["ui_runtime"]["list"]["api_id"] == "customer_list"
    assert body["ui_runtime"]["list"]["param_source"] == "queryParams"
    assert body["ui_runtime"]["detail"]["enabled"] is True
    assert body["ui_runtime"]["detail"]["api_id"] == "customer_detail"
    assert body["ui_runtime"]["detail"]["request"]["identifier_param"] == "customerId"
    assert body["ui_runtime"]["detail"]["source"]["identifier_field"] == "customerId"
    assert body["ui_runtime"]["list"]["pagination"]["enabled"] is True
    assert body["ui_runtime"]["list"]["pagination"]["total"] == 8
    assert body["ui_runtime"]["list"]["pagination"]["mutation_target"] == "report-table.props.dataSource"
    assert body["ui_runtime"]["list"]["filters"]["enabled"] is False
    assert body["ui_runtime"]["list"]["query_context"]["current_params"] == {"pageNum": 1, "pageSize": 1}
    action_codes = {item["code"] for item in body["ui_runtime"]["ui_actions"]}
    assert {"refresh", "export", "remoteQuery", "view_detail"} <= action_codes
    assert stub_retriever.last_filters.model_dump() == {
        "domains": [],
        "envs": [],
        "statuses": ["active"],
        "tag_names": [],
    }


def test_api_query_direct_mode_bypasses_semantic_chain_and_returns_runtime_contract(monkeypatch, caplog) -> None:
    detail_entry = _make_entry(
        id="customer_detail",
        description="查询客户详情",
        path="/api/v1/customers/detail",
        param_schema={"type": "object", "properties": {"customerId": {"type": "string"}}, "required": ["customerId"]},
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        template_hint=ApiCatalogTemplateHint(enabled=False),
    )

    class FailIfCalledRetriever:
        async def search(self, *args, **kwargs):  # pragma: no cover - should never be invoked
            raise AssertionError("direct mode should bypass retriever.search")

        async def search_stratified(self, *args, **kwargs):  # pragma: no cover - should never be invoked
            raise AssertionError("direct mode should bypass retriever.search_stratified")

    class FailIfCalledExtractor:
        async def route_query(self, *args, **kwargs):  # pragma: no cover - should never be invoked
            raise AssertionError("direct mode should bypass extractor.route_query")

        async def extract_routing_result(self, *args, **kwargs):  # pragma: no cover - should never be invoked
            raise AssertionError("direct mode should bypass extractor.extract_routing_result")

    class CapturingExecutor:
        def __init__(self) -> None:
            self.last_params = None

        async def call(self, entry, params, user_token=None, trace_id: str | None = None):
            self.last_params = params
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data={"customerId": "C001", "customerName": "张三"},
                total=1,
                trace_id=trace_id,
            )

    registry_source = StubRegistrySource(detail_entry)
    executor = CapturingExecutor()
    stub_services = (
        FailIfCalledRetriever(),
        FailIfCalledExtractor(),
        executor,
        StubDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_registry_source", lambda: registry_source)
    monkeypatch.setattr(
        api_query_routes,
        "_get_planner",
        lambda: (_ for _ in ()).throw(AssertionError("direct mode should bypass planner")),
    )

    client = TestClient(create_test_app())
    with caplog.at_level("INFO", logger=api_query_routes.logger.name):
        response = client.post(
            "/api/v1/api-query",
            json={
                "mode": "direct",
                "conversation_id": "conv_001",
                "direct_query": {
                    "api_id": "customer_detail",
                    "params": {"customerId": "C001"},
                },
            },
            headers={"X-Trace-Id": "trace-direct-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"trace_id", "execution_status", "execution_plan", "ui_runtime", "ui_spec", "error"}
    assert body["trace_id"] == "trace-direct-001"
    assert body["execution_status"] == "SUCCESS"
    assert body["execution_plan"]["plan_id"] == "direct_trace-di"
    assert body["execution_plan"]["steps"] == [
        {
            "step_id": "step_customer_detail",
            "api_id": "customer_detail",
            "api_path": "/api/v1/customers/detail",
            "params": {"customerId": "C001"},
            "depends_on": [],
        }
    ]
    assert body["ui_runtime"]["detail"]["enabled"] is True
    assert body["ui_runtime"]["detail"]["api_id"] == "customer_detail"
    assert body["ui_spec"]["elements"][body["ui_spec"]["root"]]["type"] == "PlannerCard"
    assert registry_source.last_api_id == "customer_detail"
    assert executor.last_params == {"customerId": "C001"}
    assert "conversation_id=conv_001" in caplog.text
    assert "phase=http_adapter" in caplog.text
    assert "node=dispatch" in caplog.text


def test_api_query_direct_mode_returns_list_patch_response(monkeypatch) -> None:
    entry = _make_entry(
        param_schema={
            "type": "object",
            "properties": {
                "ownerId": {"type": "string"},
                "pageNum": {"type": "integer"},
                "pageSize": {"type": "integer"},
            },
            "required": ["ownerId", "pageNum", "pageSize"],
        }
    )
    stub_services = (
        object(),
        object(),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[
                    {"customerId": "C021", "customerName": "客户21"},
                    {"customerId": "C022", "customerName": "客户22"},
                ],
                total=68,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_registry_source", lambda: StubRegistrySource(entry))

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={
            "mode": "direct",
            "response_mode": "patch",
            "direct_query": {
                "api_id": "customer_list",
                "params": {"ownerId": "E8899", "pageNum": 2, "pageSize": 20},
            },
            "patch_context": {
                "patch_type": "list_query",
                "trigger": "pagination",
                "mutation_target": "report-table.props.dataSource",
            },
        },
        headers={"X-Trace-Id": "trace-direct-patch-001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "SUCCESS"
    assert body["ui_spec"]["kind"] == "patch"
    assert body["ui_spec"]["patch_type"] == "list_query"
    assert body["ui_spec"]["mutation_target"] == "report-table.props.dataSource"
    assert body["ui_spec"]["operations"] == [
        {
            "op": "replace",
            "path": "report-table.props.dataSource",
            "value": [
                {"customerId": "C021", "customerName": "客户21"},
                {"customerId": "C022", "customerName": "客户22"},
            ],
        },
        {"op": "replace", "path": "report-table.props.pagination.currentPage", "value": 2},
        {"op": "replace", "path": "report-table.props.pagination.pageSize", "value": 20},
        {"op": "replace", "path": "report-table.props.pagination.total", "value": 68},
    ]
    assert body["ui_runtime"]["list"]["pagination"]["current_page"] == 2
    assert body["ui_runtime"]["list"]["query_context"]["current_params"] == {
        "ownerId": "E8899",
        "pageNum": 2,
        "pageSize": 20,
    }


def test_api_query_direct_mode_requires_direct_query_payload() -> None:
    client = TestClient(create_test_app())

    response = client.post("/api/v1/api-query", json={"mode": "direct"})

    assert response.status_code == 422
    assert "mode=direct 时必须提供 direct_query" in str(response.json())


def test_api_query_direct_mode_rejects_unknown_params(monkeypatch) -> None:
    detail_entry = _make_entry(
        id="customer_detail",
        path="/api/v1/customers/detail",
        param_schema={"type": "object", "properties": {"customerId": {"type": "string"}}, "required": ["customerId"]},
    )
    stub_services = (
        object(),
        object(),
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
    monkeypatch.setattr(api_query_routes, "_get_registry_source", lambda: StubRegistrySource(detail_entry))

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={
            "mode": "direct",
            "direct_query": {
                "api_id": "customer_detail",
                "params": {"customerId": "C001", "unexpected": "boom"},
            },
        },
        headers={"X-Trace-Id": "trace-direct-params-001"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "[trace-direct-params-001] direct 模式存在未声明参数：unexpected"


def test_api_query_direct_mode_requires_required_params(monkeypatch) -> None:
    detail_entry = _make_entry(
        id="customer_detail",
        path="/api/v1/customers/detail",
        param_schema={"type": "object", "properties": {"customerId": {"type": "string"}}, "required": ["customerId"]},
    )
    stub_services = (
        object(),
        object(),
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
    monkeypatch.setattr(api_query_routes, "_get_registry_source", lambda: StubRegistrySource(detail_entry))

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={
            "mode": "direct",
            "direct_query": {
                "api_id": "customer_detail",
                "params": {},
            },
        },
        headers={"X-Trace-Id": "trace-direct-required-001"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "[trace-direct-required-001] direct 模式缺少必要参数：customerId"


def test_api_query_direct_mode_blocks_non_read_method(monkeypatch) -> None:
    write_entry = _make_entry(
        id="customer_update",
        method="POST",
        operation_safety="mutation",
        path="/api/v1/customers/update",
        detail_hint=ApiCatalogDetailHint(enabled=False),
    )
    stub_services = (
        object(),
        object(),
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
    monkeypatch.setattr(api_query_routes, "_get_registry_source", lambda: StubRegistrySource(write_entry))

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={
            "mode": "direct",
            "direct_query": {
                "api_id": "customer_update",
                "params": {"customerId": "C001"},
            },
        },
        headers={"X-Trace-Id": "trace-direct-block-001"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "[trace-direct-block-001] api_query 仅支持查询安全接口，当前接口语义为 mutation"


def test_api_query_direct_mode_rejects_patch_for_non_paginated_entry(monkeypatch) -> None:
    detail_entry = _make_entry(
        id="customer_detail",
        path="/api/v1/customers/detail",
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        param_schema={
            "type": "object",
            "properties": {
                "customerId": {"type": "string"},
                "pageNum": {"type": "integer"},
                "pageSize": {"type": "integer"},
            },
            "required": ["customerId"],
        },
    )
    stub_services = (
        object(),
        object(),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data={"customerId": "C001"},
                total=1,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_registry_source", lambda: StubRegistrySource(detail_entry))

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={
            "mode": "direct",
            "response_mode": "patch",
            "direct_query": {
                "api_id": "customer_detail",
                "params": {"customerId": "C001", "pageNum": 1, "pageSize": 20},
            },
            "patch_context": {
                "patch_type": "list_query",
                "trigger": "pagination",
                "mutation_target": "report-table.props.dataSource",
            },
        },
        headers={"X-Trace-Id": "trace-direct-patch-unsupported-001"},
    )

    assert response.status_code == 422
    assert "PATCH_MODE_NOT_SUPPORTED" in response.json()["detail"]


def test_api_query_direct_mode_rejects_patch_when_page_size_exceeds_limit(monkeypatch) -> None:
    entry = _make_entry(
        param_schema={
            "type": "object",
            "properties": {
                "ownerId": {"type": "string"},
                "pageNum": {"type": "integer"},
                "pageSize": {"type": "integer"},
            },
            "required": ["ownerId", "pageNum", "pageSize"],
        }
    )
    stub_services = (
        object(),
        object(),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[],
                total=0,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_registry_source", lambda: StubRegistrySource(entry))

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={
            "mode": "direct",
            "response_mode": "patch",
            "direct_query": {
                "api_id": "customer_list",
                "params": {"ownerId": "E8899", "pageNum": 1, "pageSize": 51},
            },
            "patch_context": {
                "patch_type": "list_query",
                "trigger": "pagination",
                "mutation_target": "report-table.props.dataSource",
            },
        },
        headers={"X-Trace-Id": "trace-direct-patch-limit-001"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "[trace-direct-patch-limit-001] patch 模式下 pageSize 不能超过 50"


def test_api_query_direct_mode_rejects_filter_submit_without_page_reset(monkeypatch) -> None:
    entry = _make_entry(
        param_schema={
            "type": "object",
            "properties": {
                "ownerId": {"type": "string"},
                "keyword": {"type": "string"},
                "pageNum": {"type": "integer"},
                "pageSize": {"type": "integer"},
            },
            "required": ["ownerId", "pageNum", "pageSize"],
        }
    )
    stub_services = (
        object(),
        object(),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[],
                total=0,
            )
        ),
        StubDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_registry_source", lambda: StubRegistrySource(entry))

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={
            "mode": "direct",
            "response_mode": "patch",
            "direct_query": {
                "api_id": "customer_list",
                "params": {"ownerId": "E8899", "keyword": "张", "pageNum": 2, "pageSize": 20},
            },
            "patch_context": {
                "patch_type": "list_query",
                "trigger": "filter_submit",
                "mutation_target": "report-table.props.dataSource",
            },
        },
        headers={"X-Trace-Id": "trace-direct-patch-filter-001"},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "[trace-direct-patch-filter-001] patch 模式下触发 filter_submit 时必须将 pageNum 重置为 1"
    )


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


def test_api_query_blocks_mutation_entry(monkeypatch) -> None:
    """mutation 接口在 NL 模式下不再直接阻断，而是返回预填表单 UI。"""
    entry = _make_entry(
        id="customer_update", method="POST", operation_safety="mutation", path="/api/v1/customers/update",
        param_schema={
            "type": "object",
            "properties": {
                "customerId": {"type": "string", "title": "客户ID"},
                "industry": {"type": "string", "title": "所属行业"},
            },
            "required": ["customerId"],
        },
        detail_hint=ApiCatalogDetailHint(enabled=False),
    )
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry, {"customerId": "C001"}, business_intents=["saveToServer"]),
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

    # NL 模式下 mutation 接口走表单快路，返回 200 + SKIPPED + form.enabled
    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "SKIPPED"
    assert body["error"] is None
    assert body["ui_runtime"]["form"]["enabled"] is True
    assert body["ui_runtime"]["form"]["api_id"] == "customer_update"
    assert body["ui_runtime"]["form"]["route_url"] == "/api/v1/customers/update"
    assert body["ui_runtime"]["form"]["mode"] == "edit"
    assert body["ui_runtime"]["form"]["submit"]["confirm_required"] is True
    # execution_plan 包含 mutation 接口步骤，供前端确认后直接调用
    assert body["execution_plan"]["steps"][0]["api_id"] == "customer_update"


def test_api_query_allows_query_safe_post_entry(monkeypatch) -> None:
    entry = _make_entry(id="customer_search", method="POST", operation_safety="query", path="/api/v1/customers/search")
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry, {"customerName": "张三"}),
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
        json={"query": "按姓名查询张三客户"},
        headers={"X-Trace-Id": "trace-query-post-001"},
    )

    assert response.status_code == 200
    assert response.json()["execution_status"] == "SUCCESS"


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
            json={"query": "帮我处理那个事情", "conversation_id": "conv_degrade_001"},
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
    assert "interaction_id=ia-degrade-001" in caplog.text
    assert "conversation_id=conv_degrade_001" in caplog.text
    assert "phase=http_adapter" in caplog.text


def test_runtime_metadata_endpoint_returns_contract(monkeypatch) -> None:
    stub_catalog_service = StubUICatalogService()
    monkeypatch.setattr(api_query_routes, "_get_ui_catalog_service", lambda: stub_catalog_service)

    client = TestClient(create_test_app())
    response = client.get("/api/v1/api-query/runtime-metadata")

    assert response.status_code == 200
    body = response.json()
    action_codes = {item["code"] for item in body["ui_runtime"]["ui_actions"]}
    assert action_codes == {"remoteQuery", "remoteMutation"}
    assert "PlannerForm" in body["ui_runtime"]["components"]
    template_codes = {item["code"] for item in body["template_scenarios"]}
    assert template_codes == {"custom_template"}
    assert body["ui_runtime"]["list"]["route_url"] == "/api/v1/api-query"
    assert body["ui_runtime"]["detail"]["request"]["param_source"] == "queryParams"
    assert body["ui_runtime"]["form"]["route_url"] is None
    assert body["ui_runtime"]["form"]["ui_action"] == "remoteMutation"
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
    assert body["ui_runtime"]["list"]["enabled"] is False
    assert body["ui_runtime"]["detail"]["enabled"] is False
    assert body["ui_runtime"]["form"]["enabled"] is False
    root_id = body["ui_spec"]["root"]
    notice = body["ui_spec"]["elements"]["child_1"]
    assert body["ui_spec"]["elements"][root_id]["type"] == "PlannerCard"
    assert notice["type"] == "PlannerNotice"
    assert "已冻结当前操作视图" in notice["props"]["text"]


def test_api_query_enriches_form_runtime_from_generated_spec(monkeypatch) -> None:
    query_entry = _make_entry()
    mutation_entry = _make_entry(
        id="customer_update",
        method="POST",
        operation_safety="mutation",
        path="/api/v1/customers/update",
        detail_hint=ApiCatalogDetailHint(enabled=False),
        pagination_hint=ApiCatalogPaginationHint(enabled=False),
        template_hint=ApiCatalogTemplateHint(enabled=False),
        param_schema={
            "type": "object",
            "properties": {
                "customerId": {"type": "string"},
                "industry": {"type": "string"},
            },
            "required": ["customerId", "industry"],
        },
    )
    stub_services = (
        StubRetriever(query_entry),
        StubExtractor(query_entry, {"customerId": "C001"}, business_intents=["saveToServer"]),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "customerName": "张三"}],
                total=1,
            )
        ),
        FormRuntimeDynamicUI(),
        StubSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(
        api_query_routes,
        "_get_registry_source",
        lambda: StubRegistrySource({"customer_list": query_entry, "customer_update": mutation_entry}),
    )

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={"query": "把客户 C001 的行业改成医疗"},
        headers={"X-Trace-Id": "trace-form-001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ui_runtime"]["form"]["enabled"] is True
    assert body["ui_runtime"]["form"]["api_id"] == "customer_update"
    assert body["ui_runtime"]["form"]["route_url"] == "/api/v1/customers/update"
    assert body["ui_runtime"]["form"]["mode"] == "edit"
    assert body["ui_runtime"]["form"]["state_path"] == "/form"
    assert body["ui_runtime"]["form"]["submit"]["business_intent"] == "saveToServer"
    fields = {field["submit_key"]: field for field in body["ui_runtime"]["form"]["fields"]}
    assert fields["customerId"]["source_kind"] == "context"
    assert fields["customerId"]["writable"] is False
    assert fields["industry"]["source_kind"] == "dictionary"
    assert fields["industry"]["option_source"] == {"type": "dict", "dict_code": "industry"}
