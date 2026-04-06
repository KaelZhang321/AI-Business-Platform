from __future__ import annotations

import pytest

import app.services.api_catalog.registry_source as registry_source_module
from app.core.config import settings
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource


class FakeCursor:
    def __init__(self, rows: list[dict], capture: dict[str, object]) -> None:
        self._rows = rows
        self._capture = capture

    async def execute(self, sql: str) -> None:
        self._capture["sql"] = sql

    async def fetchall(self) -> list[dict]:
        return list(self._rows)


class FakeCursorContext:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    async def __aenter__(self) -> FakeCursor:
        return self._cursor

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConnection:
    def __init__(self, rows: list[dict], capture: dict[str, object]) -> None:
        self._rows = rows
        self._capture = capture

    def cursor(self, cursor_cls) -> FakeCursorContext:
        self._capture["cursor_cls"] = cursor_cls
        return FakeCursorContext(FakeCursor(self._rows, self._capture))


class FakeAcquireContext:
    def __init__(self, rows: list[dict], capture: dict[str, object]) -> None:
        self._rows = rows
        self._capture = capture

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection(self._rows, self._capture)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakePool:
    def __init__(self, rows: list[dict], capture: dict[str, object]) -> None:
        self._rows = rows
        self._capture = capture
        self.closed = False
        self.wait_closed_called = False

    def acquire(self) -> FakeAcquireContext:
        return FakeAcquireContext(self._rows, self._capture)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.wait_closed_called = True


def _mysql_row() -> dict[str, object]:
    return {
        "endpointId": "ep_1",
        "tagId": "tag_customer",
        "tagName": "客户管理",
        "endpointName": "客户列表",
        "path": "/api/customer/list",
        "method": "GET",
        "summary": "查询当前登录用户名下的客户列表",
        "requestSchema": '{"type":"object","properties":{"page":{"type":"integer"}}}',
        "responseSchema": '{"type":"object","properties":{"data":{"type":"object","properties":{"list":{"type":"array","items":{"type":"object","properties":{"customerId":{"type":"string","description":"客户ID"}}}}}}}}',
        "sampleRequest": '{"page":1}',
        "sampleResponse": '{"data":{"list":[{"customerId":"C001"}]}}',
        "endpointStatus": "active",
        "sourceId": "src_1",
        "sourceCode": "crm",
        "sourceName": "CRM接口",
        "sourceType": "openapi",
        "baseUrl": "http://business-server",
        "docUrl": "http://business-server/doc",
        "authType": "bearer",
        "authConfig": '{"mode":"token"}',
        "defaultHeaders": '{"X-App":"ui-builder"}',
        "env": "prod",
        "sourceStatus": "active",
    }


@pytest.mark.asyncio
async def test_registry_source_loads_mysql_entries_and_merges_overlay(tmp_path, monkeypatch) -> None:
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

    capture: dict[str, object] = {}
    fake_pool = FakePool([_mysql_row()], capture)

    async def fake_create_pool(**kwargs):
        capture["conn_kwargs"] = kwargs
        return fake_pool

    monkeypatch.setattr(settings, "api_catalog_source_mode", "ui_builder")
    monkeypatch.setattr(settings, "business_mysql_host", "ai-platform-mysql")
    monkeypatch.setattr(settings, "business_mysql_port", 3306)
    monkeypatch.setattr(settings, "business_mysql_user", "ai_platform")
    monkeypatch.setattr(settings, "business_mysql_password", "ai_platform_dev")
    monkeypatch.setattr(settings, "business_mysql_database", "ai_platform_business")
    monkeypatch.setattr(registry_source_module.aiomysql, "create_pool", fake_create_pool)

    source = ApiCatalogRegistrySource()
    entries = await source.load_entries(str(overlay))
    await source.close()

    assert capture["conn_kwargs"] == {
        "host": "ai-platform-mysql",
        "port": 3306,
        "user": "ai_platform",
        "password": "ai_platform_dev",
        "db": "ai_platform_business",
        "charset": "utf8mb4",
        "minsize": 1,
        "maxsize": 5,
    }
    assert "FROM ui_api_endpoints e" in str(capture["sql"])
    assert fake_pool.closed is True
    assert fake_pool.wait_closed_called is True

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
async def test_registry_source_falls_back_to_overlay_in_hybrid_mode_when_mysql_fails(tmp_path, monkeypatch) -> None:
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

    async def failing_create_pool(**kwargs):  # pragma: no cover - invoked via registry source
        raise RuntimeError("boom")

    monkeypatch.setattr(settings, "api_catalog_source_mode", "hybrid")
    monkeypatch.setattr(registry_source_module.aiomysql, "create_pool", failing_create_pool)

    source = ApiCatalogRegistrySource()
    entries = await source.load_entries(str(overlay))
    await source.close()

    assert any(entry.id == "fallback_customer_list" for entry in entries)
    assert any(entry.path == "/api/system/dicts" for entry in entries)


@pytest.mark.asyncio
async def test_registry_source_raises_in_ui_builder_mode_when_mysql_fails(monkeypatch) -> None:
    async def failing_create_pool(**kwargs):  # pragma: no cover - invoked via registry source
        raise RuntimeError("boom")

    monkeypatch.setattr(settings, "api_catalog_source_mode", "ui_builder")
    monkeypatch.setattr(registry_source_module.aiomysql, "create_pool", failing_create_pool)

    source = ApiCatalogRegistrySource()
    with pytest.raises(registry_source_module.ApiCatalogSourceError, match="无法从 MySQL 加载注册表"):
        await source.load_entries()
    await source.close()
