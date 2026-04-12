from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.models.schemas import ApiCatalogIndexJobStatus
from app.services.api_catalog.index_job_service import ApiCatalogIndexJobService


class _FakeProcess:
    def __init__(self, *, pid: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.pid = pid
        self.returncode: int | None = None
        self._stdout = stdout
        self._stderr = stderr
        self._done = asyncio.Event()

    async def communicate(self) -> tuple[bytes, bytes]:
        await self._done.wait()
        return self._stdout, self._stderr

    def finish(self, *, returncode: int) -> None:
        self.returncode = returncode
        self._done.set()


@pytest.mark.asyncio
async def test_start_rebuild_reuses_running_job() -> None:
    """同一时刻只允许一个重建任务运行，避免并发重建互相污染图库和向量库。"""

    created_processes: list[_FakeProcess] = []

    async def fake_process_factory(command: list[str], working_directory) -> _FakeProcess:
        process = _FakeProcess(pid=4321)
        created_processes.append(process)
        return process

    service = ApiCatalogIndexJobService(
        process_factory=fake_process_factory,
        clock=lambda: datetime(2026, 4, 12, 9, 30, tzinfo=UTC),
    )

    first_snapshot = await service.start_rebuild()
    second_snapshot = await service.start_rebuild()

    assert len(created_processes) == 1
    assert first_snapshot.job_id == second_snapshot.job_id
    assert first_snapshot.status == ApiCatalogIndexJobStatus.RUNNING
    assert second_snapshot.reused_existing_job is True

    created_processes[0].finish(returncode=0)
    final_snapshot = await service.wait_for_job(first_snapshot.job_id)

    assert final_snapshot is not None
    assert final_snapshot.status == ApiCatalogIndexJobStatus.SUCCESS
    assert final_snapshot.exit_code == 0


@pytest.mark.asyncio
async def test_watch_process_marks_failed_job_and_preserves_output_tail() -> None:
    """失败任务必须保留尾部输出，避免管理端只知道失败却完全不知道原因。"""

    process = _FakeProcess(
        pid=5678,
        stdout=b"indexing started\nindexing failed\n",
        stderr=b"neo4j unavailable\n",
    )

    async def fake_process_factory(command: list[str], working_directory) -> _FakeProcess:
        return process

    service = ApiCatalogIndexJobService(process_factory=fake_process_factory)
    snapshot = await service.start_rebuild()

    process.finish(returncode=2)
    final_snapshot = await service.wait_for_job(snapshot.job_id)

    assert final_snapshot is not None
    assert final_snapshot.status == ApiCatalogIndexJobStatus.FAILED
    assert final_snapshot.exit_code == 2
    assert "indexing failed" in final_snapshot.stdout_tail
    assert "neo4j unavailable" in final_snapshot.stderr_tail
