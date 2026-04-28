from __future__ import annotations

from typing import Any

import pytest

from app.services.model_runtime_config_service import ModelRuntimeConfigService, ModelRuntimeConfigServiceError


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    async def __aenter__(self) -> _FakeCursor:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self.executed.append((sql, params))

    async def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._cursor = _FakeCursor(rows)
        self.committed = False

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    def cursor(self, *args, **kwargs) -> _FakeCursor:  # noqa: ANN002, ANN003
        del args, kwargs
        return self._cursor

    async def commit(self) -> None:
        self.committed = True


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class _FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._conn = _FakeConn(rows)

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self._conn)


@pytest.mark.asyncio
async def test_model_runtime_config_service_normalizes_chat_path_and_sorts_priority() -> None:
    """配置服务应修正绝对路径并遵循优先级排序，避免路由错发。"""

    rows = [
        {
            "backend_name": "secondary",
            "backend_type": "openai",
            "base_url": "https://api.example.com/v1",
            "model_name": "model-b",
            "api_key": "k2",
            "chat_path": "/chat/completions",
            "priority": 10,
            "enabled": 1,
        },
        {
            "backend_name": "primary",
            "backend_type": "openai",
            "base_url": "https://api.example.com/v1",
            "model_name": "model-a",
            "api_key": "k1",
            "chat_path": "/v1/chat/completions",
            "priority": 0,
            "enabled": 1,
        },
    ]
    service = ModelRuntimeConfigService(cache_ttl_seconds=60)
    service._table_ready = True
    service._pool = _FakePool(rows)  # type: ignore[assignment]

    backends = await service.get_backends("api.query")

    assert [backend.name for backend in backends] == ["primary", "secondary"]
    assert backends[0].chat_path == "v1/chat/completions"
    assert backends[1].chat_path == "chat/completions"


@pytest.mark.asyncio
async def test_model_runtime_config_service_uses_cache_to_avoid_repeated_db_read() -> None:
    """同 service_code 在 TTL 内应命中缓存，避免重复数据库查询。"""

    rows = [
        {
            "backend_name": "primary",
            "backend_type": "openai",
            "base_url": "https://api.example.com/v1",
            "model_name": "model-a",
            "api_key": "k1",
            "chat_path": "chat/completions",
            "priority": 0,
            "enabled": 1,
        }
    ]
    service = ModelRuntimeConfigService(cache_ttl_seconds=60)
    service._table_ready = True
    pool = _FakePool(rows)
    service._pool = pool  # type: ignore[assignment]

    first = await service.get_backends("gateway.default")
    second = await service.get_backends("gateway.default")

    assert [backend.name for backend in first] == ["primary"]
    assert [backend.name for backend in second] == ["primary"]
    # 一次 DDL 之外，只应有一次真正的 SELECT 查询。
    executed_sql_count = len(pool._conn._cursor.executed)
    assert executed_sql_count == 1


@pytest.mark.asyncio
async def test_model_runtime_config_service_raises_when_no_rows() -> None:
    """当 service_code 无可用配置时必须显式报错，防止链路静默失效。"""

    service = ModelRuntimeConfigService(cache_ttl_seconds=60)
    service._table_ready = True
    service._pool = _FakePool([])  # type: ignore[assignment]

    with pytest.raises(ModelRuntimeConfigServiceError, match="未配置启用中的模型后端"):
        await service.get_backends("health.quadrant")
