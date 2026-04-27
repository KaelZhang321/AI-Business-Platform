from __future__ import annotations

import pytest

from app.models.schemas import ApiQueryExecutionResult, ApiQueryExecutionStatus, ApiQueryRequest
from app.services.api_catalog.schema import ApiCatalogEntry
from app.services.customer_profile_fixed_service import (
    _CUSTOMER_LOOKUP_API_ID,
    CustomerProfileEndpointCatalog,
    CustomerProfileFixedService,
    CustomerProfileSection,
)


class RecordingExecutor:
    """记录固定分支调用顺序的执行器桩。

    功能：测试关注的是“多候选不扩散、选定后才调用下游”，因此执行器只需要按 api_id 返回预置结果，
    并保留每次调用的接口和参数用于断言。
    """

    def __init__(self, results_by_api_id: dict[str, ApiQueryExecutionResult]) -> None:
        self._results_by_api_id = results_by_api_id
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call(self, entry: ApiCatalogEntry, params: dict[str, object], **_: object) -> ApiQueryExecutionResult:
        self.calls.append((entry.id, dict(params)))
        result = self._results_by_api_id[entry.id]
        return result.model_copy(update={"trace_id": "trace-customer-profile"})


def test_detect_customer_profile_branch_excludes_single_topic_query() -> None:
    from app.services.customer_profile_fixed_service import detect_customer_profile_trigger

    assert detect_customer_profile_trigger("查询客户刘海坚的个人信息") is not None
    assert detect_customer_profile_trigger("查询客户刘海坚的储值方案") is None
    assert detect_customer_profile_trigger("客户信息怎么维护") is None


def test_customer_profile_catalog_keeps_raw_response_keys_for_binding(monkeypatch) -> None:
    """固定档案分支必须保留原始字段名，否则后续 predecessor 绑定会取不到 idCard。"""

    from app.services.customer_profile_fixed_service import build_catalog_entry_from_xlsx_row, build_section_params

    header = {
        "id": 0,
        "name": 1,
        "path": 2,
        "method": 3,
        "summary": 4,
        "status": 5,
        "operation_safety": 6,
        "request_schema": 7,
        "response_schema": 8,
        "sample_request": 9,
        "predecessor_specs": 10,
        "detail_view_meta": 11,
    }
    row = [
        "identity",
        "一、身份与联系信息",
        "/identity",
        "POST",
        "身份与联系信息",
        "active",
        "query",
        '{"type":"object","properties":{"encryptedIdCard":{"type":"string"}}}',
        '{"type":"object","properties":{"result":{"type":"object","properties":{"idCard":{"type":"string","description":"身份证号"}}}}}',
        "{}",
        '[{"predecessor_api_id":"6bbc18329c3dde651603182a651569ab","param_bindings":[{"target_param":"encryptedIdCard","source_path":"$.idCard","select_mode":"user_select"}]}]',
        "{}",
    ]

    entry = build_catalog_entry_from_xlsx_row(row, header)

    assert entry.field_labels == {}
    assert build_section_params(entry, {"idCard": "ENC001", "身份证号": "SHOULD_NOT_BE_USED"}) == {
        "encryptedIdCard": "ENC001"
    }


@pytest.mark.asyncio
async def test_customer_profile_fixed_waits_when_lookup_returns_multiple_customers(monkeypatch) -> None:
    """首跳返回多个客户时必须先让用户选择，不能提前调用档案接口。"""

    catalog = build_test_catalog()
    monkeypatch.setattr(
        "app.services.customer_profile_fixed_service.load_customer_profile_catalog",
        lambda *_: catalog,
    )
    executor = RecordingExecutor(
        {
            _CUSTOMER_LOOKUP_API_ID: ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[
                    {"id": "C001", "name": "刘海坚", "idCard": "ENC001", "idCardObfuscated": "110***001"},
                    {"id": "C002", "name": "刘海坚", "idCard": "ENC002", "idCardObfuscated": "110***002"},
                ],
                total=2,
            ),
            "identity": ApiQueryExecutionResult(status=ApiQueryExecutionStatus.SUCCESS, data={"name": "刘海坚"}, total=1),
        }
    )

    response = await CustomerProfileFixedService().handle(
        request_body=ApiQueryRequest.model_validate({"query": "查询客户刘海坚的个人信息"}),
        executor=executor,  # type: ignore[arg-type]
        user_token=None,
        user_id="2",
        trace_id="trace-customer-profile",
    )

    assert response is not None
    assert response.execution_status == ApiQueryExecutionStatus.SKIPPED
    assert [api_id for api_id, _ in executor.calls] == [_CUSTOMER_LOOKUP_API_ID]
    table = response.ui_spec["elements"]["customer_candidates"]
    assert table["type"] == "PlannerTable"
    assert table["props"]["waitSelect"]["errorCode"] == "WAIT_SELECT_REQUIRED"
    assert table["props"]["dataSource"][0]["bindingMap"]["customerRow"]["id"] == "C001"


@pytest.mark.asyncio
async def test_customer_profile_fixed_resumes_with_selected_customer(monkeypatch) -> None:
    """用户选定客户后才生成固定档案分区，并且下游只绑定选定客户。"""

    catalog = build_test_catalog()
    monkeypatch.setattr(
        "app.services.customer_profile_fixed_service.load_customer_profile_catalog",
        lambda *_: catalog,
    )
    executor = RecordingExecutor(
        {
            _CUSTOMER_LOOKUP_API_ID: ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data=[
                    {"id": "C001", "name": "刘海坚", "idCard": "ENC001", "idCardObfuscated": "110***001"},
                    {"id": "C002", "name": "刘海坚", "idCard": "ENC002", "idCardObfuscated": "110***002"},
                ],
                total=2,
            ),
            "identity": ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data={"name": "刘海坚", "phoneObfuscated": "138****0000"},
                total=1,
            ),
            "asset": ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.SUCCESS,
                data={
                    "summaryCard": {"storeFundCount": 12, "storeLeftFunds": 13245060.0},
                    "deliveryRecords": [{"deliveryProject": "免疫功能调理", "deliveryAmount": 20000}],
                    "curePlanRecords": [{"fProductBillProjectName": "肝胆双益", "fProjectAmount": 98000}],
                },
                total=1,
            ),
        }
    )

    response = await CustomerProfileFixedService().handle(
        request_body=ApiQueryRequest.model_validate(
            {
                "query": "查询客户刘海坚的个人信息",
                "selection_context": {"user_select": {"customerRow": {"id": "C002", "name": "刘海坚", "idCard": "ENC002"}}},
            }
        ),
        executor=executor,  # type: ignore[arg-type]
        user_token=None,
        user_id="2",
        trace_id="trace-customer-profile",
    )

    assert response is not None
    assert response.execution_status == ApiQueryExecutionStatus.SUCCESS
    assert [api_id for api_id, _ in executor.calls] == [_CUSTOMER_LOOKUP_API_ID, "identity", "asset"]
    assert executor.calls[1][1] == {"encryptedIdCard": "ENC002"}
    assert response.ui_spec["elements"]["root"]["props"]["renderMode"] == "customer_profile_fixed"
    assert response.ui_spec["elements"]["section_identity_contact"]["type"] == "PlannerDetailCard"
    assert response.ui_spec["elements"]["section_asset_summary"]["type"] == "PlannerInfoGrid"
    assert response.ui_spec["elements"]["section_asset_delivery_records"]["type"] == "PlannerTable"
    assert response.ui_spec["elements"]["section_asset_cure_plan_records"]["props"]["title"] == "规划方案"


def build_test_catalog() -> CustomerProfileEndpointCatalog:
    """构造覆盖身份分区与资产组合区的最小目录。"""

    lookup = ApiCatalogEntry(
        id=_CUSTOMER_LOOKUP_API_ID,
        name="客户列表查询",
        description="客户列表查询",
        domain="customer_profile",
        method="POST",
        path="/leczcore-crm/customerInquiry/getCustomerInfo",
        operation_safety="query",
    )
    identity = ApiCatalogEntry(
        id="identity",
        name="一、身份与联系信息",
        description="一、身份与联系信息",
        domain="customer_profile",
        method="POST",
        path="/identity",
        operation_safety="query",
        response_schema={
            "type": "object",
            "properties": {
                "result": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "客户姓名"},
                        "phoneObfuscated": {"type": "string", "description": "脱敏手机号"},
                    },
                }
            },
        },
        detail_view_meta={"display_fields": ["name", "phoneObfuscated"]},
        predecessors=[build_encrypted_id_predecessor()],
    )
    asset = ApiCatalogEntry(
        id="asset",
        name="十六、历史购买储值方案/规划方案/剩余项目金",
        description="资产概览",
        domain="customer_profile",
        method="POST",
        path="/asset",
        operation_safety="query",
        response_schema={
            "type": "object",
            "properties": {
                "result": {
                    "type": "object",
                    "properties": {
                        "summaryCard": {
                            "type": "object",
                            "properties": {
                                "storeFundCount": {"type": "integer", "description": "储值方案项目金数量"},
                                "storeLeftFunds": {"type": "number", "description": "可用规划金额"},
                            },
                        },
                        "deliveryRecords": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"deliveryProject": {"type": "string", "description": "交付项目"}},
                            },
                        },
                        "curePlanRecords": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"fProductBillProjectName": {"type": "string", "description": "治疗项目名称"}},
                            },
                        },
                    },
                }
            },
        },
        predecessors=[build_encrypted_id_predecessor()],
    )
    return CustomerProfileEndpointCatalog(
        entries_by_id={lookup.id: lookup, identity.id: identity, asset.id: asset},
        sections=[
            CustomerProfileSection("identity_contact", "一、身份与联系信息", "identity"),
            CustomerProfileSection("asset_overview", "十六、历史购买储值方案/规划方案/剩余项目金", "asset"),
        ],
    )


def build_encrypted_id_predecessor():
    from app.services.api_catalog.schema import ApiCatalogPredecessorParamBinding, ApiCatalogPredecessorSpec

    return ApiCatalogPredecessorSpec(
        predecessor_api_id=_CUSTOMER_LOOKUP_API_ID,
        required=True,
        order=1,
        param_bindings=[
            ApiCatalogPredecessorParamBinding(
                target_param="encryptedIdCard",
                source_path="$.idCard",
                select_mode="user_select",
            )
        ],
    )
