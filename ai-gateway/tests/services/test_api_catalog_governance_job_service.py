from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.models.schemas import (
    ApiCatalogGovernanceRunResponse,
    ApiCatalogGovernanceJobStatus,
    ApiCatalogIncrementalGovernanceRequest,
    SemanticCurationMode,
    SemanticCurationPhase,
    SemanticCurationRunStatus,
)
from app.services.api_catalog.governance_job_service import ApiCatalogGovernanceJobService
from app.services.api_catalog.graph_models import SemanticGovernanceSnapshot
from app.services.api_catalog.schema import ApiCatalogEntry
from app.services.api_catalog.semantic_governance_proposal_models import (
    SemanticGovernancePersistSummary,
    SemanticGovernanceProposalBatch,
)


def _build_entry(api_id: str) -> ApiCatalogEntry:
    """构造最小可用目录条目，避免测试被无关字段噪声干扰。"""

    return ApiCatalogEntry(
        id=api_id,
        description=f"entry for {api_id}",
        path=f"/api/{api_id}",
    )


class _StubRegistrySource:
    def __init__(self, mapping: dict[str, ApiCatalogEntry | None]) -> None:
        self._mapping = mapping
        self.closed = False
        self.changed_api_ids: list[str] = []

    async def get_entry_by_id(self, api_id: str) -> ApiCatalogEntry | None:
        return self._mapping.get(api_id)

    async def close(self) -> None:
        self.closed = True

    async def load_changed_api_ids(self, *, updated_since, limit: int = 500) -> list[str]:
        return self.changed_api_ids[:limit]


class _StubIndexer:
    def __init__(self, *, fail_api_ids: set[str] | None = None, block_event: asyncio.Event | None = None) -> None:
        self._fail_api_ids = fail_api_ids or set()
        self._block_event = block_event
        self.indexed_api_ids: list[str] = []

    async def index_entry(self, entry: ApiCatalogEntry) -> bool:
        if self._block_event is not None:
            await self._block_event.wait()
        if entry.id in self._fail_api_ids:
            raise RuntimeError(f"failed: {entry.id}")
        self.indexed_api_ids.append(entry.id)
        return True


class _StubRunRepository:
    """模拟治理 run 控制面仓储。"""

    def __init__(self) -> None:
        self.snapshots: dict[str, ApiCatalogGovernanceRunResponse] = {}
        self.closed = False

    async def create_run(
        self,
        *,
        run_id: str,
        phase: SemanticCurationPhase,
        mode: SemanticCurationMode,
        status: SemanticCurationRunStatus,
        previous_run_id: str | None = None,
        triggered_by: str | None = None,
        trigger_reason: str | None = None,
    ) -> ApiCatalogGovernanceRunResponse:
        snapshot = ApiCatalogGovernanceRunResponse(
            run_id=run_id,
            phase=phase,
            mode=mode,
            status=status,
            previous_run_id=previous_run_id,
            triggered_by=triggered_by,
            trigger_reason=trigger_reason,
            started_at=datetime(2026, 4, 13, 10, 0, tzinfo=UTC),
            finished_at=None,
            error_message=None,
        )
        self.snapshots[run_id] = snapshot
        return snapshot

    async def update_run(self, run_id: str, **kwargs) -> ApiCatalogGovernanceRunResponse | None:
        snapshot = self.snapshots.get(run_id)
        if snapshot is None:
            return None
        self.snapshots[run_id] = snapshot.model_copy(update=kwargs)
        return self.snapshots[run_id]

    async def get_run(self, run_id: str) -> ApiCatalogGovernanceRunResponse | None:
        return self.snapshots.get(run_id)

    async def get_latest_promoted_run(self) -> ApiCatalogGovernanceRunResponse | None:
        return None

    async def close(self) -> None:
        self.closed = True


class _StubSemanticFieldRepository:
    async def load_active_rules(self) -> SemanticGovernanceSnapshot:
        return SemanticGovernanceSnapshot()

    async def close(self) -> None:
        return None


class _StubProposalService:
    async def build_batch(
        self,
        *,
        entries: list[ApiCatalogEntry],
        phase: SemanticCurationPhase,
        governance_snapshot: SemanticGovernanceSnapshot,
    ) -> SemanticGovernanceProposalBatch:
        return SemanticGovernanceProposalBatch(total_fields=len(entries), high_confidence_fields=len(entries))

    async def close(self) -> None:
        return None


class _StubProposalRepository:
    async def persist_batch(self, run_id: str, batch: SemanticGovernanceProposalBatch) -> SemanticGovernancePersistSummary:
        return SemanticGovernancePersistSummary(
            dict_written=batch.total_fields,
            alias_written=batch.total_fields,
            value_map_written=0,
        )

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_incremental_governance_reuses_running_job() -> None:
    """同一时刻只保留一个治理任务，避免并发批次互相覆盖状态。"""

    blocker = asyncio.Event()
    stub_registry = _StubRegistrySource({"api_1": _build_entry("api_1")})
    stub_indexer = _StubIndexer(block_event=blocker)
    stub_run_repo = _StubRunRepository()

    service = ApiCatalogGovernanceJobService(
        registry_source_factory=lambda: stub_registry,
        indexer_factory=lambda: stub_indexer,
        run_repository=stub_run_repo,
        proposal_service=_StubProposalService(),
        proposal_repository=_StubProposalRepository(),
        semantic_field_repository=_StubSemanticFieldRepository(),
        clock=lambda: datetime(2026, 4, 13, 10, 0, tzinfo=UTC),
    )
    request = ApiCatalogIncrementalGovernanceRequest(api_ids=["api_1"], reason="metadata changed")

    first = await service.start_incremental_governance(request, requested_by="tester")
    second = await service.start_incremental_governance(request, requested_by="tester")

    assert first.job_id == second.job_id
    assert first.status == ApiCatalogGovernanceJobStatus.RUNNING
    assert second.reused_existing_job is True

    blocker.set()
    finished = await service.wait_for_job(first.job_id)
    assert finished is not None
    assert finished.status == ApiCatalogGovernanceJobStatus.SUCCESS
    assert finished.indexed == 1
    assert finished.run_id is not None


@pytest.mark.asyncio
async def test_incremental_governance_reports_partial_success() -> None:
    """失败条目要保留，成功条目也要继续推进，避免整批回滚造成治理停滞。"""

    stub_registry = _StubRegistrySource(
        {
            "api_1": _build_entry("api_1"),
            "api_2": _build_entry("api_2"),
            "api_3": None,
        }
    )
    stub_indexer = _StubIndexer(fail_api_ids={"api_2"})
    stub_run_repo = _StubRunRepository()
    service = ApiCatalogGovernanceJobService(
        registry_source_factory=lambda: stub_registry,
        indexer_factory=lambda: stub_indexer,
        run_repository=stub_run_repo,
        proposal_service=_StubProposalService(),
        proposal_repository=_StubProposalRepository(),
        semantic_field_repository=_StubSemanticFieldRepository(),
    )

    snapshot = await service.start_incremental_governance(
        ApiCatalogIncrementalGovernanceRequest(api_ids=["api_1", "api_2", "api_3"], reason="delta sync"),
        requested_by="upstream-system",
    )
    finished = await service.wait_for_job(snapshot.job_id)

    assert finished is not None
    assert finished.status == ApiCatalogGovernanceJobStatus.PARTIAL_SUCCESS
    assert finished.total_apis == 3
    assert finished.indexed == 1
    assert finished.skipped == 1
    assert finished.failed_api_ids == ["api_2"]
    assert "api_2" in finished.error_summary
    assert stub_registry.closed is True


@pytest.mark.asyncio
async def test_incremental_governance_marks_failed_when_all_entries_fail() -> None:
    """如果所有有效条目都失败，任务状态必须明确为 FAILED，避免误判为部分成功。"""

    stub_registry = _StubRegistrySource(
        {
            "api_1": _build_entry("api_1"),
            "api_2": _build_entry("api_2"),
        }
    )
    stub_indexer = _StubIndexer(fail_api_ids={"api_1", "api_2"})
    stub_run_repo = _StubRunRepository()
    service = ApiCatalogGovernanceJobService(
        registry_source_factory=lambda: stub_registry,
        indexer_factory=lambda: stub_indexer,
        run_repository=stub_run_repo,
        proposal_service=_StubProposalService(),
        proposal_repository=_StubProposalRepository(),
        semantic_field_repository=_StubSemanticFieldRepository(),
    )

    snapshot = await service.start_incremental_governance(
        ApiCatalogIncrementalGovernanceRequest(api_ids=["api_1", "api_2"], reason="delta sync"),
        requested_by="upstream-system",
    )
    finished = await service.wait_for_job(snapshot.job_id)

    assert finished is not None
    assert finished.status == ApiCatalogGovernanceJobStatus.FAILED
    assert finished.indexed == 0
    assert finished.skipped == 0
    assert finished.failed_api_ids == ["api_1", "api_2"]


@pytest.mark.asyncio
async def test_incremental_governance_supports_updated_at_detection_mode() -> None:
    """当未显式传 api_ids 时，应支持按 updated_at 自动探测目标接口。"""

    stub_registry = _StubRegistrySource(
        {
            "api_3": _build_entry("api_3"),
        }
    )
    stub_registry.changed_api_ids = ["api_3"]
    stub_indexer = _StubIndexer()
    stub_run_repo = _StubRunRepository()
    service = ApiCatalogGovernanceJobService(
        registry_source_factory=lambda: stub_registry,
        indexer_factory=lambda: stub_indexer,
        run_repository=stub_run_repo,
        proposal_service=_StubProposalService(),
        proposal_repository=_StubProposalRepository(),
        semantic_field_repository=_StubSemanticFieldRepository(),
    )

    snapshot = await service.start_incremental_governance(
        ApiCatalogIncrementalGovernanceRequest(
            api_ids=[],
            detect_mode="updated_at",
            reason="updated_at polling",
        ),
        requested_by="poller",
    )
    finished = await service.wait_for_job(snapshot.job_id)

    assert finished is not None
    assert finished.status == ApiCatalogGovernanceJobStatus.SUCCESS
    assert finished.total_apis == 1
    assert finished.indexed == 1
