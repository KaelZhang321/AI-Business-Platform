from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_curation_run_repository,
    get_governance_job_service,
    get_publication_service,
)
from app.api.routes import catalog_governance as governance_routes
from app.models.schemas import (
    ApiCatalogColdStartGovernanceRequest,
    ApiCatalogGovernancePromoteRequest,
    ApiCatalogGovernanceRollbackRequest,
    ApiCatalogGovernanceJobResponse,
    ApiCatalogGovernanceRunResponse,
    ApiCatalogGovernanceJobStatus,
    ApiCatalogIncrementalGovernanceRequest,
    SemanticCurationMode,
    SemanticCurationPhase,
    SemanticCurationRunStatus,
)


class _StubGovernanceJobService:
    """模拟离线治理任务服务。"""

    def __init__(self) -> None:
        self.last_request: ApiCatalogIncrementalGovernanceRequest | None = None
        self.last_requested_by: str | None = None
        self.requested_job_id: str | None = None
        self.snapshot = ApiCatalogGovernanceJobResponse(
            job_id="job_governance_001",
            status=ApiCatalogGovernanceJobStatus.RUNNING,
            message="增量治理任务已启动。",
            reused_existing_job=False,
            requested_at=datetime(2026, 4, 13, 11, 0, tzinfo=UTC),
            started_at=datetime(2026, 4, 13, 11, 0, tzinfo=UTC),
            finished_at=None,
            reason="metadata changed",
            requested_by="u_1001",
            total_apis=2,
            indexed=0,
            skipped=0,
            failed_api_ids=[],
            error_summary="",
        )

    async def start_incremental_governance(
        self,
        request: ApiCatalogIncrementalGovernanceRequest,
        *,
        requested_by: str | None,
    ) -> ApiCatalogGovernanceJobResponse:
        self.last_request = request
        self.last_requested_by = requested_by
        return self.snapshot

    async def start_cold_start_governance(
        self,
        request: ApiCatalogColdStartGovernanceRequest,
        *,
        requested_by: str | None,
    ) -> ApiCatalogGovernanceJobResponse:
        self.last_requested_by = requested_by
        self.last_request = ApiCatalogIncrementalGovernanceRequest(
            api_ids=request.api_ids,
            reason=request.reason,
        )
        return self.snapshot.model_copy(update={"message": "冷启动治理任务已启动。"})

    def get_job(self, job_id: str) -> ApiCatalogGovernanceJobResponse | None:
        self.requested_job_id = job_id
        if job_id != self.snapshot.job_id:
            return None
        return self.snapshot


class _StubRunRepository:
    """模拟治理 run 仓储。"""

    def __init__(self) -> None:
        self.requested_run_id: str | None = None
        self.snapshot = ApiCatalogGovernanceRunResponse(
            run_id="R_20260413_100000_abc123",
            phase=SemanticCurationPhase.PLAN_B,
            mode=SemanticCurationMode.INCREMENTAL,
            status=SemanticCurationRunStatus.REVIEW_PENDING,
            previous_run_id=None,
            triggered_by="u_1001",
            trigger_reason="metadata changed",
            started_at=datetime(2026, 4, 13, 11, 0, tzinfo=UTC),
            finished_at=datetime(2026, 4, 13, 11, 1, tzinfo=UTC),
            error_message=None,
            indexed=2,
            skipped=0,
            failed_count=0,
        )

    async def get_run(self, run_id: str) -> ApiCatalogGovernanceRunResponse | None:
        self.requested_run_id = run_id
        if run_id != self.snapshot.run_id:
            return None
        return self.snapshot


class _StubPublicationService:
    """模拟治理发布服务。"""

    def __init__(self, run_snapshot: ApiCatalogGovernanceRunResponse) -> None:
        self.run_snapshot = run_snapshot
        self.last_promote_request: tuple[str, str | None] | None = None
        self.last_rollback_request: tuple[str, str | None] | None = None

    async def promote_run(self, run_id: str, *, reviewer: str | None = None) -> ApiCatalogGovernanceRunResponse | None:
        self.last_promote_request = (run_id, reviewer)
        if run_id != self.run_snapshot.run_id:
            return None
        return self.run_snapshot.model_copy(update={"status": SemanticCurationRunStatus.PROMOTED})

    async def rollback_to_run(self, target_run_id: str, *, reason: str | None = None) -> ApiCatalogGovernanceRunResponse | None:
        self.last_rollback_request = (target_run_id, reason)
        if target_run_id != self.run_snapshot.run_id:
            return None
        return self.run_snapshot.model_copy(update={"status": SemanticCurationRunStatus.PROMOTED})


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(governance_routes.router, prefix="/api/v1")
    return app


def test_trigger_incremental_governance_returns_accepted_job() -> None:
    """触发接口只返回任务句柄，不在 HTTP 请求里同步等待治理完成。"""

    stub_service = _StubGovernanceJobService()
    app = _create_test_app()
    app.dependency_overrides[get_governance_job_service] = lambda: stub_service
    client = TestClient(app)
    response = client.post(
        "/api/v1/catalog-governance/incremental",
        json={"api_ids": ["api_1", "api_2"], "reason": "metadata changed"},
        headers={"X-User-Id": "u_1001"},
    )

    assert response.status_code == 202
    assert stub_service.last_request is not None
    assert stub_service.last_request.api_ids == ["api_1", "api_2"]
    assert stub_service.last_requested_by == "u_1001"
    assert response.json()["job_id"] == "job_governance_001"
    assert response.json()["status"] == "RUNNING"
    app.dependency_overrides.clear()


def test_get_incremental_governance_job_returns_snapshot() -> None:
    """状态查询必须读取已有任务快照，而不是重新触发治理任务。"""

    stub_service = _StubGovernanceJobService()
    app = _create_test_app()
    app.dependency_overrides[get_governance_job_service] = lambda: stub_service
    client = TestClient(app)
    response = client.get("/api/v1/catalog-governance/incremental/job_governance_001")

    assert response.status_code == 200
    assert stub_service.requested_job_id == "job_governance_001"
    assert response.json()["message"] == "增量治理任务已启动。"
    app.dependency_overrides.clear()


def test_trigger_cold_start_governance_returns_accepted_job() -> None:
    """冷启动治理触发也必须异步返回任务句柄。"""

    stub_service = _StubGovernanceJobService()
    app = _create_test_app()
    app.dependency_overrides[get_governance_job_service] = lambda: stub_service
    client = TestClient(app)
    response = client.post(
        "/api/v1/catalog-governance/cold-start",
        json={"domains": ["crm"], "dry_run": True, "reason": "bootstrap"},
        headers={"X-User-Id": "u_2002"},
    )

    assert response.status_code == 202
    assert response.json()["message"] == "冷启动治理任务已启动。"
    app.dependency_overrides.clear()


def test_get_incremental_governance_job_returns_404_when_missing() -> None:
    """任务不存在时必须返回 404，避免调用方误判为任务仍在执行。"""

    stub_service = _StubGovernanceJobService()
    app = _create_test_app()
    app.dependency_overrides[get_governance_job_service] = lambda: stub_service
    client = TestClient(app)
    response = client.get("/api/v1/catalog-governance/incremental/not_found")

    assert response.status_code == 404
    assert "未找到 API 数据治理任务" in response.json()["detail"]
    app.dependency_overrides.clear()


def test_get_curation_run_returns_snapshot() -> None:
    """run 查询应返回控制面快照。"""

    stub_repo = _StubRunRepository()
    app = _create_test_app()
    app.dependency_overrides[get_curation_run_repository] = lambda: stub_repo
    client = TestClient(app)
    response = client.get(f"/api/v1/catalog-governance/runs/{stub_repo.snapshot.run_id}")

    assert response.status_code == 200
    assert stub_repo.requested_run_id == stub_repo.snapshot.run_id
    assert response.json()["status"] == "REVIEW_PENDING"
    app.dependency_overrides.clear()


def test_promote_curation_run_calls_publication_service() -> None:
    """发布接口应转发到发布服务执行原子切流。"""

    stub_repo = _StubRunRepository()
    stub_publication = _StubPublicationService(stub_repo.snapshot)
    app = _create_test_app()
    app.dependency_overrides[get_publication_service] = lambda: stub_publication
    client = TestClient(app)
    response = client.post(
        f"/api/v1/catalog-governance/runs/{stub_repo.snapshot.run_id}/promote",
        json=ApiCatalogGovernancePromoteRequest(reviewer="architect", note="ok").model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert stub_publication.last_promote_request == (stub_repo.snapshot.run_id, "architect")
    assert response.json()["status"] == "PROMOTED"
    app.dependency_overrides.clear()


def test_rollback_curation_run_calls_publication_service() -> None:
    """回滚接口应调用发布服务恢复目标 run。"""

    stub_repo = _StubRunRepository()
    stub_publication = _StubPublicationService(stub_repo.snapshot)
    app = _create_test_app()
    app.dependency_overrides[get_publication_service] = lambda: stub_publication
    client = TestClient(app)
    response = client.post(
        "/api/v1/catalog-governance/runs/rollback",
        json=ApiCatalogGovernanceRollbackRequest(
            target_run_id=stub_repo.snapshot.run_id,
            reason="verify failed",
        ).model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert stub_publication.last_rollback_request == (stub_repo.snapshot.run_id, "verify failed")
    assert response.json()["status"] == "PROMOTED"
    app.dependency_overrides.clear()
