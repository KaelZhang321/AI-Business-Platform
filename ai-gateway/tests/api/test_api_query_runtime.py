from __future__ import annotations

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import api_query as api_query_routes
from app.api import dependencies as api_dependencies
from app.core.config import settings
from app.services.api_catalog.business_intents import BusinessIntentCatalogService, set_business_intent_catalog_service
from app.services.ui_catalog_service import UICatalogService
from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryPlanStep,
    ApiQueryRoutingResult,
)
from app.services.api_catalog.schema import ApiCatalogDetailHint, ApiCatalogEntry, ApiCatalogPaginationHint, ApiCatalogSearchResult


class StubAppResources:
    """API 路由测试只注入当前接口依赖的资源桩。"""

    def __init__(self) -> None:
        self.ui_catalog_service = UICatalogService()
        self.api_catalog_registry_source = StubRegistrySource(None)


def _reset_api_query_singletons() -> None:
    api_query_routes._workflow = None
    api_query_routes._retriever = None
    api_query_routes._extractor = None
    api_query_routes._executor = None
    api_query_routes._planner = None
    api_query_routes._dynamic_ui = None
    api_query_routes._snapshot_service = None


def _get_test_resources() -> StubAppResources:
    return StubAppResources()


def _install_test_dependencies(app: FastAPI) -> None:
    resources = _get_test_resources()
    app.dependency_overrides[api_dependencies.get_app_resource_container] = lambda: resources


@pytest.fixture(autouse=True)
def api_query_runtime_test_fixture():
    """API 路由测试显式注入进程级目录服务，并隔离 route 单例缓存。"""

    _reset_api_query_singletons()
    set_business_intent_catalog_service(BusinessIntentCatalogService())
    yield
    set_business_intent_catalog_service(None)
    _reset_api_query_singletons()


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
    _install_test_dependencies(app)
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
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "customerId": {"type": "string", "description": "客户编号"},
                            "customerName": {"type": "string", "description": "客户姓名"},
                            "level": {"type": "string", "description": "客户等级"},
                        },
                    },
                }
            },
        },
        response_data_path="data",
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


def _children_of(spec: dict[str, object], element: dict[str, object]) -> list[dict[str, object]]:
    """按元素 children 顺序取回直接子元素。"""
    elements = spec["elements"]
    assert isinstance(elements, dict)
    child_ids = element.get("children", [])
    assert isinstance(child_ids, list)
    children: list[dict[str, object]] = []
    for child_id in child_ids:
        assert isinstance(child_id, str)
        child = elements[child_id]
        assert isinstance(child, dict)
        children.append(child)
    return children


def _get_root_children(spec: dict[str, object]) -> list[dict[str, object]]:
    """返回业务卡片内的直接子元素，兼容根空容器结构。"""
    root_children = _children_of(spec, _get_root_element(spec))
    if len(root_children) == 1 and root_children[0].get("type") == "PlannerCard":
        return _children_of(spec, root_children[0])
    return root_children


def _get_child_by_type(spec: dict[str, object], expected_type: str) -> dict[str, object]:
    """按组件类型递归查找元素。"""
    elements = spec["elements"]
    assert isinstance(elements, dict)
    for element in elements.values():
        assert isinstance(element, dict)
        if element.get("type") == expected_type:
            return element
    raise AssertionError(f"missing child type: {expected_type}")


def _get_first_card(spec: dict[str, object]) -> dict[str, object]:
    """读取根空容器下第一张业务卡片。"""
    for child in _children_of(spec, _get_root_element(spec)):
        if child.get("type") == "PlannerCard":
            return child
    raise AssertionError("missing PlannerCard")


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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询客户详情"})

    assert response.status_code == 200
    body = response.json()
    _assert_api_query_response_keys(body)
    assert body["execution_plan"]["steps"][0]["step_id"] == "step_customer_list"
    detail_card = _get_child_by_type(body["ui_spec"], "PlannerInfoGrid")
    assert detail_card["props"]["title"] == "查询客户列表"
    assert {"label": "客户编号", "value": "C001"} in detail_card["props"]["items"]
    assert {"label": "客户等级", "value": "VIP"} in detail_card["props"]["items"]
    _assert_runtime_metadata(detail_card["props"], trace_id=body["trace_id"], api_suffix="customer_list")


def test_api_query_renders_composite_single_object_as_metrics_and_tables(monkeypatch) -> None:
    entry = _make_entry()
    entry.response_schema = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "properties": {
                    "summaryCard": {
                        "type": "object",
                        "properties": {
                            "storeLeftFunds": {"type": "number", "description": "可用储值余额"},
                            "storeFundCount": {"type": "integer", "description": "储值方案数"},
                        },
                    },
                    "deliveryRecords": {
                        "type": "array",
                        "description": "交付记录",
                        "items": {
                            "type": "object",
                            "properties": {
                                "deliveryDate": {"type": "string", "description": "交付日期"},
                                "deliveryProject": {"type": "string", "description": "交付项目"},
                                "deliveryAmount": {"type": "number", "description": "交付金额"},
                            },
                        },
                    },
                    "curePlanRecords": {
                        "type": "array",
                        "description": "调理方案记录",
                        "items": {
                            "type": "object",
                            "properties": {
                                "fcreateTime": {"type": "string", "description": "创建时间"},
                                "fproductBillProjectName": {"type": "string", "description": "方案名称"},
                                "fprojectAmount": {"type": "number", "description": "方案金额"},
                            },
                        },
                    },
                },
            }
        },
    }
    entry.response_data_path = "data"
    stub_services = (
        StubRetriever(entry),
        StubExtractor(entry),
        StubExecutor(
            ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data={
                    "summaryCard": {"storeLeftFunds": 13245060.0, "storeFundCount": 12},
                    "deliveryRecords": [
                        {"deliveryDate": "2024-10-01T00:00", "deliveryProject": "肝脏解毒支持（白金版）", "deliveryAmount": 27103.46}
                    ],
                    "curePlanRecords": [
                        {"fcreateTime": "2024-11-20T09:44", "fproductBillProjectName": "免疫力改善-C治疗", "fprojectAmount": 298000.0}
                    ],
                },
                total=1,
            )
        ),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询刘海坚的储值方案"})

    assert response.status_code == 200
    body = response.json()
    _assert_api_query_response_keys(body)
    children = _get_root_children(body["ui_spec"])
    child_types = [child["type"] for child in children]
    assert "PlannerInfoGrid" in child_types
    assert child_types.count("PlannerTable") >= 2
    assert "PlannerDetailCard" not in child_types

    info_grid = next(child for child in children if child["type"] == "PlannerInfoGrid")
    metric_pairs = {(item["label"], item["value"]) for item in info_grid["props"]["items"]}
    assert ("可用储值余额", "13245060.0") in metric_pairs
    assert info_grid["props"]["bizFieldKey"] == "summaryCard"

    delivery_table = next(child for child in children if child["type"] == "PlannerTable" and child["props"].get("title") == "交付记录")
    assert delivery_table["props"]["bizFieldKey"] == "deliveryRecords"
    assert delivery_table["props"]["columns"][0]["title"] == "交付日期"
    assert delivery_table["props"]["dataSource"][0]["deliveryProject"] == "肝脏解毒支持（白金版）"
    cure_plan_table = next(child for child in children if child["type"] == "PlannerTable" and child["props"].get("title") == "调理方案记录")
    assert cure_plan_table["props"]["bizFieldKey"] == "curePlanRecords"
    # 纯单接口详情场景未启用列表 runtime，因此 composite 表格不会挂载二跳接口地址。
    assert delivery_table["props"]["api"] == ""
    _assert_runtime_metadata(delivery_table["props"], trace_id=body["trace_id"], api_suffix=None)


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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)

    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_api_catalog_registry_source] = lambda: StubRegistrySource(
        {"customer_detail": detail_entry}
    )
    client = TestClient(app)
    response = client.post("/api/v1/api-query", json={"query": "查询客户详情"})

    assert response.status_code == 200
    body = response.json()
    detail_card = _get_child_by_type(body["ui_spec"], "PlannerInfoGrid")
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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)
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
    assert table["props"]["columns"][0]["dataIndex"] == "customerId"
    assert table["props"]["dataSource"][0]["orderCount"] == 3


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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_planner", lambda: PlannerStub())

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查我的客户，并看他们的订单统计"})

    assert response.status_code == 200
    body = response.json()
    _assert_api_query_response_keys(body)
    assert body["execution_plan"]["plan_id"] == "dag_customer_orders_partial"
    assert body["execution_status"] == "PARTIAL_SUCCESS"
    root = _get_root_element(body["ui_spec"])
    assert root["type"] == "PlannerBlankContainer"
    card = _get_first_card(body["ui_spec"])
    assert "部分步骤执行失败" in card["props"]["subtitle"]
    table = _get_root_children(body["ui_spec"])[1]
    assert table["props"]["dataSource"][0]["customerId"] == "C001"


def test_api_query_multi_step_can_fallback_to_summary_table_via_policy(monkeypatch) -> None:
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
                reasoning="summary policy runtime test",
                route_status="ok",
            )

    class PlannerStub:
        async def build_plan(self, query, candidates, user_context, route_hint, **kwargs):
            return ApiQueryExecutionPlan(
                plan_id="dag_customer_orders_summary",
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
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"customerId": "C001", "customerName": "张三"}],
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"customerId": "C001", "orderCount": 3}],
                total=1,
                trace_id=trace_id,
            )

    monkeypatch.setattr(settings, "api_query_multi_step_render_policy", "summary_table")
    stub_services = (
        MultiRetriever(),
        RouteOnlyExtractor(),
        MultiStepExecutor(),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_planner", lambda: PlannerStub())

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查我的客户，并看他们的订单统计"})

    assert response.status_code == 200
    body = response.json()
    table = _get_root_children(body["ui_spec"])[1]
    assert table["props"]["dataSource"][0]["stepId"] == "step_customers"


def test_api_query_multi_step_can_render_aggregate_sections(monkeypatch) -> None:
    customer_entry = ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/v1/customers",
        param_schema={
            "type": "object",
            "properties": {"customerInfo": {"type": "string"}},
            "required": ["customerInfo"],
        },
    )
    health_basic_entry = ApiCatalogEntry(
        id="health_basic",
        description="健康基本信息",
        domain="health",
        operation_safety="query",
        method="GET",
        path="/leczcore-data-manage/dwCustomerArchive/healthBasic",
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "bloodType": {"type": "string", "description": "血型"},
                        },
                    },
                }
            },
        },
        response_data_path="data",
        param_schema={
            "type": "object",
            "properties": {"encryptedIdCard": {"type": "string"}},
            "required": ["encryptedIdCard"],
        },
    )
    health_history_entry = ApiCatalogEntry(
        id="health_history",
        description="病史",
        domain="health",
        operation_safety="query",
        method="GET",
        path="/leczcore-data-manage/dwCustomerArchive/healthStatusMedicalHistory",
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "history": {"type": "string", "description": "既往史"},
                        },
                    },
                }
            },
        },
        response_data_path="data",
        param_schema={
            "type": "object",
            "properties": {"encryptedIdCard": {"type": "string"}},
            "required": ["encryptedIdCard"],
        },
    )
    physical_exam_entry = ApiCatalogEntry(
        id="physical_exam",
        description="体检情况",
        domain="health",
        operation_safety="query",
        method="GET",
        path="/leczcore-data-manage/dwCustomerArchive/physicalExam",
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "latestExamDate": {"type": "string", "description": "最近体检时间"},
                        },
                    },
                }
            },
        },
        response_data_path="data",
        param_schema={
            "type": "object",
            "properties": {"encryptedIdCard": {"type": "string"}},
            "required": ["encryptedIdCard"],
        },
    )

    class MultiRetriever:
        async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
            return [
                ApiCatalogSearchResult(entry=customer_entry, score=0.95),
                ApiCatalogSearchResult(entry=health_basic_entry, score=0.94),
                ApiCatalogSearchResult(entry=health_history_entry, score=0.93),
                ApiCatalogSearchResult(entry=physical_exam_entry, score=0.92),
            ]

        async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
            return await self.search(query, top_k=top_k, score_threshold=0.3, filters=filters)

    class RouteOnlyExtractor:
        async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
            return ApiQueryRoutingResult(
                query_domains=["crm", "health"],
                business_intents=["none"],
                is_multi_domain=True,
                reasoning="aggregate policy runtime test",
                route_status="ok",
            )

    class PlannerStub:
        async def build_plan(self, query, candidates, user_context, route_hint, **kwargs):
            return ApiQueryExecutionPlan(
                plan_id="dag_liuhaijian_health",
                steps=[
                    ApiQueryPlanStep(
                        step_id="step_get_customer",
                        api_id="customer_list",
                        api_path=customer_entry.path,
                        params={"customerInfo": "刘海坚", "pageNo": 1, "pageSize": 10},
                        depends_on=[],
                    ),
                    ApiQueryPlanStep(
                        step_id="step_health_basic",
                        api_id="health_basic",
                        api_path=health_basic_entry.path,
                        params={"encryptedIdCard": "$[step_get_customer.data][*].idCard"},
                        depends_on=["step_get_customer"],
                    ),
                    ApiQueryPlanStep(
                        step_id="step_health_history",
                        api_id="health_history",
                        api_path=health_history_entry.path,
                        params={"encryptedIdCard": "$[step_get_customer.data][*].idCard"},
                        depends_on=["step_get_customer"],
                    ),
                    ApiQueryPlanStep(
                        step_id="step_physical_exam",
                        api_id="physical_exam",
                        api_path=physical_exam_entry.path,
                        params={"encryptedIdCard": "$[step_get_customer.data][*].idCard"},
                        depends_on=["step_get_customer"],
                    ),
                ],
            )

        def validate_plan(self, plan, candidates):
            return {
                "step_get_customer": customer_entry,
                "step_health_basic": health_basic_entry,
                "step_health_history": health_history_entry,
                "step_physical_exam": physical_exam_entry,
            }

    class MultiStepExecutor:
        async def call(self, entry, params, user_token=None, trace_id: str | None = None, user_id: str | None = None):
            if entry.id == "customer_list":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"idCard": "ENC001", "customerName": "刘海坚"}],
                    total=1,
                    trace_id=trace_id,
                )
            if entry.id == "health_basic":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"bloodType": "A型"}],
                    total=1,
                    trace_id=trace_id,
                )
            if entry.id == "health_history":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"history": "高血压"}],
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"latestExamDate": "2025-04-08"}],
                total=1,
                trace_id=trace_id,
            )

    monkeypatch.setattr(settings, "api_query_multi_step_render_policy", "aggregate_result")
    stub_services = (
        MultiRetriever(),
        RouteOnlyExtractor(),
        MultiStepExecutor(),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_planner", lambda: PlannerStub())

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询客户刘海坚的健康数据"})

    assert response.status_code == 200
    body = response.json()
    _assert_api_query_response_keys(body)
    children = _get_root_children(body["ui_spec"])
    info_grids = [child for child in children if child["type"] == "PlannerInfoGrid"]
    assert len(info_grids) == 3

    # 聚合模式下详情型子块使用信息网格，并保留稳定 bizFieldKey 供前端映射。
    assert {grid["props"]["bizFieldKey"] for grid in info_grids} == {
        "healthBasic",
        "healthStatusMedicalHistory",
        "physicalExam",
    }
    titles = {grid["props"]["title"] for grid in info_grids}
    assert {"健康基本信息", "病史", "体检情况"} <= titles
    runtime_api_suffix_by_section = {
        "healthBasic": "health_basic",
        "healthStatusMedicalHistory": "health_history",
        "physicalExam": "physical_exam",
    }
    for grid in info_grids:
        section_key = grid["props"]["bizFieldKey"]
        _assert_runtime_metadata(
            grid["props"],
            trace_id=body["trace_id"],
            api_suffix=runtime_api_suffix_by_section[section_key],
        )
        assert grid["props"]["queryParams"] == {"encryptedIdCard": "ENC001"}
        assert grid["props"]["body"] == {}


def test_api_query_multi_step_auto_policy_renders_aggregate_sections(monkeypatch) -> None:
    customer_entry = ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/v1/customers",
        param_schema={
            "type": "object",
            "properties": {"customerInfo": {"type": "string"}},
            "required": ["customerInfo"],
        },
    )
    health_basic_entry = ApiCatalogEntry(
        id="health_basic",
        description="健康基本信息",
        domain="health",
        operation_safety="query",
        method="GET",
        path="/leczcore-data-manage/dwCustomerArchive/healthBasic",
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "bloodType": {"type": "string", "description": "血型"},
                        },
                    },
                }
            },
        },
        response_data_path="data",
        param_schema={
            "type": "object",
            "properties": {"encryptedIdCard": {"type": "string"}},
            "required": ["encryptedIdCard"],
        },
    )
    health_history_entry = ApiCatalogEntry(
        id="health_history",
        description="病史",
        domain="health",
        operation_safety="query",
        method="GET",
        path="/leczcore-data-manage/dwCustomerArchive/healthStatusMedicalHistory",
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "history": {"type": "string", "description": "既往史"},
                        },
                    },
                }
            },
        },
        response_data_path="data",
        param_schema={
            "type": "object",
            "properties": {"encryptedIdCard": {"type": "string"}},
            "required": ["encryptedIdCard"],
        },
    )
    physical_exam_entry = ApiCatalogEntry(
        id="physical_exam",
        description="体检情况",
        domain="health",
        operation_safety="query",
        method="GET",
        path="/leczcore-data-manage/dwCustomerArchive/physicalExam",
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "latestExamDate": {"type": "string", "description": "最近体检时间"},
                        },
                    },
                }
            },
        },
        response_data_path="data",
        param_schema={
            "type": "object",
            "properties": {"encryptedIdCard": {"type": "string"}},
            "required": ["encryptedIdCard"],
        },
    )

    class MultiRetriever:
        async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
            return [
                ApiCatalogSearchResult(entry=customer_entry, score=0.95),
                ApiCatalogSearchResult(entry=health_basic_entry, score=0.94),
                ApiCatalogSearchResult(entry=health_history_entry, score=0.93),
                ApiCatalogSearchResult(entry=physical_exam_entry, score=0.92),
            ]

        async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
            return await self.search(query, top_k=top_k, score_threshold=0.3, filters=filters)

    class RouteOnlyExtractor:
        async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
            return ApiQueryRoutingResult(
                query_domains=["crm", "health"],
                business_intents=["none"],
                is_multi_domain=True,
                reasoning="auto policy runtime test",
                route_status="ok",
            )

    class PlannerStub:
        async def build_plan(self, query, candidates, user_context, route_hint, **kwargs):
            return ApiQueryExecutionPlan(
                plan_id="dag_liuhaijian_health_auto",
                steps=[
                    ApiQueryPlanStep(
                        step_id="step_get_customer",
                        api_id="customer_list",
                        api_path=customer_entry.path,
                        params={"customerInfo": "刘海坚", "pageNo": 1, "pageSize": 10},
                        depends_on=[],
                    ),
                    ApiQueryPlanStep(
                        step_id="step_health_basic",
                        api_id="health_basic",
                        api_path=health_basic_entry.path,
                        params={"encryptedIdCard": "$[step_get_customer.data][*].idCard"},
                        depends_on=["step_get_customer"],
                    ),
                    ApiQueryPlanStep(
                        step_id="step_health_history",
                        api_id="health_history",
                        api_path=health_history_entry.path,
                        params={"encryptedIdCard": "$[step_get_customer.data][*].idCard"},
                        depends_on=["step_get_customer"],
                    ),
                    ApiQueryPlanStep(
                        step_id="step_physical_exam",
                        api_id="physical_exam",
                        api_path=physical_exam_entry.path,
                        params={"encryptedIdCard": "$[step_get_customer.data][*].idCard"},
                        depends_on=["step_get_customer"],
                    ),
                ],
            )

        def validate_plan(self, plan, candidates):
            return {
                "step_get_customer": customer_entry,
                "step_health_basic": health_basic_entry,
                "step_health_history": health_history_entry,
                "step_physical_exam": physical_exam_entry,
            }

    class MultiStepExecutor:
        async def call(self, entry, params, user_token=None, trace_id: str | None = None, user_id: str | None = None):
            if entry.id == "customer_list":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"idCard": "ENC001", "customerName": "刘海坚"}],
                    total=1,
                    trace_id=trace_id,
                )
            if entry.id == "health_basic":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"bloodType": "A型"}],
                    total=1,
                    trace_id=trace_id,
                )
            if entry.id == "health_history":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"history": "高血压"}],
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"latestExamDate": "2025-04-08"}],
                total=1,
                trace_id=trace_id,
            )

    monkeypatch.setattr(settings, "api_query_multi_step_render_policy", "auto_result")
    stub_services = (
        MultiRetriever(),
        RouteOnlyExtractor(),
        MultiStepExecutor(),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_planner", lambda: PlannerStub())

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询客户刘海坚的健康数据"})

    assert response.status_code == 200
    body = response.json()
    _assert_api_query_response_keys(body)
    children = _get_root_children(body["ui_spec"])
    info_grids = [child for child in children if child["type"] == "PlannerInfoGrid"]
    assert len(info_grids) == 3
    assert {grid["props"]["bizFieldKey"] for grid in info_grids} == {
        "healthBasic",
        "healthStatusMedicalHistory",
        "physicalExam",
    }


def test_api_query_multi_step_aggregate_keeps_explicit_list_section_as_table(monkeypatch) -> None:
    customer_entry = ApiCatalogEntry(
        id="customer_list",
        description="查询客户列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/v1/customers",
        param_schema={
            "type": "object",
            "properties": {"customerInfo": {"type": "string"}},
            "required": ["customerInfo"],
        },
    )
    customer_tag_entry = ApiCatalogEntry(
        id="customer_tags",
        description="客户标签列表",
        domain="crm",
        operation_safety="query",
        method="GET",
        path="/api/v1/customer-tags",
        ui_hint="list",
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tagName": {"type": "string", "description": "标签名称"},
                            "tagLevel": {"type": "string", "description": "标签等级"},
                        },
                    },
                }
            },
        },
        response_data_path="data",
        param_schema={
            "type": "object",
            "properties": {"customerId": {"type": "string"}},
            "required": ["customerId"],
        },
        pagination_hint=ApiCatalogPaginationHint(enabled=True),
    )

    class MultiRetriever:
        async def search(self, query: str, top_k: int = 3, score_threshold: float = 0.3, filters=None):
            return [
                ApiCatalogSearchResult(entry=customer_entry, score=0.95),
                ApiCatalogSearchResult(entry=customer_tag_entry, score=0.94),
            ]

        async def search_stratified(self, query: str, *, domains, top_k: int = 3, filters=None, **kwargs):
            return await self.search(query, top_k=top_k, score_threshold=0.3, filters=filters)

    class RouteOnlyExtractor:
        async def route_query(self, query: str, user_context: dict[str, object], **kwargs):
            return ApiQueryRoutingResult(
                query_domains=["crm"],
                business_intents=["none"],
                is_multi_domain=True,
                reasoning="explicit list section runtime test",
                route_status="ok",
            )

    class PlannerStub:
        async def build_plan(self, query, candidates, user_context, route_hint, **kwargs):
            return ApiQueryExecutionPlan(
                plan_id="dag_customer_tag_list",
                steps=[
                    ApiQueryPlanStep(
                        step_id="step_get_customer",
                        api_id="customer_list",
                        api_path=customer_entry.path,
                        params={"customerInfo": "刘海坚"},
                        depends_on=[],
                    ),
                    ApiQueryPlanStep(
                        step_id="step_customer_tags",
                        api_id="customer_tags",
                        api_path=customer_tag_entry.path,
                        params={"customerId": "$[step_get_customer.data][*].customerId"},
                        depends_on=["step_get_customer"],
                    ),
                ],
            )

        def validate_plan(self, plan, candidates):
            return {
                "step_get_customer": customer_entry,
                "step_customer_tags": customer_tag_entry,
            }

    class MultiStepExecutor:
        async def call(self, entry, params, user_token=None, trace_id: str | None = None, user_id: str | None = None):
            if entry.id == "customer_list":
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.SUCCESS,
                    data=[{"customerId": "C001", "customerName": "刘海坚"}],
                    total=1,
                    trace_id=trace_id,
                )
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[{"tagName": "高净值", "tagLevel": "A"}],
                total=1,
                trace_id=trace_id,
            )

    monkeypatch.setattr(settings, "api_query_multi_step_render_policy", "aggregate_result")
    stub_services = (
        MultiRetriever(),
        RouteOnlyExtractor(),
        MultiStepExecutor(),
        api_query_routes.DynamicUIService(),
        PassThroughSnapshotService(),
    )
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)
    monkeypatch.setattr(api_query_routes, "_get_planner", lambda: PlannerStub())

    client = TestClient(create_test_app())
    response = client.post("/api/v1/api-query", json={"query": "查询客户刘海坚的标签"})

    assert response.status_code == 200
    body = response.json()
    children = _get_root_children(body["ui_spec"])
    tables = [child for child in children if child["type"] == "PlannerTable"]
    assert len(tables) == 1
    table = tables[0]
    assert table["props"]["bizFieldKey"] == "customer_tags"
    assert table["props"]["dataSource"] == [{"tagName": "高净值", "tagLevel": "A"}]
    _assert_runtime_metadata(table["props"], trace_id=body["trace_id"], api_suffix="customer_tags")
    assert table["props"]["queryParams"] == {"customerId": "C001"}


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
    monkeypatch.setattr(api_query_routes, "_get_services", lambda **_: stub_services)
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
