from __future__ import annotations

import pytest

from app.services.prompt_template_repository import PromptTemplateRepository, PromptTemplateRepositoryError


class _FakeCursor:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []

    async def __aenter__(self) -> _FakeCursor:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    async def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
        self.executed.append((sql, params))

    async def fetchone(self) -> dict[str, object] | None:
        return self._row


class _FakeConnection:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._cursor = _FakeCursor(row)

    async def __aenter__(self) -> _FakeConnection:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    def cursor(self, *args, **kwargs) -> _FakeCursor:  # noqa: ANN002, ANN003
        del args, kwargs
        return self._cursor


class _FakeAcquire:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConnection:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class _FakePool:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._conn = _FakeConnection(row)

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self._conn)

    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


@pytest.mark.asyncio
async def test_prompt_template_repository_uses_injected_pool() -> None:
    """Prompt 模板仓储只能消费注入的业务库连接池。"""

    repository = PromptTemplateRepository(
        pool=_FakePool(
            {
                "service_code": "transcript.extract.task1",
                "system_prompt": "system",
                "user_prompt": "user",
                "enabled": 1,
                "remark": "demo",
            }
        )  # type: ignore[arg-type]
    )

    record = await repository.get_by_service_code("transcript.extract.task1")

    assert record is not None
    assert record.service_code == "transcript.extract.task1"


@pytest.mark.asyncio
async def test_prompt_template_repository_requires_injected_pool() -> None:
    """未注入连接池时应立即报错，避免运行时偷偷建池。"""

    repository = PromptTemplateRepository()

    with pytest.raises(PromptTemplateRepositoryError, match="业务库连接池未注入"):
        await repository.get_by_service_code("transcript.extract.task1")
