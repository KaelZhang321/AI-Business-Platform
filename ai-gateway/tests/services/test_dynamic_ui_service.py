from __future__ import annotations

import pytest

from app.core.config import settings
from app.models.schemas import (
    ApiQueryDetailRequestRuntime,
    ApiQueryDetailRuntime,
    ApiQueryExecutionStatus,
    ApiQueryFormFieldRuntime,
    ApiQueryFormRuntime,
    ApiQueryFormSubmitRuntime,
    ApiQueryDetailSourceRuntime,
    ApiQueryListPaginationRuntime,
    ApiQueryListQueryContextRuntime,
    ApiQueryListTableFieldRuntime,
    ApiQueryListRuntime,
    ApiQueryUIAction,
    ApiQueryUIRuntime,
)
from app.services.dynamic_ui_service import DynamicUIService
from app.services.ui_catalog_service import UICatalogService, UIActionDefinition


class RecordingLLM:
    """记录 Renderer 调用入参的测试替身。"""

    def __init__(self, replies: list[str] | None = None, *, fail_on_json_mode: bool = False) -> None:
        self._replies = list(replies or [])
        self._fail_on_json_mode = fail_on_json_mode
        self.calls: list[dict[str, object]] = []

    async def chat(self, messages, temperature=0.7, *, response_format=None, timeout_seconds=None) -> str:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "response_format": response_format,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self._fail_on_json_mode and response_format:
            raise RuntimeError("response_format unsupported")
        if not self._replies:
            return ""
        return self._replies.pop(0)


class StubUICatalogService:
    """为 Renderer Prompt 提供可控组件目录的测试替身。"""

    def get_component_catalog(self, *, intent: str | None = None, requested_codes=None) -> dict[str, str]:
        if intent == "query":
            return {
                "PlannerBlankContainer": "自定义空白容器说明",
                "PlannerCard": "自定义卡片说明",
                "PlannerInfoGrid": "自定义信息网格说明",
                "PlannerTable": "自定义表格说明",
                "PlannerPagination": "自定义分页说明",
                "PlannerForm": "自定义表单说明",
                "PlannerInput": "自定义输入框说明",
                "PlannerButton": "自定义按钮说明",
                "PlannerNotice": "自定义提示说明",
            }
        return {
            "Card": "通用卡片说明",
            "Table": "通用表格说明",
        }

    def get_component_codes(self, *, intent: str | None = None, requested_codes=None) -> list[str]:
        if intent == "query":
            return [
                "PlannerBlankContainer",
                "PlannerCard",
                "PlannerInfoGrid",
                "PlannerTable",
                "PlannerPagination",
                "PlannerForm",
                "PlannerInput",
                "PlannerButton",
                "PlannerNotice",
            ]
        return ["Card", "Table"]

    def get_all_component_codes(self) -> set[str]:
        return {
            "PlannerBlankContainer",
            "PlannerCard",
            "PlannerInfoGrid",
            "PlannerTable",
            "PlannerPagination",
            "PlannerForm",
            "PlannerInput",
            "PlannerButton",
            "PlannerNotice",
            "Card",
            "Table",
        }

    def get_all_action_codes(self) -> set[str]:
        return {"remoteQuery"}

    def get_action_definition(self, code: str) -> UIActionDefinition | None:
        if code != "remoteQuery":
            return None
        return UIActionDefinition(
            code="remoteQuery",
            name="远程查询",
            description="详情和分页刷新动作",
            params_schema={"type": "object", "required": ["api_id"]},
            enabled=True,
        )


def _make_runtime() -> ApiQueryUIRuntime:
    return ApiQueryUIRuntime(
        components=[
            "PlannerBlankContainer",
            "PlannerCard",
            "PlannerMetric",
            "PlannerInfoGrid",
            "PlannerTable",
            "PlannerPagination",
            "PlannerForm",
            "PlannerInput",
            "PlannerButton",
            "PlannerNotice",
        ],
        ui_actions=[
            ApiQueryUIAction(
                code="remoteQuery",
                description="详情和分页刷新动作",
                enabled=True,
                params_schema={"type": "object"},
            )
        ],
    )


def _make_list_runtime() -> ApiQueryUIRuntime:
    """构造带分页与详情能力的列表运行时契约。"""
    runtime = _make_runtime()
    return runtime.model_copy(
        update={
            "list": ApiQueryListRuntime(
                enabled=True,
                api_id="customer_list",
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                param_source="queryParams",
                pagination=ApiQueryListPaginationRuntime(
                    enabled=True,
                    total=68,
                    current_page=2,
                    page_size=20,
                    page_param="pageNum",
                    page_size_param="pageSize",
                    mutation_target="report-table.props.dataSource",
                ),
                query_context=ApiQueryListQueryContextRuntime(
                    enabled=True,
                    current_params={"ownerId": "E8899", "pageNum": 2, "pageSize": 20},
                    page_param="pageNum",
                    page_size_param="pageSize",
                    preserve_on_pagination=["ownerId"],
                    reset_page_on_filter_change=True,
                ),
            ),
            "detail": ApiQueryDetailRuntime(
                enabled=True,
                api_id="customer_detail",
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                request=ApiQueryDetailRequestRuntime(
                    param_source="queryParams",
                    identifier_param="customerId",
                ),
                source=ApiQueryDetailSourceRuntime(
                    identifier_field="customerId",
                    value_type="string",
                    required=True,
                ),
            ),
        }
    )


def _root_element(spec: dict[str, object]) -> dict[str, object]:
    root_id = spec["root"]
    elements = spec["elements"]
    assert isinstance(root_id, str)
    assert isinstance(elements, dict)
    root = elements[root_id]
    assert isinstance(root, dict)
    return root


def _root_child_by_type(spec: dict[str, object], component_type: str) -> dict[str, object]:
    """按组件类型递归取回元素，兼容根空容器下的二跳业务组件。"""
    elements = spec["elements"]
    assert isinstance(elements, dict)
    for element in elements.values():
        assert isinstance(element, dict)
        if element.get("type") == component_type:
            return element
    raise AssertionError(f"missing child type: {component_type}")


def _children_of(spec: dict[str, object], element: dict[str, object]) -> list[dict[str, object]]:
    """按元素 children 顺序取回直接子元素。"""
    elements = spec["elements"]
    child_ids = element.get("children", [])
    assert isinstance(elements, dict)
    assert isinstance(child_ids, list)
    children: list[dict[str, object]] = []
    for child_id in child_ids:
        assert isinstance(child_id, str)
        child = elements[child_id]
        assert isinstance(child, dict)
        children.append(child)
    return children


@pytest.mark.asyncio
async def test_generate_ui_spec_uses_renderer_prompt_json_mode_and_pruned_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """任务3核心验证：首轮必须走 JSON Mode，且 prompt 输入不能原样塞完整 context_pool。"""
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService(catalog_service=StubUICatalogService())
    service._llm_service = RecordingLLM(
        [
            """
            {
              "root": "root",
              "state": {},
              "elements": {
                "root": {
                  "type": "PlannerCard",
                  "props": {"title": "LLM 详情视图"},
                  "children": []
                }
              }
            }
            """
        ]
    )

    context = {
        "question": "查询客户详情",
        "user_query": "查询客户详情",
        "title": "客户详情",
        "query_render_mode": "detail",
        "business_intents": [{"code": "none", "category": "read", "risk_level": "none"}],
        "context_pool": {
            "step_customer_list": {
                "status": "SUCCESS",
                "domain": "crm",
                "api_id": "customer_list",
                "total": 6,
                "data": [
                    {"customerId": "C001", "customerName": "张三"},
                    {"customerId": "C002", "customerName": "李四"},
                    {"customerId": "C003", "customerName": "王五"},
                    {"customerId": "C004", "customerName": "赵六"},
                ],
                "meta": {
                    "raw_row_count": 6,
                    "render_row_count": 5,
                    "render_row_limit": 5,
                    "truncated": True,
                    "truncated_count": 1,
                    "resolved_params": {"pageNum": 1},
                },
            }
        },
    }

    spec = await service.generate_ui_spec(
        intent="query",
        data=[
            {"customerId": "C001", "customerName": "张三"},
            {"customerId": "C002", "customerName": "李四"},
            {"customerId": "C003", "customerName": "王五"},
            {"customerId": "C004", "customerName": "赵六"},
        ],
        context=context,
        runtime=_make_runtime(),
    )

    assert spec is not None
    llm_call = service._llm_service.calls[0]
    assert llm_call["response_format"] == {"type": "json_object"}
    messages = llm_call["messages"]
    assert isinstance(messages, list)
    system_prompt = messages[0]["content"]
    user_prompt = messages[1]["content"]
    assert "Renderer Agent" in system_prompt
    assert "UI Catalog" in system_prompt
    assert "PlannerInfoGrid" in system_prompt
    assert "自定义表格说明" in system_prompt
    assert "business_intents" in user_prompt
    assert "context_pool" in user_prompt
    assert "C004" not in user_prompt
    assert "resolved_params" not in user_prompt
    assert _root_element(spec)["type"] == "PlannerBlankContainer"
    assert _root_child_by_type(spec, "PlannerCard")["props"]["title"] == "LLM 详情视图"


@pytest.mark.asyncio
async def test_generate_ui_spec_retries_without_json_mode_when_backend_rejects_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService(catalog_service=StubUICatalogService())
    service._llm_service = RecordingLLM(
        [
            """
            {
              "root": "root",
              "elements": {
                "root": {
                  "type": "PlannerCard",
                  "props": {"title": "纯文本兜底成功"},
                  "children": []
                }
              }
            }
            """
        ],
        fail_on_json_mode=True,
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"customerId": "C001", "customerName": "张三"}],
        context={"question": "查询客户"},
        runtime=_make_runtime(),
    )

    assert spec is not None
    assert len(service._llm_service.calls) == 2
    assert service._llm_service.calls[0]["response_format"] == {"type": "json_object"}
    assert service._llm_service.calls[1]["response_format"] is None
    assert _root_element(spec)["type"] == "PlannerBlankContainer"
    assert _root_child_by_type(spec, "PlannerCard")["props"]["title"] == "纯文本兜底成功"


@pytest.mark.asyncio
async def test_generate_ui_spec_parses_dirty_renderer_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService(catalog_service=StubUICatalogService())
    service._llm_service = RecordingLLM(
        [
            """```json
            {
              // 这是一个说明注释
              "root": "root",
              "state": {},
              "elements": {
                "root": {
                  "type": "PlannerCard",
                  "props": {
                    "title": "脏 JSON 也要能解析",
                  },
                  "children": [],
                },
              },
            }
            ```"""
        ]
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"customerId": "C001"}],
        context={"question": "查询客户"},
        runtime=_make_runtime(),
    )

    assert spec is not None
    assert _root_element(spec)["type"] == "PlannerBlankContainer"
    assert _root_child_by_type(spec, "PlannerCard")["props"]["title"] == "脏 JSON 也要能解析"
    assert spec["state"] == {}


@pytest.mark.asyncio
async def test_generate_ui_spec_sanitizes_llm_detail_request_keys_to_request_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService(catalog_service=StubUICatalogService())
    service._llm_service = RecordingLLM(
        [
            """
            {
              "root": "root",
              "state": {},
              "elements": {
                "root": {
                  "type": "PlannerCard",
                  "props": {"title": "客户详情"},
                  "children": ["detail"]
                },
                "detail": {
                  "type": "PlannerDetailCard",
                  "props": {
                    "title": "客户详情",
                    "items": [
                      {"label": "主键ID", "value": "71593"},
                      {"label": "客户姓名", "value": "张三"}
                    ],
                    "api": "/api/v1/ui-builder/runtime/endpoints/customer_detail/invoke",
                    "queryParams": {"主键ID": "71593"},
                    "body": {},
                    "flowNum": "trace-detail-001",
                    "createdBy": "user-001"
                  }
                }
              }
            }
            """
        ]
    )
    runtime = _make_runtime().model_copy(
        update={
            "detail": ApiQueryDetailRuntime(
                enabled=True,
                api_id="customer_detail",
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                request=ApiQueryDetailRequestRuntime(
                    param_source="queryParams",
                    identifier_param="id",
                    request_schema_fields=["id"],
                ),
                source=ApiQueryDetailSourceRuntime(
                    identifier_field="主键ID",
                    value_type="string",
                    required=True,
                ),
            )
        }
    )

    result = await service.generate_ui_spec_result(
        intent="query",
        data=[{"主键ID": "71593", "客户姓名": "张三"}],
        context={
            "question": "帮我查一下客户71593的详情",
            "title": "客户详情",
            "query_render_mode": "detail",
            "request_params": {"id": 71593},
            "flow_num": "trace-detail-001",
            "created_by": "user-001",
        },
        runtime=runtime,
        trace_id="trace-detail-001",
    )

    assert result.frozen is False
    assert result.spec is not None
    detail = _root_child_by_type(result.spec, "PlannerInfoGrid")
    assert detail["props"]["queryParams"] == {"id": 71593}
    assert detail["props"]["body"] == {}


@pytest.mark.asyncio
async def test_generate_ui_spec_falls_back_to_rule_renderer_when_llm_output_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService(catalog_service=StubUICatalogService())
    service._llm_service = RecordingLLM(["not json", "still not json"])

    spec = await service.generate_ui_spec(
        intent="query",
        data=[
            {"customerId": "C001", "customerName": "张三"},
            {"customerId": "C002", "customerName": "李四"},
        ],
        context={"question": "查询客户列表"},
        runtime=_make_runtime(),
    )

    assert spec is not None
    assert len(service._llm_service.calls) == 2
    table = _root_child_by_type(spec, "PlannerTable")
    assert table["props"]["dataSource"][0]["customerId"] == "C001"


@pytest.mark.asyncio
async def test_generate_ui_spec_result_freezes_invalid_renderer_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard 命中未知组件时，必须冻结为无交互安全视图。"""
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService(catalog_service=StubUICatalogService())
    service._llm_service = RecordingLLM(
        [
            """
            {
              "root": "root",
              "state": {},
              "elements": {
                "root": {
                  "type": "PlannerCard",
                  "props": {"title": "危险视图"},
                  "children": ["unknown_child"]
                },
                "unknown_child": {
                  "type": "MagicPanel",
                  "props": {"text": "非法组件"}
                }
              }
            }
            """
        ]
    )

    result = await service.generate_ui_spec_result(
        intent="query",
        data=[{"customerId": "C001", "customerName": "张三"}],
        context={"title": "客户详情"},
        runtime=_make_runtime(),
        trace_id="trace-freeze-001",
    )

    assert result.frozen is True
    assert result.validation.is_valid is False
    assert result.spec is not None
    notice = _root_child_by_type(result.spec, "PlannerNotice")
    assert _root_element(result.spec)["type"] == "PlannerBlankContainer"
    assert _root_child_by_type(result.spec, "PlannerCard")["props"]["title"] == "客户详情"
    assert "已冻结当前操作视图" in notice["props"]["text"]


@pytest.mark.asyncio
async def test_rule_query_spec_exposes_runtime_metadata_for_list_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """列表视图必须固定输出三段式节点，并在组件 props 中携带 runtime 元数据。"""
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=StubUICatalogService())

    spec = await service.generate_ui_spec(
        intent="query",
        data=[
            {"customerId": "C021", "customerName": "客户21"},
            {"customerId": "C022", "customerName": "客户22"},
        ],
        context={
            "question": "查询客户列表",
            "flow_num": "trace-query-001",
            "created_by": "user-001",
        },
        runtime=_make_list_runtime(),
    )

    assert spec is not None
    root = _root_element(spec)
    assert root["type"] == "PlannerBlankContainer"
    card = _root_child_by_type(spec, "PlannerCard")
    assert card["children"] == ["query-filters", "report-table", "report-pagination"]

    elements = spec["elements"]
    assert isinstance(elements, dict)

    filters = elements["query-filters"]
    table = elements["report-table"]
    pagination = elements["report-pagination"]
    assert filters["type"] == "PlannerForm"
    assert table["type"] == "PlannerTable"
    assert pagination["type"] == "PlannerPagination"

    assert filters["props"]["api"] == "/api/v1/ui-builder/runtime/endpoints/customer_list/invoke"
    assert filters["props"]["queryParams"] == {"ownerId": "E8899", "pageNum": 2, "pageSize": 20}
    assert filters["props"]["body"] == {}
    assert filters["props"]["flowNum"] == "trace-query-001"
    assert filters["props"]["createdBy"] == "user-001"

    assert table["props"]["api"] == "/api/v1/ui-builder/runtime/endpoints/customer_list/invoke"
    assert table["props"]["queryParams"] == {"ownerId": "E8899", "pageNum": 2, "pageSize": 20}
    assert table["props"]["body"] == {}
    row_action = table["props"]["rowActions"][0]
    assert row_action["action"] == "remoteQuery"
    assert "type" not in row_action
    assert row_action["params"]["api"] == "/api/v1/ui-builder/runtime/endpoints/customer_detail/invoke"
    assert row_action["params"]["renderMode"] == "dynamic_ui"
    assert row_action["params"]["fallbackMode"] == "dynamic_ui"
    assert "templateCode" not in row_action["params"]
    assert row_action["params"]["queryParams"] == {"customerId": {"$bindRow": "customerId"}}
    assert row_action["params"]["body"] == {}
    assert row_action["params"]["flowNum"] == "trace-query-001"
    assert row_action["params"]["createdBy"] == "user-001"

    assert pagination["props"]["api"] == "/api/v1/ui-builder/runtime/endpoints/customer_list/invoke"
    assert pagination["props"]["queryParams"] == {"ownerId": "E8899", "pageNum": 2, "pageSize": 20}
    assert pagination["props"]["body"] == {}
    assert pagination["props"]["flowNum"] == "trace-query-001"
    assert pagination["props"]["createdBy"] == "user-001"
    assert pagination["props"]["currentPage"] == 2
    assert pagination["props"]["pageSize"] == 20
    assert pagination["props"]["total"] == 68
    assert pagination["props"]["pageParam"] == "pageNum"
    assert pagination["props"]["pageSizeParam"] == "pageSize"


@pytest.mark.asyncio
async def test_rule_query_spec_composite_renders_metrics_and_tables_without_stringifying_nested_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """composite 模式应拆分指标与明细表，而不是把嵌套结构塞进详情字符串。"""
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    data = [
        {
            "summaryCard": {
                "storeFundCount": 12,
                "storeLeftFunds": 13245060.0,
                "storeAvailableAmount": 11954620.0,
            },
            "deliveryRecords": [
                {
                    "deliveryDate": "2024-10-01T00:00",
                    "deliveryProject": "肝脏解毒支持（白金版）",
                    "deliveryAmount": 27103.46,
                },
                {
                    "deliveryDate": "2024-09-30T00:00",
                    "deliveryProject": "免疫功能调理",
                    "deliveryAmount": 20000.0,
                },
            ],
            "curePlanRecords": [
                {
                    "fid": "P001",
                    "fcreateTime": "2024-11-20T09:44",
                    "fproductBillProjectName": "免疫力改善-C治疗",
                    "fprojectAmount": 298000.0,
                }
            ],
        }
    ]

    spec = await service.generate_ui_spec(
        intent="query",
        data=data,
        context={
            "question": "查询刘海坚的储值方案",
            "query_render_mode": "composite",
            "flow_num": "trace-query-001",
            "created_by": "user-001",
            "response_field_label_index": {
                "summaryCard.storeLeftFunds": "储值总余额",
                "deliveryRecords": "交付记录",
                "deliveryRecords[].deliveryDate": "交付日期",
                "curePlanRecords": "调理方案记录",
                "curePlanRecords[].fId": "订单ID",
                "curePlanRecords[].fCreateTime": "创建时间",
                "curePlanRecords[].fProductBillProjectName": "治疗项目名称",
                "curePlanRecords[].fProjectAmount": "方案金额",
            },
        },
        runtime=_make_runtime().model_copy(
            update={
                "list": ApiQueryListRuntime(
                    enabled=True,
                    api_id="fa969d461ef059ab82f1dd6d3c2aa116",
                    param_source="body",
                    request_schema_fields=["encryptedIdCard"],
                    query_context=ApiQueryListQueryContextRuntime(
                        enabled=True,
                        current_params={"encryptedIdCard": "ENC001", "展示标签": "SHOULD_DROP"},
                    ),
                )
            }
        ),
    )

    assert spec is not None
    root = _root_element(spec)
    assert root["type"] == "PlannerBlankContainer"
    card = _root_child_by_type(spec, "PlannerCard")
    children = _children_of(spec, card)
    child_types = [child["type"] for child in children]

    assert "PlannerInfoGrid" in child_types
    assert child_types.count("PlannerTable") >= 2
    assert "PlannerDetailCard" not in child_types

    info_grid = next(child for child in children if child["type"] == "PlannerInfoGrid")
    info_items = {(item["label"], item["value"]) for item in info_grid["props"]["items"]}
    assert ("储值总余额", "13245060.0") in info_items
    assert info_grid["props"]["bizFieldKey"] == "summaryCard"
    assert info_grid["props"]["api"] == "/api/v1/ui-builder/runtime/endpoints/fa969d461ef059ab82f1dd6d3c2aa116/invoke"
    assert info_grid["props"]["queryParams"] == {}
    assert info_grid["props"]["body"] == {"encryptedIdCard": "ENC001"}
    assert info_grid["props"]["flowNum"] == "trace-query-001"
    assert info_grid["props"]["createdBy"] == "user-001"

    tables = [child for child in children if child["type"] == "PlannerTable"]
    table_titles = [table["props"].get("title") for table in tables]
    assert "交付记录" in table_titles
    assert "调理方案记录" in table_titles

    delivery_table = next(table for table in tables if table["props"].get("title") == "交付记录")
    assert delivery_table["props"]["bizFieldKey"] == "deliveryRecords"
    assert delivery_table["props"]["columns"][0]["dataIndex"] == "deliveryDate"
    assert delivery_table["props"]["columns"][0]["title"] == "交付日期"
    assert delivery_table["props"]["dataSource"][0]["deliveryProject"] == "肝脏解毒支持（白金版）"
    cure_plan_table = next(table for table in tables if table["props"].get("title") == "调理方案记录")
    assert cure_plan_table["props"]["bizFieldKey"] == "curePlanRecords"
    cure_plan_columns = cure_plan_table["props"]["columns"]
    assert [column["dataIndex"] for column in cure_plan_columns] == [
        "fid",
        "fcreateTime",
        "fproductBillProjectName",
        "fprojectAmount",
    ]
    assert [column["title"] for column in cure_plan_columns] == [
        "订单ID",
        "创建时间",
        "治疗项目名称",
        "方案金额",
    ]


@pytest.mark.asyncio
async def test_rule_query_spec_composite_uses_aggregate_section_title_index_for_table_titles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """聚合渲染下，表格标题应优先使用后端下发的 section 标题映射。"""
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    data = [
        {
            "healthBasic": {"__sectionType": "detail", "data": {"bloodType": "A型"}},
            "healthStatusMedicalHistory": {"__sectionType": "detail", "data": {"history": "高血压"}},
            "physicalExam": {"__sectionType": "detail", "data": {"latestExamDate": "2025-04-08"}},
        }
    ]

    spec = await service.generate_ui_spec(
        intent="query",
        data=data,
        context={
            "question": "查询客户刘海坚的健康数据",
            "query_render_mode": "composite",
            "aggregate_section_title_index": {
                "healthBasic": "健康基础档案",
                "healthStatusMedicalHistory": "医疗史概览",
                "physicalExam": "体检结果",
            },
        },
        runtime=_make_runtime(),
    )

    assert spec is not None
    root = _root_element(spec)
    assert root["type"] == "PlannerBlankContainer"
    card = _root_child_by_type(spec, "PlannerCard")
    info_grids = [child for child in _children_of(spec, card) if child["type"] == "PlannerInfoGrid"]
    assert {grid["props"]["bizFieldKey"] for grid in info_grids} == {
        "healthBasic",
        "healthStatusMedicalHistory",
        "physicalExam",
    }
    assert {grid["props"]["title"] for grid in info_grids} == {
        "健康基础档案",
        "医疗史概览",
        "体检结果",
    }


@pytest.mark.asyncio
async def test_rule_query_spec_composite_uses_section_runtime_for_typed_aggregate_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """多接口聚合页每个 child 应使用自己的二跳接口元数据。"""

    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    spec = await service.generate_ui_spec(
        intent="query",
        data=[
            {
                "identityContact": {"__sectionType": "detail", "data": {"customerName": "刘海坚"}},
                "serviceRecords": {
                    "__sectionType": "table",
                    "data": [{"visitFrequency": "每月"}],
                },
            }
        ],
        context={
            "question": "查询客户刘海坚的信息",
            "query_render_mode": "composite",
            "flow_num": "trace-section-runtime",
            "created_by": "2",
            "aggregate_section_runtime_index": {
                "identityContact": {
                    "api_id": "identity_api",
                    "param_source": "queryParams",
                    "params": {"encryptedIdCard": "ENC001", "extra": "DROP"},
                    "request_schema_fields": ["encryptedIdCard"],
                },
                "serviceRecords": {
                    "api_id": "service_api",
                    "param_source": "body",
                    "params": {"encryptedIdCard": "ENC001", "extra": "DROP"},
                    "request_schema_fields": ["encryptedIdCard"],
                },
            },
        },
        runtime=_make_runtime(),
    )

    assert spec is not None
    card = _root_child_by_type(spec, "PlannerCard")
    children = _children_of(spec, card)
    info_grid = next(child for child in children if child["type"] == "PlannerInfoGrid")
    table = next(child for child in children if child["type"] == "PlannerTable")

    assert info_grid["props"]["api"] == "/api/v1/ui-builder/runtime/endpoints/identity_api/invoke"
    assert info_grid["props"]["queryParams"] == {"encryptedIdCard": "ENC001"}
    assert info_grid["props"]["body"] == {}
    assert table["props"]["api"] == "/api/v1/ui-builder/runtime/endpoints/service_api/invoke"
    assert table["props"]["queryParams"] == {}
    assert table["props"]["body"] == {"encryptedIdCard": "ENC001"}
    assert info_grid["props"]["flowNum"] == "trace-section-runtime"
    assert table["props"]["createdBy"] == "2"


@pytest.mark.asyncio
async def test_rule_query_spec_detail_uses_schema_description_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """detail 模式应优先展示 response_schema 描述作为字段标签。"""

    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"customerId": "C001", "level": "VIP"}],
        context={
            "question": "查询客户详情",
            "query_render_mode": "detail",
            "response_field_label_index": {
                "customerId": "客户编号",
                "level": "客户等级",
            },
        },
        runtime=_make_runtime(),
    )

    assert spec is not None
    detail_card = _root_child_by_type(spec, "PlannerInfoGrid")
    assert detail_card["props"]["items"] == [
        {"label": "客户编号", "value": "C001"},
        {"label": "客户等级", "value": "VIP"},
    ]


@pytest.mark.asyncio
async def test_rule_query_spec_table_uses_schema_description_column_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    """table 模式应优先展示 response_schema 描述作为列标题。"""

    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"customerId": "C001", "customerName": "张三"}],
        context={
            "question": "查询客户列表",
            "query_render_mode": "table",
            "response_field_label_index": {
                "customerId": "客户编号",
                "customerName": "客户姓名",
            },
        },
        runtime=_make_list_runtime(),
    )

    assert spec is not None
    table = _root_child_by_type(spec, "PlannerTable")
    columns = table["props"]["columns"]
    assert columns[0]["title"] == "客户编号"
    assert columns[1]["title"] == "客户姓名"


@pytest.mark.asyncio
async def test_rule_query_spec_table_columns_strictly_follow_runtime_table_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """当 runtime 下发 table_fields 时，列表列必须严格按白名单渲染。"""

    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    runtime = _make_list_runtime().model_copy(
        update={
            "list": _make_list_runtime().list.model_copy(
                update={
                    "table_fields": [
                        ApiQueryListTableFieldRuntime(name="customerName", title="客户姓名"),
                        ApiQueryListTableFieldRuntime(name="mainTeacherName", title="主市场老师"),
                    ]
                }
            )
        }
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"customerId": "C001", "customerName": "张三", "mainTeacherName": "王雪梅", "age": 65}],
        context={"question": "查询客户列表"},
        runtime=runtime,
    )

    assert spec is not None
    table = _root_child_by_type(spec, "PlannerTable")
    columns = table["props"]["columns"]
    assert [column["dataIndex"] for column in columns] == ["customerName", "mainTeacherName"]
    assert [column["title"] for column in columns] == ["客户姓名", "主市场老师"]


@pytest.mark.asyncio
async def test_rule_query_spec_table_renders_combined_runtime_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """组合列应生成派生 dataIndex，并按配置折叠来源字段。"""

    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    runtime = _make_list_runtime().model_copy(
        update={
            "list": _make_list_runtime().list.model_copy(
                update={
                    "table_fields": [
                        ApiQueryListTableFieldRuntime(name="customerName", title="客户姓名"),
                        ApiQueryListTableFieldRuntime(
                            name="__combined_2",
                            title="地址",
                            source_fields=["province", "city", "county"],
                            separator="",
                            empty_value="-",
                        ),
                        ApiQueryListTableFieldRuntime(
                            name="__combined_3",
                            title="主市场老师",
                            source_fields=["mainTeacherName", "mainTeacherNo"],
                            separator=" / ",
                            empty_value="-",
                        ),
                    ]
                }
            )
        }
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[
            {
                "customerName": "刘海坚",
                "province": None,
                "city": "和平区",
                "county": None,
                "mainTeacherName": "王雪梅",
                "mainTeacherNo": "MK405829",
                "age": 65,
            }
        ],
        context={"question": "查询客户列表"},
        runtime=runtime,
    )

    assert spec is not None
    table = _root_child_by_type(spec, "PlannerTable")
    columns = table["props"]["columns"]
    row = table["props"]["dataSource"][0]
    assert [column["dataIndex"] for column in columns] == ["customerName", "__combined_2", "__combined_3"]
    assert [column["title"] for column in columns] == ["客户姓名", "地址", "主市场老师"]
    assert row["__combined_2"] == "和平区"
    assert row["__combined_3"] == "王雪梅 / MK405829"



@pytest.mark.asyncio
async def test_rule_query_spec_detail_applies_detail_view_meta_priority_and_group_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """详情字段应按 exclude>required>display 过滤，并按 groups 排序。"""

    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    runtime = _make_runtime().model_copy(
        update={
            "detail": ApiQueryDetailRuntime(
                enabled=True,
                api_id="customer_detail",
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                request=ApiQueryDetailRequestRuntime(
                    param_source="queryParams",
                    identifier_param="id",
                ),
                source=ApiQueryDetailSourceRuntime(
                    identifier_field="id",
                    value_type="string",
                    required=True,
                ),
                detail_view_meta={
                    "display_fields": ["id", "name", "phone"],
                    "required_fields": ["id", "mainTeacherName"],
                    "exclude_fields": ["phone"],
                    "groups": [
                        {"title": "服务归属", "fields": ["mainTeacherName"]},
                        {"title": "基础信息", "fields": ["name", "id"]},
                    ],
                },
            )
        }
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"id": "C001", "name": "刘海坚", "phone": "13900000000", "mainTeacherName": "王雪梅", "age": 65}],
        context={"question": "查询客户详情", "query_render_mode": "detail"},
        runtime=runtime,
    )

    assert spec is not None
    detail_card = _root_child_by_type(spec, "PlannerInfoGrid")
    items = detail_card["props"]["items"]
    assert [item["label"] for item in items] == ["mainTeacherName", "name", "id"]
    assert [item["value"] for item in items] == ["王雪梅", "刘海坚", "C001"]


@pytest.mark.asyncio
async def test_rule_query_spec_detail_stringifies_scalar_array_with_chinese_delimiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """详情卡应展示 list[string] 字段，并用顿号折叠为单行文本。"""

    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    service = DynamicUIService(catalog_service=UICatalogService())

    runtime = _make_runtime().model_copy(
        update={
            "detail": _make_runtime().detail.model_copy(
                update={
                    "detail_view_meta": {
                        "display_fields": ["physicalExamPackage", "keyAbnormalIndicators", "doctorAdvice"],
                        "required_fields": [],
                        "exclude_fields": [],
                        "groups": [
                            {
                                "title": "体检情况",
                                "fields": ["physicalExamPackage", "keyAbnormalIndicators", "doctorAdvice"],
                            }
                        ],
                    }
                }
            )
        }
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[
            {
                "physicalExamPackage": "个性定制体检套餐",
                "keyAbnormalIndicators": ["食物不耐受", "甲状腺结节", "糖尿病前期"],
                "doctorAdvice": "建议复查",
            }
        ],
        context={"question": "查询客户体检情况", "query_render_mode": "detail"},
        runtime=runtime,
    )

    assert spec is not None
    detail_card = _root_child_by_type(spec, "PlannerInfoGrid")
    items = detail_card["props"]["items"]
    assert [item["label"] for item in items] == ["physicalExamPackage", "keyAbnormalIndicators", "doctorAdvice"]
    assert [item["value"] for item in items] == ["个性定制体检套餐", "食物不耐受、甲状腺结节、糖尿病前期", "建议复查"]


@pytest.mark.asyncio
async def test_rule_query_spec_table_row_action_exposes_template_first_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    """详情配置了模板编码时，row action 需显式透传模板优先与动态兜底策略。"""

    monkeypatch.setattr(settings, "llm_ui_spec_enabled", False)
    monkeypatch.setattr(settings, "api_query_template_first_enabled", True)
    service = DynamicUIService(catalog_service=StubUICatalogService())

    runtime = _make_list_runtime().model_copy(
        update={
            "detail": _make_list_runtime().detail.model_copy(
                update={
                    "render_mode": "template_first",
                    "template_code": "customer_detail_template",
                    "fallback_mode": "dynamic_ui",
                }
            )
        }
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"customerId": "C001", "customerName": "张三"}],
        context={
            "question": "查询客户列表",
            "flow_num": "trace-template-001",
            "created_by": "user-001",
        },
        runtime=runtime,
    )

    assert spec is not None
    table = _root_child_by_type(spec, "PlannerTable")
    row_action = table["props"]["rowActions"][0]
    assert row_action["params"]["renderMode"] == "template_first"
    assert row_action["params"]["templateCode"] == "customer_detail_template"
    assert row_action["params"]["fallbackMode"] == "dynamic_ui"

@pytest.mark.asyncio
async def test_mutation_form_skipped_status_still_renders_planner_form() -> None:
    """mutation confirm 场景虽然状态是 SKIPPED，但必须渲染可提交表单。"""

    service = DynamicUIService(catalog_service=UICatalogService())
    runtime = ApiQueryUIRuntime(
        components=[
            "PlannerBlankContainer",
            "PlannerCard",
            "PlannerMetric",
            "PlannerForm",
            "PlannerInput",
            "PlannerButton",
            "PlannerNotice",
        ],
        ui_actions=[
            ApiQueryUIAction(
                code="remoteMutation",
                description="远程写入",
                enabled=True,
                params_schema={"type": "object", "required": ["api_id"]},
            )
        ],
        form=ApiQueryFormRuntime(
            enabled=True,
            form_code="employee_update_form",
            mode="edit",
            api_id="employee_update",
            route_url="https://runtime.example/ui-builder/runtime/endpoints/employee_update/invoke",
            ui_action="remoteMutation",
            state_path="/form",
            fields=[
                ApiQueryFormFieldRuntime(
                    name="id",
                    value_type="string",
                    state_path="/form/id",
                    submit_key="id",
                    required=True,
                    writable=False,
                    source_kind="context",
                ),
                ApiQueryFormFieldRuntime(
                    name="email",
                    value_type="string",
                    state_path="/form/email",
                    submit_key="email",
                    required=True,
                    writable=True,
                    source_kind="context",
                ),
                ApiQueryFormFieldRuntime(
                    name="手机号",
                    value_type="string",
                    state_path="/form/mobile",
                    submit_key="mobile",
                    required=False,
                    writable=True,
                    source_kind="user_input",
                ),
            ],
            submit=ApiQueryFormSubmitRuntime(
                business_intent="saveToServer",
                confirm_required=True,
            ),
        ),
    )

    result = await service.generate_ui_spec_result(
        intent="mutation_form",
        data={"id": "8058", "email": "437462373467289@qq.com"},
        context={
            "title": "确认修改：修改员工",
            "form_state": {
                "form": {
                    "id": "8058",
                    "email": "437462373467289@qq.com",
                    "mobile": None,
                }
            },
        },
        status=ApiQueryExecutionStatus.SKIPPED,
        runtime=runtime,
        trace_id="trace-mutation-form-001",
    )

    assert result.frozen is False
    assert result.spec is not None
    form = _root_child_by_type(result.spec, "PlannerForm")
    assert form["props"]["formCode"] == "employee_update_form"
    assert form["props"]["api"] == "/api/v1/ui-builder/runtime/endpoints/employee_update/invoke"
    assert form["props"]["queryParams"] == {}
    assert form["props"]["body"]["email"] == {"$bindState": "/form/email"}
    assert form["props"]["flowNum"] == ""
    assert form["props"]["createdBy"] == ""
    elements = result.spec["elements"]
    assert isinstance(elements, dict)
    assert elements["form_field_1"]["props"]["required"] is True
    assert elements["form_field_2"]["props"]["required"] is True
    assert elements["form_field_3"]["type"] == "PlannerInput"
    assert elements["form_field_3"]["props"]["label"] == "手机号"
    assert elements["form_field_3"]["props"]["required"] is False
    submit = elements["form_submit"]
    assert submit["type"] == "PlannerButton"
    assert submit["on"]["press"]["action"] == "remoteMutation"
    assert submit["on"]["press"]["params"]["api_id"] == "employee_update"
    assert submit["on"]["press"]["params"]["api"] == "/api/v1/ui-builder/runtime/endpoints/employee_update/invoke"
    assert submit["on"]["press"]["params"]["queryParams"] == {}
    assert submit["on"]["press"]["params"]["body"]["email"] == {"$bindState": "/form/email"}
    assert submit["on"]["press"]["params"]["body"]["mobile"] == {"$bindState": "/form/mobile"}
    assert submit["on"]["press"]["params"]["flowNum"] == ""
    assert submit["on"]["press"]["params"]["createdBy"] == ""
    root = _root_element(result.spec)
    assert root["type"] == "PlannerBlankContainer"
    assert "PlannerNotice" not in [element.get("type") for element in elements.values() if isinstance(element, dict)]
