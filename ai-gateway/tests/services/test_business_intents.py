from __future__ import annotations

import pytest

import app.services.api_catalog.business_intents as business_intents_module
from app.services.api_catalog.business_intents import (
    BusinessIntentCatalogService,
    NOOP_BUSINESS_INTENT,
    normalize_business_intent_code,
    normalize_business_intent_codes,
    resolve_business_intent_risk_level,
)


class FakeCursor:
    """按 SQL 关键字回放不同结果集，模拟两张治理表的读取。"""

    def __init__(self, rows_by_sql: dict[str, list[dict]], capture: dict[str, object]) -> None:
        self._rows_by_sql = rows_by_sql
        self._capture = capture
        self._current_sql = ""

    async def execute(self, sql: str) -> None:
        self._current_sql = sql
        self._capture.setdefault("sqls", []).append(sql)

    async def fetchall(self) -> list[dict]:
        if "FROM ui_business_intent_aliases" in self._current_sql:
            return list(self._rows_by_sql["aliases"])
        return list(self._rows_by_sql["intents"])


class FakeCursorContext:
    """让测试桩符合 aiomysql 的异步上下文协议。"""

    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    async def __aenter__(self) -> FakeCursor:
        return self._cursor

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConnection:
    """模拟连接对象，确保源码仍按 DictCursor 读取业务意图目录。"""

    def __init__(self, rows_by_sql: dict[str, list[dict]], capture: dict[str, object]) -> None:
        self._rows_by_sql = rows_by_sql
        self._capture = capture

    def cursor(self, cursor_cls) -> FakeCursorContext:
        self._capture["cursor_cls"] = cursor_cls
        return FakeCursorContext(FakeCursor(self._rows_by_sql, self._capture))


class FakeAcquireContext:
    """模拟 `pool.acquire()` 返回值。"""

    def __init__(self, rows_by_sql: dict[str, list[dict]], capture: dict[str, object]) -> None:
        self._rows_by_sql = rows_by_sql
        self._capture = capture

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection(self._rows_by_sql, self._capture)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakePool:
    """连接池测试桩，用来验证预热和 close 生命周期。"""

    def __init__(self, rows_by_sql: dict[str, list[dict]], capture: dict[str, object]) -> None:
        self._rows_by_sql = rows_by_sql
        self._capture = capture
        self.closed = False
        self.wait_closed_called = False

    def acquire(self) -> FakeAcquireContext:
        return FakeAcquireContext(self._rows_by_sql, self._capture)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.wait_closed_called = True


def _intent_rows() -> list[dict]:
    return [
        {
            "code": "none",
            "name": "纯查询",
            "category": "read",
            "description": "只读请求",
            "risk_level": "none",
            "enabled": 1,
            "status": "active",
            "allow_in_router": 1,
            "allow_in_response": 1,
            "sort_order": 10,
            "is_builtin": 1,
        },
        {
            "code": "saveToServer",
            "name": "保存业务数据",
            "category": "write",
            "description": "写入业务系统",
            "risk_level": "medium",
            "enabled": 1,
            "status": "active",
            "allow_in_router": 1,
            "allow_in_response": 1,
            "sort_order": 20,
            "is_builtin": 0,
        },
        {
            "code": "deleteCustomer",
            "name": "删除客户数据",
            "category": "write",
            "description": "删除客户",
            "risk_level": "high",
            "enabled": 0,
            "status": "active",
            "allow_in_router": 1,
            "allow_in_response": 1,
            "sort_order": 30,
            "is_builtin": 0,
        },
    ]


def _alias_rows() -> list[dict]:
    return [
        {
            "alias_code": "prepare_record_update",
            "canonical_code": "saveToServer",
            "risk_level_override": None,
            "status": "active",
        },
        {
            "alias_code": "prepare_high_risk_change",
            "canonical_code": "saveToServer",
            "risk_level_override": "high",
            "status": "active",
        },
    ]


@pytest.mark.asyncio
async def test_business_intent_catalog_loads_mysql_snapshot_and_normalizes_aliases(monkeypatch) -> None:
    """验证业务意图目录可从 MySQL 预热，并驱动白名单、别名和风险等级判断。"""
    capture: dict[str, object] = {}
    fake_pool = FakePool({"intents": _intent_rows(), "aliases": _alias_rows()}, capture)
    service = BusinessIntentCatalogService(pool=fake_pool)  # type: ignore[arg-type]
    monkeypatch.setattr(business_intents_module, "_catalog_service", service)

    await service.warmup()

    assert any("FROM ui_business_intents" in sql for sql in capture["sqls"])
    assert any("FROM ui_business_intent_aliases" in sql for sql in capture["sqls"])

    # deleteCustomer 在 MySQL 中被禁用后，不应继续进入 Router allowlist。
    assert service.get_allowed_codes() == {NOOP_BUSINESS_INTENT, "saveToServer"}
    assert normalize_business_intent_code("prepare_record_update") == "saveToServer"
    assert normalize_business_intent_codes(["query_business_data"]) == ["none"]
    assert normalize_business_intent_codes(["prepare_record_update"]) == ["saveToServer"]
    assert resolve_business_intent_risk_level("saveToServer", ["saveToServer"]) == "medium"
    assert resolve_business_intent_risk_level("saveToServer", ["prepare_high_risk_change"]) == "high"

    await service.close()
    assert fake_pool.closed is False
    assert fake_pool.wait_closed_called is False


@pytest.mark.asyncio
async def test_business_intent_catalog_keeps_builtin_snapshot_when_mysql_unavailable(monkeypatch) -> None:
    """MySQL 不可用时必须保留内置语义，避免第二阶段把全部写意图误降级成 none。"""

    service = BusinessIntentCatalogService()
    monkeypatch.setattr(business_intents_module, "_catalog_service", service)

    await service.warmup()

    assert service.get_allowed_codes() == {"none", "saveToServer", "deleteCustomer"}
    assert normalize_business_intent_codes(["prepare_high_risk_change"]) == ["saveToServer"]
    assert resolve_business_intent_risk_level("saveToServer", ["prepare_high_risk_change"]) == "high"

    await service.close()


@pytest.mark.asyncio
async def test_business_intent_catalog_requires_injected_pool_for_warmup(monkeypatch) -> None:
    """未注入业务库连接池时，warmup 应走内置降级而不是偷偷建池。"""

    service = BusinessIntentCatalogService()
    monkeypatch.setattr(business_intents_module, "_catalog_service", service)

    await service.warmup()

    assert service.get_allowed_codes() == {"none", "saveToServer", "deleteCustomer"}
