"""API Catalog 数据治理控制面路由。

功能：
    该路由只承接离线治理任务（增量治理触发、任务状态查询），不进入 `/api-query`
    在线请求链路，避免在线查询流量与治理任务相互影响。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.models.schemas import (
    ApiCatalogColdStartGovernanceRequest,
    ApiCatalogGovernancePromoteRequest,
    ApiCatalogGovernanceRollbackRequest,
    ApiCatalogGovernanceJobResponse,
    ApiCatalogGovernanceRunResponse,
    ApiCatalogIncrementalGovernanceRequest,
)
from app.services.api_catalog.governance_job_service import ApiCatalogGovernanceJobService
from app.services.api_catalog.semantic_curation_run_repository import (
    SemanticCurationRunRepository,
    SemanticCurationRunRepositoryError,
)
from app.services.api_catalog.semantic_governance_publication_service import (
    SemanticGovernancePublicationError,
    SemanticGovernancePublicationService,
)

router = APIRouter(prefix="/catalog-governance", tags=["Catalog Governance"])

_governance_job_service: ApiCatalogGovernanceJobService | None = None
_curation_run_repository: SemanticCurationRunRepository | None = None
_publication_service: SemanticGovernancePublicationService | None = None


def _get_governance_job_service() -> ApiCatalogGovernanceJobService:
    """获取增量治理任务服务单例。

    功能：
        控制面的触发接口和状态查询接口必须共享同一份任务表，否则 POST 刚创建的任务
        在 GET 查询阶段会丢失。
    """

    global _governance_job_service
    if _governance_job_service is None:
        _governance_job_service = ApiCatalogGovernanceJobService(run_repository=_get_curation_run_repository())
    return _governance_job_service


def _get_curation_run_repository() -> SemanticCurationRunRepository:
    """获取治理 run 仓储单例。"""

    global _curation_run_repository
    if _curation_run_repository is None:
        _curation_run_repository = SemanticCurationRunRepository()
    return _curation_run_repository


def _get_publication_service() -> SemanticGovernancePublicationService:
    """获取治理发布服务单例。"""

    global _publication_service
    if _publication_service is None:
        _publication_service = SemanticGovernancePublicationService(run_repository=_get_curation_run_repository())
    return _publication_service


@router.post(
    "/incremental",
    response_model=ApiCatalogGovernanceJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="异步触发 API 数据治理增量任务（离线）",
)
async def trigger_incremental_governance(
    request_body: ApiCatalogIncrementalGovernanceRequest,
    request: Request,
) -> ApiCatalogGovernanceJobResponse:
    """触发增量治理任务并返回任务句柄。

    功能：
        业务系统在接口元数据变更后，调用本接口通知网关做增量治理。路由只负责受理请求、
        记录触发人并返回 `job_id`，实际治理工作在后台任务中执行。
    """

    requested_by = (request.headers.get("X-User-Id") or "").strip() or None
    return await _get_governance_job_service().start_incremental_governance(
        request_body,
        requested_by=requested_by,
    )


@router.post(
    "/cold-start",
    response_model=ApiCatalogGovernanceJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="异步触发 API 数据治理冷启动任务（离线）",
)
async def trigger_cold_start_governance(
    request_body: ApiCatalogColdStartGovernanceRequest,
    request: Request,
) -> ApiCatalogGovernanceJobResponse:
    """触发冷启动治理任务并返回任务句柄。"""

    requested_by = (request.headers.get("X-User-Id") or "").strip() or None
    return await _get_governance_job_service().start_cold_start_governance(
        request_body,
        requested_by=requested_by,
    )


@router.get(
    "/incremental/{job_id}",
    response_model=ApiCatalogGovernanceJobResponse,
    summary="查询 API 数据治理增量任务状态（离线）",
)
async def get_incremental_governance_job(job_id: str) -> ApiCatalogGovernanceJobResponse:
    """读取指定增量治理任务的快照。"""

    snapshot = _get_governance_job_service().get_job(job_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到 API 数据治理任务: {job_id}",
        )
    return snapshot


@router.get(
    "/runs/{run_id}",
    response_model=ApiCatalogGovernanceRunResponse,
    summary="查询字段治理 run 状态（离线）",
)
async def get_curation_run(run_id: str) -> ApiCatalogGovernanceRunResponse:
    """读取指定治理 run 快照。"""

    try:
        snapshot = await _get_curation_run_repository().get_run(run_id)
    except SemanticCurationRunRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到治理 run: {run_id}",
        )
    return snapshot


@router.post(
    "/runs/{run_id}/promote",
    response_model=ApiCatalogGovernanceRunResponse,
    summary="发布治理 run（原子切流）",
)
async def promote_curation_run(run_id: str, request_body: ApiCatalogGovernancePromoteRequest) -> ApiCatalogGovernanceRunResponse:
    """把指定 run 发布为在线版本。"""

    try:
        snapshot = await _get_publication_service().promote_run(run_id, reviewer=request_body.reviewer)
    except SemanticGovernancePublicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到治理 run: {run_id}",
        )
    return snapshot


@router.post(
    "/runs/rollback",
    response_model=ApiCatalogGovernanceRunResponse,
    summary="回滚到历史治理 run（原子切流）",
)
async def rollback_curation_run(request_body: ApiCatalogGovernanceRollbackRequest) -> ApiCatalogGovernanceRunResponse:
    """把在线规则回滚到目标 run。"""

    try:
        snapshot = await _get_publication_service().rollback_to_run(
            request_body.target_run_id,
            reason=request_body.reason,
        )
    except SemanticGovernancePublicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到治理 run: {request_body.target_run_id}",
        )
    return snapshot
