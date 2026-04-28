from __future__ import annotations

import pytest

import app.services.api_catalog.semantic_field_repository as repository_module
from app.services.api_catalog.semantic_field_repository import SemanticFieldRepository, SemanticFieldRepositoryError


class FakeCursor:
    """模拟治理仓储游标，按查询顺序回放三张表结果。"""

    def __init__(self, query_rows: list[list[dict[str, object]]], capture: dict[str, object]) -> None:
        self._query_rows = query_rows
        self._capture = capture
        self._current_rows: list[dict[str, object]] = []

    async def execute(self, sql: str, params=None) -> None:
        executed_sqls = self._capture.setdefault("sqls", [])
        assert isinstance(executed_sqls, list)
        executed_sqls.append(sql)
        self._capture["params"] = params
        execute_count = int(self._capture.get("global_execute_count", 0))
        self._current_rows = self._query_rows[execute_count]
        self._capture["global_execute_count"] = execute_count + 1

    async def fetchall(self) -> list[dict[str, object]]:
        return list(self._current_rows)


class FakeCursorContext:
    """让测试桩符合 aiomysql 的异步上下文协议。"""

    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    async def __aenter__(self) -> FakeCursor:
        return self._cursor

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConnection:
    """模拟连接对象，确保仓储继续按 DictCursor 读取治理表。"""

    def __init__(self, query_rows: list[list[dict[str, object]]], capture: dict[str, object]) -> None:
        self._query_rows = query_rows
        self._capture = capture

    def cursor(self, cursor_cls) -> FakeCursorContext:
        self._capture["cursor_cls"] = cursor_cls
        return FakeCursorContext(FakeCursor(self._query_rows, self._capture))


class FakeAcquireContext:
    """模拟 `pool.acquire()` 返回值，复刻 aiomysql 的双层异步上下文。"""

    def __init__(self, query_rows: list[list[dict[str, object]]], capture: dict[str, object]) -> None:
        self._query_rows = query_rows
        self._capture = capture

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection(self._query_rows, self._capture)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakePool:
    """连接池测试桩，用来验证懒加载与 close 生命周期。"""

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


def _field_dict_row() -> dict[str, object]:
    return {
        "semantic_key": "Customer.id",
        "standard_key": "customerId",
        "entity_code": "Customer",
        "canonical_name": "id",
        "label": "客户ID",
        "field_type": "text",
        "value_type": "string",
        "category": "business",
        "business_domain": "crm",
        "display_domain_code": "customer",
        "display_domain_label": "客户",
        "display_section_code": "basic",
        "display_section_label": "基本信息",
        "graph_role": "identifier",
        "is_identifier": 1,
        "is_graph_enabled": "true",
        "valueSchema": '{"enum": ["C001"]}',
        "description": "客户主键",
        "is_active": 1,
        "run_id": "R_20260413_100000_abc123",
        "review_status": "approved",
        "current_flag": 1,
        "risk_level": "high",
        "human_lock": 0,
        "conflict_streak": 0,
    }


def _alias_row() -> dict[str, object]:
    return {
        "semantic_key": "Customer.id",
        "alias": "customerId",
        "scope_type": "domain",
        "scope_value": "crm",
        "direction": "response",
        "location": "response",
        "json_path_pattern": "data.records[*].customerId",
        "source": "manual",
        "confidence": 0.93,
        "priority": 10,
        "is_active": 1,
        "run_id": "R_20260413_100000_abc123",
        "review_status": "approved",
        "current_flag": 1,
        "human_lock": 0,
        "conflict_streak": 0,
    }


def _value_map_row() -> dict[str, object]:
    return {
        "semantic_key": "Customer.status",
        "scope_type": "global",
        "scope_value": "*",
        "standard_code": "active",
        "standard_label": "启用",
        "raw_value": "1",
        "raw_label": "正常",
        "sort_order": 5,
        "source": "manual",
        "confidence": 0.88,
        "is_active": 1,
        "run_id": "R_20260413_100000_abc123",
        "review_status": "approved",
        "current_flag": 1,
        "human_lock": 0,
        "conflict_streak": 0,
    }


def _column_rows(*column_names: str) -> list[dict[str, object]]:
    return [{"COLUMN_NAME": name} for name in column_names]


@pytest.mark.asyncio
async def test_semantic_field_repository_loads_rules_from_mysql() -> None:
    """验证三张治理表会被依次读取，并转换成类型化快照。"""

    capture: dict[str, object] = {}
    fake_pool = FakePool(
        [
            _column_rows(
                "semantic_key",
                "standard_key",
                "entity_code",
                "canonical_name",
                "label",
                "field_type",
                "value_type",
                "category",
                "business_domain",
                "display_domain_code",
                "display_domain_label",
                "display_section_code",
                "display_section_label",
                "graph_role",
                "is_identifier",
                "is_graph_enabled",
                "value_schema",
                "description",
                "is_active",
                "run_id",
                "review_status",
                "current_flag",
                "risk_level",
                "human_lock",
                "conflict_streak",
            ),
            _column_rows(
                "semantic_key",
                "alias",
                "scope_type",
                "scope_value",
                "direction",
                "location",
                "json_path_pattern",
                "source",
                "confidence",
                "priority",
                "is_active",
                "run_id",
                "review_status",
                "current_flag",
                "human_lock",
                "conflict_streak",
            ),
            _column_rows(
                "semantic_key",
                "scope_type",
                "scope_value",
                "standard_code",
                "standard_label",
                "raw_value",
                "raw_label",
                "sort_order",
                "source",
                "confidence",
                "is_active",
                "run_id",
                "review_status",
                "current_flag",
                "human_lock",
                "conflict_streak",
            ),
            [_field_dict_row()],
            [_alias_row()],
            [_value_map_row()],
        ],
        capture,
    )

    repository = SemanticFieldRepository(pool=fake_pool)  # type: ignore[arg-type]
    snapshot = await repository.load_active_rules()
    await repository.close()

    assert capture["cursor_cls"] is repository_module.aiomysql.DictCursor
    assert len(capture["sqls"]) == 6
    assert "INFORMATION_SCHEMA.COLUMNS" in str(capture["sqls"][0])
    assert "INFORMATION_SCHEMA.COLUMNS" in str(capture["sqls"][1])
    assert "INFORMATION_SCHEMA.COLUMNS" in str(capture["sqls"][2])
    assert "FROM semantic_field_dict" in str(capture["sqls"][3])
    assert "FROM semantic_field_alias" in str(capture["sqls"][4])
    assert "FROM semantic_field_value_map" in str(capture["sqls"][5])
    assert "current_flag = 1" in str(capture["sqls"][3])
    assert "review_status = 'approved'" in str(capture["sqls"][3])
    assert fake_pool.closed is False
    assert fake_pool.wait_closed_called is False

    field_dict = snapshot.field_dicts[0]
    assert field_dict.semantic_key == "Customer.id"
    assert field_dict.display_partition_key == "customer.basic"
    assert field_dict.value_schema == {"enum": ["C001"]}
    assert field_dict.is_identifier is True
    assert field_dict.is_graph_enabled is True

    alias = snapshot.aliases[0]
    assert alias.semantic_key == "Customer.id"
    assert alias.scope_type == "domain"
    assert alias.json_path_pattern == "data.records[*].customerId"
    assert alias.confidence == pytest.approx(0.93)

    value_map = snapshot.value_maps[0]
    assert value_map.semantic_key == "Customer.status"
    assert value_map.standard_code == "active"
    assert value_map.raw_label == "正常"
    assert value_map.confidence == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_semantic_field_repository_reuses_injected_pool_between_loads() -> None:
    """同一个仓储实例重复读取时，应复用同一个注入 pool。"""

    capture: dict[str, object] = {"create_pool_calls": 0}
    fake_pool = FakePool(
        [
            _column_rows(*_field_dict_row().keys()),
            _column_rows(*_alias_row().keys()),
            _column_rows(*_value_map_row().keys()),
            [_field_dict_row()],
            [_alias_row()],
            [_value_map_row()],
            [_field_dict_row()],
            [_alias_row()],
            [_value_map_row()],
        ],
        capture,
    )

    repository = SemanticFieldRepository(pool=fake_pool)  # type: ignore[arg-type]
    first_snapshot = await repository.load_active_rules()
    second_snapshot = await repository.load_active_rules()
    await repository.close()

    assert first_snapshot.field_dicts[0].semantic_key == "Customer.id"
    assert second_snapshot.aliases[0].semantic_key == "Customer.id"
    assert capture["create_pool_calls"] == 0


@pytest.mark.asyncio
async def test_semantic_field_repository_requires_injected_pool() -> None:
    """未注入业务库连接池时必须抛出语义化仓储异常。"""

    repository = SemanticFieldRepository()
    with pytest.raises(SemanticFieldRepositoryError, match="业务库连接池未注入"):
        await repository.load_active_rules()
    await repository.close()


@pytest.mark.asyncio
async def test_semantic_field_repository_close_is_noop_without_pool() -> None:
    """close 在未建连场景下应保持幂等，避免测试和脚本额外判断状态。"""

    repository = SemanticFieldRepository()
    await repository.close()
