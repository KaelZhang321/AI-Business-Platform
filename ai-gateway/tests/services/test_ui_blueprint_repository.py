from __future__ import annotations

import pytest

import app.services.api_catalog.ui_blueprint_repository as repository_module
from app.services.api_catalog.ui_blueprint_repository import UiBlueprintRepository, UiBlueprintRepositoryError


class FakeCursor:
    """按查询顺序回放结果的游标桩。"""

    def __init__(self, query_rows: list[list[dict[str, object]]], capture: dict[str, object]) -> None:
        self._query_rows = query_rows
        self._capture = capture
        self._current_rows: list[dict[str, object]] = []

    async def execute(self, sql: str, params=None) -> None:
        executed = self._capture.setdefault("sqls", [])
        assert isinstance(executed, list)
        executed.append(sql)
        self._capture["params"] = params
        idx = int(self._capture.get("global_execute_count", 0))
        self._current_rows = self._query_rows[idx]
        self._capture["global_execute_count"] = idx + 1

    async def fetchall(self) -> list[dict[str, object]]:
        return list(self._current_rows)

    async def fetchone(self) -> dict[str, object] | None:
        rows = self._current_rows
        return dict(rows[0]) if rows else None


class FakeCursorContext:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    async def __aenter__(self) -> FakeCursor:
        return self._cursor

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConnection:
    def __init__(self, query_rows: list[list[dict[str, object]]], capture: dict[str, object]) -> None:
        self._query_rows = query_rows
        self._capture = capture

    def cursor(self, cursor_cls) -> FakeCursorContext:
        self._capture["cursor_cls"] = cursor_cls
        return FakeCursorContext(FakeCursor(self._query_rows, self._capture))


class FakeAcquireContext:
    def __init__(self, query_rows: list[list[dict[str, object]]], capture: dict[str, object]) -> None:
        self._query_rows = query_rows
        self._capture = capture

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection(self._query_rows, self._capture)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakePool:
    def __init__(self, query_rows: list[list[dict[str, object]]], capture: dict[str, object]) -> None:
        self._query_rows = query_rows
        self._capture = capture
        self.closed = False
        self.wait_closed_called = False

    def acquire(self) -> FakeAcquireContext:
        return FakeAcquireContext(self._query_rows, self._capture)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.wait_closed_called = True


@pytest.mark.asyncio
async def test_ui_blueprint_repository_loads_partition_rules() -> None:
    """应把 ui_blueprint_dict 规则转换成分区快照。"""

    capture: dict[str, object] = {}
    fake_pool = FakePool(
        [
            [{"1": 1}],
            [
                {"COLUMN_NAME": "id"},
                {"COLUMN_NAME": "display_domain_code"},
                {"COLUMN_NAME": "display_domain_label"},
                {"COLUMN_NAME": "display_section_code"},
                {"COLUMN_NAME": "display_section_label"},
                {"COLUMN_NAME": "typical_fields"},
                {"COLUMN_NAME": "priority"},
                {"COLUMN_NAME": "is_active"},
            ],
            [
                {
                    "id": 1,
                    "display_domain_code": "customer",
                    "display_domain_label": "客户档案",
                    "display_section_code": "basic_info",
                    "display_section_label": "基本信息",
                    "typical_fields": '["customer_id","name"]',
                    "priority": 10,
                    "is_active": 1,
                }
            ],
        ],
        capture,
    )

    repository = UiBlueprintRepository(pool=fake_pool)  # type: ignore[arg-type]
    snapshot = await repository.load_snapshot()
    await repository.close()

    assert len(snapshot.rules) == 1
    rule = snapshot.rules[0]
    assert rule.display_domain_code == "customer"
    assert rule.display_section_code == "basic_info"
    assert rule.typical_fields == ["customer_id", "name"]
    assert capture["cursor_cls"] is repository_module.aiomysql.DictCursor
    assert fake_pool.closed is False
    assert fake_pool.wait_closed_called is False


@pytest.mark.asyncio
async def test_ui_blueprint_repository_returns_empty_when_table_missing() -> None:
    """当 ui_blueprint_dict 未部署时应降级为空快照，不阻断治理任务。"""

    capture: dict[str, object] = {}
    fake_pool = FakePool([[]], capture)
    repository = UiBlueprintRepository(pool=fake_pool)  # type: ignore[arg-type]
    snapshot = await repository.load_snapshot()
    await repository.close()

    assert snapshot.rules == []


@pytest.mark.asyncio
async def test_ui_blueprint_repository_requires_injected_pool() -> None:
    """未注入业务库连接池时应立即报错，避免运行期偷偷建池。"""

    repository = UiBlueprintRepository()

    with pytest.raises(UiBlueprintRepositoryError, match="业务库连接池未注入"):
        await repository.load_snapshot()
