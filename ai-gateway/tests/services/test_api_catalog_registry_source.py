from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource


def _ok_page(data: list[dict], *, total: int | None = None) -> dict:
    return {
        "code": 200,
        "message": "success",
        "data": {
            "data": data,
            "total": len(data) if total is None else total,
            "page": 1,
            "size": 100,
        },
    }


@pytest.mark.asyncio
async def test_registry_source_loads_ui_builder_entries_and_merges_overlay(tmp_path, monkeypatch) -> None:
    overlay = tmp_path / "api_catalog.yaml"
    overlay.write_text(
        """
apis:
  - id: customer_list_overlay
    description: 查询客户列表
    domain: crm
    method: GET
    path: /api/customer/list
    response_data_path: data.list
    field_labels:
      customerId: 客户ID
    pagination_hint:
      enabled: true
      api_id: customer_list_overlay
      page_param: page
      page_size_param: size
      mutation_target: report-table.props.dataSource
""".strip(),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/ui-builder/sources":
            return httpx.Response(
                200,
                json=_ok_page(
                    [
                        {
                            "id": "src_1",
                            "code": "crm",
                            "name": "CRM接口",
                            "sourceType": "openapi",
                            "baseUrl": "http://business-server",
                            "authType": "bearer",
                            "authConfig": "{\"mode\":\"token\"}",
                            "defaultHeaders": "{\"X-App\":\"ui-builder\"}",
                            "env": "prod",
                            "status": "active",
                        }
                    ]
                ),
            )
        if request.url.path == "/api/v1/ui-builder/sources/src_1/tags":
            return httpx.Response(
                200,
                json=_ok_page(
                    [
                        {
                            "id": "tag_customer",
                            "name": "客户管理",
                        }
                    ]
                ),
            )
        if request.url.path == "/api/v1/ui-builder/sources/src_1/endpoints":
            return httpx.Response(
                200,
                json=_ok_page(
                    [
                        {
                            "id": "ep_1",
                            "name": "客户列表",
                            "path": "/api/customer/list",
                            "method": "GET",
                            "summary": "查询当前登录用户名下的客户列表",
                            "requestSchema": "{\"type\":\"object\",\"properties\":{\"page\":{\"type\":\"integer\"}}}",
                            "responseSchema": "{\"type\":\"object\",\"properties\":{\"data\":{\"type\":\"object\",\"properties\":{\"list\":{\"type\":\"array\",\"items\":{\"type\":\"object\",\"properties\":{\"customerId\":{\"type\":\"string\",\"description\":\"客户ID\"}}}}}}}}",
                            "sampleRequest": "{\"page\":1}",
                            "status": "active",
                            "tagId": "tag_customer",
                        }
                    ]
                ),
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    monkeypatch.setattr(settings, "api_catalog_source_mode", "ui_builder")
    client = httpx.AsyncClient(base_url="http://testserver", transport=httpx.MockTransport(handler))
    source = ApiCatalogRegistrySource(client=client)

    entries = await source.load_entries(str(overlay))
    await source.close()

    entry_by_path = {entry.path: entry for entry in entries}
    customer_entry = entry_by_path["/api/customer/list"]
    assert customer_entry.id == "customer_list_overlay"
    assert customer_entry.domain == "crm"
    assert customer_entry.env == "prod"
    assert customer_entry.tag_name == "客户管理"
    assert customer_entry.executor_config["base_url"] == "http://business-server"
    assert customer_entry.security_rules["read_only"] is True
    assert customer_entry.response_data_path == "data.list"
    assert customer_entry.pagination_hint.enabled is True
    assert customer_entry.field_labels["customerId"] == "客户ID"
    assert customer_entry.response_schema["type"] == "object"
    assert customer_entry.sample_request == {"page": 1}
    assert customer_entry.api_schema["response_schema"]["type"] == "object"
    assert customer_entry.api_schema["sample_request"] == {"page": 1}

    dict_entry = entry_by_path["/api/system/dicts"]
    assert dict_entry.id == "system_dicts_v1"
    assert dict_entry.api_schema["request"]["properties"]["types"]["allowed_values"] == [
        "customer_region",
        "customer_level",
        "industry",
        "contract_type",
    ]
    assert dict_entry.api_schema["sample_request"] == {"types": "customer_region,customer_level"}


@pytest.mark.asyncio
async def test_registry_source_falls_back_to_overlay_in_hybrid_mode(tmp_path, monkeypatch) -> None:
    overlay = tmp_path / "api_catalog.yaml"
    overlay.write_text(
        """
apis:
  - id: fallback_customer_list
    description: 查询客户列表
    domain: crm
    method: GET
    path: /api/customer/list
""".strip(),
        encoding="utf-8",
    )

    async def failing_get(*args, **kwargs):  # pragma: no cover - invoked via registry source
        raise httpx.ConnectError("boom")

    client = httpx.AsyncClient(base_url="http://testserver")
    monkeypatch.setattr(client, "get", failing_get)
    monkeypatch.setattr(settings, "api_catalog_source_mode", "hybrid")
    source = ApiCatalogRegistrySource(client=client)

    entries = await source.load_entries(str(overlay))
    await source.close()

    assert any(entry.id == "fallback_customer_list" for entry in entries)
    assert any(entry.path == "/api/system/dicts" for entry in entries)
