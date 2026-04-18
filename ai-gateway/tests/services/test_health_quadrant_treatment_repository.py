from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.health_quadrant_treatment_repository import HealthQuadrantTreatmentRepository


class FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.executed: list[tuple[str, str]] = []

    async def execute(self, sql: str, belong_system: str) -> None:
        self.executed.append((sql, belong_system))

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
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self, cursor_cls) -> FakeCursorContext:
        return FakeCursorContext(self._cursor)


class FakeAcquireContext:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection(self._cursor)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakePool:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def acquire(self) -> FakeAcquireContext:
        return FakeAcquireContext(self._cursor)


class FakeMySQLPools:
    def __init__(self, cursor: FakeCursor) -> None:
        self._pool = FakePool(cursor)
        self.closed = False

    async def get_business_pool(self):
        return self._pool

    async def close(self) -> None:
        self.closed = True


@dataclass
class FakeTriageItem:
    item_name: str
    quadrant: str
    belong_system: str


@pytest.mark.asyncio
async def test_query_one_triage_item_empty_belong_system_returns_empty_without_query() -> None:
    cursor = FakeCursor(rows=[{"project_name": "A", "package_version": "v1"}])
    repo = HealthQuadrantTreatmentRepository(mysql_pools=FakeMySQLPools(cursor))

    rows = await repo._query_one_triage_item(
        cursor=cursor,
        belong_system="",
        trigger_item="胸闷",
        quadrant="RED",
    )

    assert rows == []
    assert cursor.executed == []


@pytest.mark.asyncio
async def test_match_candidates_deduplicates_rows_across_triage_items() -> None:
    cursor = FakeCursor(
        rows=[
            {
                "project_name": "冠脉风险高级评估",
                "package_version": "v1",
                "core_effect": "核心作用",
                "indications": "适应症",
                "contraindications": "禁忌",
            },
            {
                "project_name": "冠脉风险高级评估",
                "package_version": "v1",
                "core_effect": "重复行",
                "indications": "重复",
                "contraindications": "重复",
            },
            {
                "project_name": "代谢专项管理",
                "package_version": "v2",
                "core_effect": "代谢",
                "indications": "血糖升高",
                "contraindications": "",
            },
        ]
    )
    repo = HealthQuadrantTreatmentRepository(mysql_pools=FakeMySQLPools(cursor))

    rows = await repo.match_candidates(
        triage_items=[
            FakeTriageItem(item_name="胸闷", quadrant="RED", belong_system="心脑血管"),
            FakeTriageItem(item_name="胸闷复发", quadrant="RED", belong_system="心脑血管"),
        ]
    )

    # 按 project+version+quadrant+system 去重，跨 triage 条目不重复叠加。
    assert len(rows) == 2
    assert {row["project_name"] for row in rows} == {"冠脉风险高级评估", "代谢专项管理"}
    assert all(row["quadrant"] == "RED" for row in rows)
    assert all(row["belong_system"] == "心脑血管" for row in rows)

