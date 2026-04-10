from __future__ import annotations

import pytest

import app.services.api_catalog.registry_source as registry_source_module
from app.core.config import settings
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource, ApiCatalogSourceError


class FakeCursor:
    """模拟 MySQL 游标，专门用于捕获 registry SQL 和回放固定结果。"""

    def __init__(self, rows: list[dict], capture: dict[str, object]) -> None:
        self._rows = rows
        self._capture = capture

    async def execute(self, sql: str, params=None) -> None:
        self._capture["sql"] = sql
        self._capture["params"] = params

    async def fetchall(self) -> list[dict]:
        return list(self._rows)


class FakeCursorContext:
    """让测试桩符合 aiomysql 的异步上下文协议。"""

    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    async def __aenter__(self) -> FakeCursor:
        return self._cursor

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConnection:
    """模拟连接对象，确保源码仍按 DictCursor 读取联表结果。"""

    def __init__(self, rows: list[dict], capture: dict[str, object]) -> None:
        self._rows = rows
        self._capture = capture

    def cursor(self, cursor_cls) -> FakeCursorContext:
        self._capture["cursor_cls"] = cursor_cls
        return FakeCursorContext(FakeCursor(self._rows, self._capture))


class FakeAcquireContext:
    """模拟 `pool.acquire()` 返回值，复刻 aiomysql 的双层异步上下文。"""

    def __init__(self, rows: list[dict], capture: dict[str, object]) -> None:
        self._rows = rows
        self._capture = capture

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection(self._rows, self._capture)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakePool:
    """连接池测试桩，用来验证懒加载和 close 生命周期是否正确收口。"""

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
    """构造最小联表结果，覆盖目录主链路实际依赖的关键字段。"""
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
        "operationSafety": "query",
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
async def test_registry_source_loads_entries_from_mysql_and_appends_builtin_dict(monkeypatch) -> None:
    """验证唯一主链路：MySQL 联表成功后产出标准目录并自动补齐 builtin 字典接口。"""
    capture: dict[str, object] = {}
    fake_pool = FakePool([_mysql_row()], capture)

    async def fake_create_pool(**kwargs):
        capture["conn_kwargs"] = kwargs
        return fake_pool

    monkeypatch.setattr(settings, "business_mysql_host", "ai-platform-mysql")
    monkeypatch.setattr(settings, "business_mysql_port", 3306)
    monkeypatch.setattr(settings, "business_mysql_user", "ai_platform")
    monkeypatch.setattr(settings, "business_mysql_password", "ai_platform_dev")
    monkeypatch.setattr(settings, "business_mysql_database", "ai_platform_business")
    monkeypatch.setattr(settings, "api_catalog_mysql_connect_timeout_seconds", 7.5)
    monkeypatch.setattr(registry_source_module.aiomysql, "create_pool", fake_create_pool)

    source = ApiCatalogRegistrySource()
    entries = await source.load_entries()
    await source.close()

    assert capture["conn_kwargs"] == {
        "host": "ai-platform-mysql",
        "port": 3306,
        "user": "ai_platform",
        "password": "ai_platform_dev",
        "db": "ai_platform_business",
        "charset": "utf8mb4",
        "connect_timeout": 7.5,
        "minsize": 1,
        "maxsize": 5,
    }
    assert "FROM ui_api_endpoints e" in str(capture["sql"])
    assert fake_pool.closed is True
    assert fake_pool.wait_closed_called is True

    entry_by_path = {entry.path: entry for entry in entries}
    customer_entry = entry_by_path["/api/customer/list"]
    assert customer_entry.id == "ep_1"
    assert customer_entry.domain == "crm"
    assert customer_entry.env == "prod"
    assert customer_entry.tag_name == "客户管理"
    assert customer_entry.operation_safety == "query"
    assert customer_entry.executor_config["base_url"] == "http://business-server"
    assert customer_entry.executor_config["executor_type"] == "runtime_invoke"
    assert customer_entry.security_rules["read_only"] is True
    assert customer_entry.security_rules["query_safe"] is True
    assert customer_entry.response_data_path == "data.list"
    assert customer_entry.response_schema["type"] == "object"
    assert customer_entry.sample_request == {"page": 1}
    assert customer_entry.api_schema["response_schema"]["type"] == "object"
    assert customer_entry.api_schema["sample_request"] == {"page": 1}

    dict_entry = entry_by_path["/api/system/dicts"]
    assert dict_entry.id == "system_dicts_v1"
    assert dict_entry.operation_safety == "query"
    assert dict_entry.api_schema["request"]["properties"]["types"]["allowed_values"] == [
        "customer_region",
        "customer_level",
        "industry",
        "contract_type",
    ]
    assert dict_entry.api_schema["sample_request"] == {"types": "customer_region,customer_level"}


@pytest.mark.asyncio
async def test_registry_source_raises_when_mysql_load_fails(monkeypatch) -> None:
    """MySQL 是唯一权威来源，连接失败时必须硬失败，避免静默回退到过期配置。"""

    async def failing_create_pool(**kwargs):  # pragma: no cover - invoked via registry source
        raise RuntimeError("boom")

    monkeypatch.setattr(registry_source_module.aiomysql, "create_pool", failing_create_pool)

    source = ApiCatalogRegistrySource()
    with pytest.raises(ApiCatalogSourceError, match="无法从 MySQL 加载注册表"):
        await source.load_entries()
    await source.close()


@pytest.mark.asyncio
async def test_registry_source_get_entry_by_id_hits_mysql_exactly_once(monkeypatch) -> None:
    """`direct` 快路必须支持按主键精确查目录，不能退化成全量加载。"""
    capture: dict[str, object] = {}
    fake_pool = FakePool([_mysql_row()], capture)

    async def fake_create_pool(**kwargs):
        return fake_pool

    monkeypatch.setattr(registry_source_module.aiomysql, "create_pool", fake_create_pool)

    source = ApiCatalogRegistrySource()
    entry = await source.get_entry_by_id("ep_1")
    await source.close()

    assert entry is not None
    assert entry.id == "ep_1"
    assert "AND e.id = %s" in str(capture["sql"])
    assert capture["params"] == ("ep_1",)


@pytest.mark.asyncio
async def test_registry_source_get_entry_by_id_returns_builtin_dict_without_mysql(monkeypatch) -> None:
    """内置字典接口不在 MySQL 中持久化，快路必须能在网关内直接命中。"""
    mysql_called = False

    async def fake_create_pool(**kwargs):  # pragma: no cover - should never be invoked
        nonlocal mysql_called
        mysql_called = True
        raise AssertionError("builtin dict lookup should not hit mysql")

    monkeypatch.setattr(registry_source_module.aiomysql, "create_pool", fake_create_pool)

    source = ApiCatalogRegistrySource()
    entry = await source.get_entry_by_id("system_dicts_v1")
    await source.close()

    assert entry is not None
    assert entry.id == "system_dicts_v1"
    assert mysql_called is False
