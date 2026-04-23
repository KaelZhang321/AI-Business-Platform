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
from app.services.api_catalog.schema import ApiCatalogDetailHint, ApiCatalogEntry, ApiCatalogSearchResult


class StubRetriever:
    def __init__(self, entry: ApiCatalogEntry) -> None:
        self._entry = entry
        self.last_filters = None

    async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
        self.last_filters = filters
        return [ApiCatalogSearchResult(entry=self._entry, score=0.95)]

    async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
        return await self.search(query, top_k=top_k, score_threshold=0.3, filters=filters)


class MultiStubRetriever:
    def __init__(self, entries: list[ApiCatalogEntry]) -> None:
        self._entries = entries

    async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
        return [ApiCatalogSearchResult(entry=entry, score=0.95) for entry in self._entries]

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


class MutationExtractor(StubExtractor):
    """为 mutation confirm 场景返回写意图和预填参数。"""

    async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            query_domains=[self._entry.domain],
            business_intents=["saveToServer"],
            is_multi_domain=False,
            reasoning="runtime mutation route",
            route_status="ok",
        )

    async def extract_routing_result(self, query: str, candidates, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            selected_api_id=self._entry.id,
            query_domains=[self._entry.domain],
            business_intents=["saveToServer"],
            params={"id": "8058", "email": "437462373467289@qq.com"},
        )


class CreateMutationExtractor(StubExtractor):
    """为创建类 mutation 场景返回选中的创建接口与预填参数。"""

    async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            query_domains=[self._entry.domain],
            business_intents=["saveToServer"],
            is_multi_domain=False,
            reasoning="runtime create-mutation route",
            route_status="ok",
        )

    async def extract_routing_result(self, query: str, candidates, user_context: dict[str, object], **kwargs):
        return ApiQueryRoutingResult(
            selected_api_id=self._entry.id,
            query_domains=[self._entry.domain],
            business_intents=["saveToServer"],
            params={},
        )


class StubExecutor:
    def __init__(self, result: ApiQueryExecutionResult) -> None:
        self._result = result

    async def call(self, entry, params, user_token=None, trace_id: str | None = None, user_id: str | None = None):
        return self._result.model_copy(update={"trace_id": trace_id})


class PassThroughSnapshotService:
    def should_capture(self, business_intents):
        return False


class StubRegistrySource:
    def __init__(self, entry: ApiCatalogEntry | dict[str, ApiCatalogEntry] | None) -> None:
        self._entry = entry

    async def get_entry_by_id(self, api_id: str) -> ApiCatalogEntry | None:
        if isinstance(self._entry, dict):
            return self._entry.get(api_id)
        return self._entry


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_query_routes.router, prefix="/api/v1")
    return app


def _make_entry() -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/v1/customers",
    )


def _make_mutation_entry() -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id="employee_update",
        description="修改员工",
        domain="iam",
        operation_safety="mutation",
        method="POST",
        path="/system/employee/sys-employee/update",
        param_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "title": "员工ID"},
                "email": {"type": "string", "title": "邮箱"},
                "realName": {"type": "string", "title": "姓名"},
                "mobile": {"type": "string", "title": "手机号"},
                "createTime": {"type": "string", "title": "创建时间"},
                "updateTime": {"type": "string", "title": "更新时间"},
            },
            "required": ["id", "email", "realName"],
        },
    )


def _make_create_mutation_entry() -> ApiCatalogEntry:
    return ApiCatalogEntry(
        id="role_create",
        description="新增角色",
        domain="iam",
        operation_safety="mutation",
        method="POST",
        path="/system/role/create",
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
    )


def _get_root_element(spec: dict[str, object]) -> dict[str, object]:
    """读取 flat spec 的根元素。

    功能：
        任务 1 之后 `api_query` 的 `ui_spec` 统一切换为 `root/state/elements`。测试层也必须
        改成消费新契约，避免继续把旧树形结构当成事实标准。
    """
    root_id = spec["root"]
    elements = spec["elements"]
    assert isinstance(root_id, str)
    assert isinstance(elements, dict)
    root_element = elements[root_id]
    assert isinstance(root_element, dict)
    return root_element


def _get_root_children(spec: dict[str, object]) -> list[dict[str, object]]:
    """按根节点 children 顺序取回子元素列表。"""
    root_element = _get_root_element(spec)
    elements = spec["elements"]
    assert isinstance(elements, dict)
    child_ids = root_element.get("children", [])
    assert isinstance(child_ids, list)
    children: list[dict[str, object]] = []
    for child_id in child_ids:
        assert isinstance(child_id, str)
        child = elements[child_id]
        assert isinstance(child, dict)
        children.append(child)
    return children


def _get_child_by_type(spec: dict[str, object], expected_type: str) -> dict[str, object]:
    """按组件类型查找根卡片下的直接子元素。"""
    for child in _get_root_children(spec):
        if child.get("type") == expected_type:
            return child
    raise AssertionError(f"missing child type: {expected_type}")


def _assert_api_query_response_keys(body: dict[str, object]) -> None:
    """断言 `/api-query` 仅暴露收口后的对外字段。"""

    assert set(body.keys()) == {"trace_id", "execution_status", "execution_plan", "ui_spec", "error"}


def _assert_runtime_metadata(
    payload: dict[str, object],
    *,
    trace_id: str,
    api_suffix: str | None = None,
) -> None:
    """断言 ui_spec 节点已携带前端二跳请求所需元数据。"""

    if api_suffix is not None:
        assert payload["api"] == f"/api/v1/ui-builder/runtime/endpoints/{api_suffix}/invoke"
    assert "queryParams" in payload
    assert "body" in payload
    assert payload["flowNum"] == trace_id
    assert "createdBy" in payload


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
    _assert_api_query_response_keys(body)
    assert body["execution_status"] == "EMPTY"
    assert body["execution_plan"]["steps"][0]["step_id"] == "step_customer_list"
    notice = _get_root_children(body["ui_spec"])[0]
    assert body["ui_spec"]["root"] == "root"
    assert notice["type"] == "PlannerNotice"
    assert notice["props"]["tone"] == "info"


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
    _assert_api_query_response_keys(body)
    assert body["execution_status"] == "ERROR"
    assert body["error"] == "业务接口超时"
    assert body["execution_plan"]["steps"][0]["step_id"] == "step_customer_list"
    notice = _get_root_children(body["ui_spec"])[0]
    assert notice["type"] == "PlannerNotice"
    assert notice["props"]["tone"] == "info"


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
    _assert_api_query_response_keys(body)
    assert body["execution_status"] == "SKIPPED"
    assert body["error"] == "缺少必要参数：customerId"
    assert body["execution_plan"]["steps"][0]["step_id"] == "step_customer_list"
    notice = _get_root_children(body["ui_spec"])[0]
    assert notice["type"] == "PlannerNotice"
    assert notice["props"]["text"] == "由于缺少必要参数 customerId，当前查询未被执行。"


def test_api_query_renders_mutation_form_instead_of_skipped_notice(monkeypatch) -> None:
    """真实 DynamicUIService 下，mutation confirm 必须渲染 PlannerForm。"""

    entry = _make_mutation_entry()
    stub_services = (
        StubRetriever(entry),
        MutationExtractor(entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[],
                total=0,
            )
        ),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={"query": "修改员工8058的邮箱为437462373467289@qq.com"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "SKIPPED"
    form = _get_child_by_type(body["ui_spec"], "PlannerForm")
    assert form["props"]["formCode"] == "employee_update_form"
    _assert_runtime_metadata(form["props"], trace_id=body["trace_id"], api_suffix="employee_update")
    assert body["ui_spec"]["state"]["form"]["id"] == "8058"
    assert body["ui_spec"]["state"]["form"]["email"] == "437462373467289@qq.com"
    assert body["ui_spec"]["state"]["form"]["realName"] is None
    assert body["ui_spec"]["state"]["form"]["mobile"] is None
    metric = body["ui_spec"]["elements"]["form_field_1"]
    assert metric["props"]["value"] == "8058"
    assert metric["props"]["required"] is True
    assert body["ui_spec"]["elements"]["form_field_2"]["props"]["required"] is True
    assert body["ui_spec"]["elements"]["form_field_3"]["props"]["required"] is True
    assert body["ui_spec"]["elements"]["form_field_4"]["props"]["required"] is False
    submit = body["ui_spec"]["elements"]["form_submit"]["on"]["press"]["params"]
    assert submit["api_id"] == "employee_update"
    _assert_runtime_metadata(submit, trace_id=body["trace_id"], api_suffix="employee_update")
    assert submit["body"]["email"] == {"$bindState": "/form/email"}
    assert submit["body"]["id"] == {"$bindState": "/form/id"}
    root_children = _get_root_children(body["ui_spec"])
    assert all(child["type"] != "PlannerNotice" for child in root_children)


def test_api_query_write_intent_with_multiple_mutations_still_renders_selected_create_form(monkeypatch) -> None:
    """多 mutation 候选时，只要选中了创建接口，就不能退化成安全拦截 Notice。"""

    update_entry = _make_mutation_entry()
    create_entry = _make_create_mutation_entry()
    stub_services = (
        MultiStubRetriever([update_entry, create_entry]),
        CreateMutationExtractor(create_entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[],
                total=0,
            )
        ),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/api-query",
        json={"query": "新增一个健管师角色"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "SKIPPED"
    assert body["error"] is None
    assert body["ui_spec"]["state"]["form"]["roleName"] == "健管师"
    assert body["execution_plan"]["steps"][0]["params"]["roleName"] == "健管师"
    form = _get_child_by_type(body["ui_spec"], "PlannerForm")
    assert form["props"]["formCode"] == "role_create_form"
    _assert_runtime_metadata(form["props"], trace_id=body["trace_id"], api_suffix="role_create")
    submit = body["ui_spec"]["elements"]["form_submit"]["on"]["press"]["params"]
    assert submit["api_id"] == "role_create"
    _assert_runtime_metadata(submit, trace_id=body["trace_id"], api_suffix="role_create")
    root_children = _get_root_children(body["ui_spec"])
    assert all(child["type"] != "PlannerNotice" for child in root_children)


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
    _assert_api_query_response_keys(body)
    assert body["execution_plan"]["steps"][0]["step_id"] == "step_customer_list"
    children = _get_root_children(body["ui_spec"])
    assert [child["type"] for child in children] == ["PlannerForm", "PlannerTable", "PlannerPagination"]
    table = children[1]
    pagination = children[2]
    assert table["props"]["columns"][0]["dataIndex"] == "customerId"
    assert len(table["props"]["dataSource"]) == 5
    _assert_runtime_metadata(table["props"], trace_id=body["trace_id"], api_suffix="customer_list")
    _assert_runtime_metadata(pagination["props"], trace_id=body["trace_id"], api_suffix="customer_list")
    assert pagination["props"]["total"] == 20


def test_api_query_renders_single_object_as_detail_card(monkeypatch) -> None:
    entry = _make_entry()
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data={"customerId": "C001", "customerName": "张三", "level": "VIP"},
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
    _assert_api_query_response_keys(body)
    assert body["execution_plan"]["steps"][0]["step_id"] == "step_customer_list"
    detail_card = _get_child_by_type(body["ui_spec"], "PlannerDetailCard")
    assert detail_card["props"]["title"] == "查询客户列表"
    assert {"label": "customerId", "value": "C001"} in detail_card["props"]["items"]
    assert {"label": "level", "value": "VIP"} in detail_card["props"]["items"]
    _assert_runtime_metadata(detail_card["props"], trace_id=body["trace_id"], api_suffix="customer_list")


def test_api_query_detail_card_uses_detail_request_schema_keys(monkeypatch) -> None:
    entry = _make_entry()
    entry.detail_hint = ApiCatalogDetailHint(
        enabled=True,
        api_id="customer_detail",
        identifier_field="customerId",
        query_param="legacyId",
    )
    detail_entry = ApiCatalogEntry(
        id="customer_detail",
        description="查询客户详情",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/v1/customers/detail",
        param_schema={
            "type": "object",
            "properties": {
                "customerId": {"type": "string"},
            },
            "required": ["customerId"],
        },
    )
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data={"customerId": "C001", "customerName": "张三"},
                total=1,
            )
        ),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(
        api_query_routes,
        "_get_registry_source",
        lambda: StubRegistrySource({"customer_detail": detail_entry}),
    )

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询客户详情"})

    assert response.status_code == 200
    body = response.json()
    detail_card = _get_child_by_type(body["ui_spec"], "PlannerDetailCard")
    assert detail_card["props"]["queryParams"] == {"customerId": "C001"}
    assert detail_card["props"]["body"] == {}
    assert "legacyId" not in detail_card["props"]["queryParams"]


def test_api_query_executes_multi_step_plan_and_returns_multi_step_context_pool(monkeypatch) -> None:
    customer_entry = ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        operation_safety="query",
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
        operation_safety="query",
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
        async def build_plan(self, query, candidates, user_context, route_hint, **kwargs):
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
        async def call(self, entry, params, user_token=None, trace_id: str | None = None, user_id: str | None = None):
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
    _assert_api_query_response_keys(body)
    assert body["execution_plan"]["plan_id"] == "dag_customer_orders"
    assert [step["step_id"] for step in body["execution_plan"]["steps"]] == ["step_customers", "step_orders"]
    assert [step["api_id"] for step in body["execution_plan"]["steps"]] == ["customer_list", "order_stats"]
    assert body["execution_status"] == "SUCCESS"
    assert body["ui_spec"]["root"] == "root"
    assert isinstance(body["ui_spec"]["elements"], dict)
    children = _get_root_children(body["ui_spec"])
    assert [child["type"] for child in children] == ["PlannerForm", "PlannerTable", "PlannerPagination"]
    table = children[1]
    assert table["props"]["columns"][0]["dataIndex"] == "stepId"


def test_api_query_renders_partial_success_with_notice_and_table(monkeypatch) -> None:
    customer_entry = ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        operation_safety="query",
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
        operation_safety="query",
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
                reasoning="partial-success runtime test",
                route_status="ok",
            )

    class PlannerStub:
        async def build_plan(self, query, candidates, user_context, route_hint, **kwargs):
            return ApiQueryExecutionPlan(
                plan_id="dag_customer_orders_partial",
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

    class PartialExecutor:
        async def call(self, entry, params, user_token=None, trace_id: str | None = None, user_id: str | None = None):
            if entry.id == "customer_list":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"customerId": "C001", "customerName": "张三"}],
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.ERROR,
                data=None,
                total=0,
                error="ERP 服务超时",
                trace_id=trace_id,
            )

    stub_services = (
        MultiRetriever(),
        RouteOnlyExtractor(),
        PartialExecutor(),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_planner", lambda: PlannerStub())

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查我的客户，并看他们的订单统计"})

    assert response.status_code == 200
    body = response.json()
    _assert_api_query_response_keys(body)
    assert body["execution_plan"]["plan_id"] == "dag_customer_orders_partial"
    assert body["execution_status"] == "PARTIAL_SUCCESS"
    root = _get_root_element(body["ui_spec"])
    assert "部分步骤执行失败" in root["props"]["subtitle"]
    table = _get_root_children(body["ui_spec"])[1]
    assert table["props"]["dataSource"][0]["stepId"] == "step_customers"


def test_api_query_returns_error_response_when_execution_graph_fails(monkeypatch) -> None:
    entry = ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/v1/customers",
        param_schema={
            "type": "object",
            "properties": {"owner_id": {"type": "string"}},
            "required": ["owner_id"],
        },
    )

    class SingleRetriever:
        async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
            return [ApiCatalogSearchResult(entry=entry, score=0.95)]

        async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
            return await self.search(query, top_k=top_k, score_threshold=0.3, filters=filters)

    class SingleExtractor:
        async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
            return ApiQueryRoutingResult(
                query_domains=["crm"],
                business_intents=["none"],
                is_multi_domain=False,
                reasoning="graph failure runtime test",
                route_status="ok",
            )

        async def extract_routing_result(self, query: str, candidates, user_context: dict[str, object], **kwargs):
            return ApiQueryRoutingResult(
                selected_api_id=entry.id,
                query_domains=["crm"],
                business_intents=["none"],
                params={"owner_id": "E8899"},
            )

    class PlannerStub:
        async def build_plan(self, query, candidates, user_context, route_hint, **kwargs):
            return ApiQueryExecutionPlan(
                plan_id="dag_graph_failed_runtime",
                steps=[
                    ApiQueryPlanStep(
                        step_id="step_customers",
                        api_path="/api/v1/customers",
                        params={"owner_id": "E8899"},
                        depends_on=[],
                    )
                ],
                )

        def validate_plan(self, plan, candidates):
            return {"step_customer_list": entry}

    class BrokenExecutor:
        async def call(self, entry, params, user_token=None, trace_id: str | None = None, user_id: str | None = None):
            raise RuntimeError("executor exploded in runtime test")

    stub_services = (
        SingleRetriever(),
        SingleExtractor(),
        BrokenExecutor(),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_planner", lambda: PlannerStub())

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查我的客户"})

    assert response.status_code == 200
    body = response.json()
    assert body["execution_plan"]["plan_id"].startswith("dag_")
    assert body["execution_status"] == "ERROR"
    assert "执行图运行失败" in body["error"]
    notice = _get_child_by_type(body["ui_spec"], "PlannerNotice")
    assert "执行图运行失败" in notice["props"]["text"]
