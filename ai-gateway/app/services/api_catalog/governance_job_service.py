"""API 数据治理离线任务服务。

功能：
    这个服务专门承接“业务系统回调触发增量治理”的离线任务，不进入 `/api-query`
    在线查询链路。这样可以把治理任务的长耗时行为（字段归一、索引更新、图同步）和
    用户在线查询流量彻底隔离，避免两类负载互相抢占 API worker。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.models.schemas.catalog_governance import (
    ApiCatalogColdStartGovernanceRequest,
    ApiCatalogGovernanceJobResponse,
    ApiCatalogGovernanceJobStatus,
    ApiCatalogIncrementalGovernanceRequest,
    SemanticCurationMode,
    SemanticCurationPhase,
    SemanticCurationRunStatus,
)
from app.services.api_catalog.indexer import ApiCatalogIndexer
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_catalog.semantic_curation_run_repository import (
    SemanticCurationRunRepository,
    SemanticCurationRunRepositoryError,
)
from app.services.api_catalog.semantic_field_repository import SemanticFieldRepository
from app.services.api_catalog.semantic_governance_proposal_models import (
    SemanticGovernancePersistSummary,
    SemanticGovernanceProposalBatch,
)
from app.services.api_catalog.semantic_governance_proposal_repository import (
    SemanticGovernanceProposalRepository,
)
from app.services.api_catalog.semantic_governance_proposal_service import SemanticGovernanceProposalService

RegistrySourceFactory = Callable[[], ApiCatalogRegistrySource]
IndexerFactory = Callable[[], ApiCatalogIndexer]


class ApiCatalogGovernanceJobService:
    """增量治理任务门面。

    功能：
        提供“触发任务 + 查询状态”的最小闭环。这里仍然使用进程内任务表，而不是直接
        引入分布式任务队列，是为了先把在线/离线边界切干净，降低当前阶段的改造风险。

    Args:
        registry_source_factory: 注册表访问器工厂，测试可注入 fake source。
        indexer_factory: 索引器工厂，测试可注入 fake indexer。
        clock: 可注入时钟，便于测试稳定断言时间字段。
    """

    def __init__(
        self,
        *,
        registry_source_factory: RegistrySourceFactory | None = None,
        indexer_factory: IndexerFactory | None = None,
        run_repository: SemanticCurationRunRepository | None = None,
        proposal_service: SemanticGovernanceProposalService | None = None,
        proposal_repository: SemanticGovernanceProposalRepository | None = None,
        semantic_field_repository: SemanticFieldRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._registry_source_factory = registry_source_factory or ApiCatalogRegistrySource
        self._indexer_factory = indexer_factory or ApiCatalogIndexer
        self._run_repository = run_repository or SemanticCurationRunRepository()
        self._proposal_service = proposal_service or SemanticGovernanceProposalService()
        self._proposal_repository = proposal_repository or SemanticGovernanceProposalRepository()
        self._semantic_field_repository = semantic_field_repository or SemanticFieldRepository()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._jobs: dict[str, ApiCatalogGovernanceJobResponse] = {}
        self._watch_tasks: dict[str, asyncio.Task[None]] = {}
        self._running_job_id: str | None = None
        self._lock = asyncio.Lock()

    async def start_incremental_governance(
        self,
        request: ApiCatalogIncrementalGovernanceRequest,
        *,
        requested_by: str | None,
    ) -> ApiCatalogGovernanceJobResponse:
        """触发一次增量治理任务。

        功能：
            业务系统的回调接口只需要拿到“任务句柄”，不能在 HTTP 请求内等待全部治理完成。
            因此这里先创建任务快照，再把真实治理流程放到后台 task 执行。

        Returns:
            任务当前快照。若已有运行中的任务，返回该任务并标记 `reused_existing_job=true`。
        """

        normalized_api_ids = await self._resolve_incremental_api_ids(request)
        if not normalized_api_ids:
            now = self._clock()
            return ApiCatalogGovernanceJobResponse(
                job_id=uuid4().hex,
                run_id=None,
                status=ApiCatalogGovernanceJobStatus.SUCCESS,
                message="未探测到增量 API 变更，本次治理已跳过。",
                reused_existing_job=False,
                requested_at=now,
                started_at=now,
                finished_at=now,
                reason=request.reason,
                requested_by=requested_by,
                total_apis=0,
                indexed=0,
                skipped=0,
                failed_api_ids=[],
                error_summary="",
            )
        return await self._start_governance_job(
            api_ids=normalized_api_ids,
            reason=request.reason,
            requested_by=requested_by,
            phase=SemanticCurationPhase.PLAN_B,
            mode=SemanticCurationMode.INCREMENTAL,
            message="增量治理任务已启动。",
        )

    async def start_cold_start_governance(
        self,
        request: ApiCatalogColdStartGovernanceRequest,
        *,
        requested_by: str | None,
    ) -> ApiCatalogGovernanceJobResponse:
        """触发一次冷启动治理任务（Plan C）。

        功能：
            冷启动阶段要覆盖全量字段语料；接口仍返回异步任务句柄，避免 HTTP 超时。
        """

        registry_source = self._registry_source_factory()
        try:
            entries = await registry_source.load_entries()
        finally:
            await registry_source.close()
        target_api_filter = set(request.api_ids)
        domain_filter = set(request.domains)
        target_api_ids = _normalize_api_ids(
            [
                entry.id
                for entry in entries
                if _cold_start_entry_matches(entry, api_filter=target_api_filter, domain_filter=domain_filter)
            ]
        )
        if not target_api_ids:
            now = self._clock()
            return ApiCatalogGovernanceJobResponse(
                job_id=uuid4().hex,
                run_id=None,
                status=ApiCatalogGovernanceJobStatus.SUCCESS,
                message="未命中冷启动治理范围，本次任务已跳过。",
                reused_existing_job=False,
                requested_at=now,
                started_at=now,
                finished_at=now,
                reason=request.reason,
                requested_by=requested_by,
                total_apis=0,
                indexed=0,
                skipped=0,
                failed_api_ids=[],
                error_summary="",
            )
        mode = SemanticCurationMode.DRY_RUN if request.dry_run else SemanticCurationMode.FULL
        return await self._start_governance_job(
            api_ids=target_api_ids,
            reason=request.reason,
            requested_by=requested_by,
            phase=SemanticCurationPhase.PLAN_C,
            mode=mode,
            message="冷启动治理任务已启动。",
        )

    async def _start_governance_job(
        self,
        *,
        api_ids: list[str],
        reason: str | None,
        requested_by: str | None,
        phase: SemanticCurationPhase,
        mode: SemanticCurationMode,
        message: str,
    ) -> ApiCatalogGovernanceJobResponse:
        """创建治理任务并启动后台执行。"""

        async with self._lock:
            running_job = self._get_running_job_locked()
            if running_job is not None:
                return running_job.model_copy(
                    update={
                        "reused_existing_job": True,
                        "message": "已有离线治理任务正在运行，已复用当前任务。",
                    }
                )

            now = self._clock()
            job_id = uuid4().hex
            governance_run_id = _build_curation_run_id(self._clock)
            job_snapshot = ApiCatalogGovernanceJobResponse(
                job_id=job_id,
                run_id=governance_run_id,
                status=ApiCatalogGovernanceJobStatus.RUNNING,
                message=message,
                reused_existing_job=False,
                requested_at=now,
                started_at=now,
                finished_at=None,
                reason=reason,
                requested_by=requested_by,
                total_apis=len(api_ids),
                indexed=0,
                skipped=0,
                failed_api_ids=[],
                error_summary="",
            )
            self._jobs[job_id] = job_snapshot
            self._running_job_id = job_id
            self._watch_tasks[job_id] = asyncio.create_task(
                self._run_governance_job(
                    job_id=job_id,
                    run_id=governance_run_id,
                    api_ids=api_ids,
                    reason=reason,
                    requested_by=requested_by,
                    phase=phase,
                    mode=mode,
                )
            )
            return job_snapshot.model_copy(deep=True)

    def get_job(self, job_id: str) -> ApiCatalogGovernanceJobResponse | None:
        """读取治理任务快照。"""

        job_snapshot = self._jobs.get(job_id)
        if job_snapshot is None:
            return None
        return job_snapshot.model_copy(deep=True)

    async def wait_for_job(self, job_id: str) -> ApiCatalogGovernanceJobResponse | None:
        """等待指定任务结束（主要用于测试）。"""

        watch_task = self._watch_tasks.get(job_id)
        if watch_task is not None:
            await watch_task
        return self.get_job(job_id)

    async def close(self) -> None:
        """等待当前仍在运行的后台任务收尾。"""

        if not self._watch_tasks:
            await self._run_repository.close()
            await self._proposal_repository.close()
            await self._semantic_field_repository.close()
            await self._proposal_service.close()
            return
        await asyncio.gather(*self._watch_tasks.values(), return_exceptions=True)
        await self._run_repository.close()
        await self._proposal_repository.close()
        await self._semantic_field_repository.close()
        await self._proposal_service.close()

    def _get_running_job_locked(self) -> ApiCatalogGovernanceJobResponse | None:
        """读取当前运行中的任务快照。"""

        if self._running_job_id is None:
            return None
        running_job = self._jobs.get(self._running_job_id)
        if running_job is None or running_job.status != ApiCatalogGovernanceJobStatus.RUNNING:
            self._running_job_id = None
            return None
        return running_job

    async def _run_governance_job(
        self,
        *,
        job_id: str,
        run_id: str,
        api_ids: list[str],
        reason: str | None,
        requested_by: str | None,
        phase: SemanticCurationPhase,
        mode: SemanticCurationMode,
    ) -> None:
        """执行治理批次并回填任务状态。

        功能：
            任务内部按 API ID 顺序逐条处理，确保失败 API 可精确归因并支持后续人工复核。
            这里不做“失败即停”，是因为增量治理目标是尽可能多地产生可用结果，失败条目
            应进入失败列表，而不是拖垮整批任务。
        """

        indexed = 0
        skipped = 0
        failed_api_ids: list[str] = []
        errors: list[str] = []
        run_tracking_error: str | None = None
        proposal_summary = SemanticGovernancePersistSummary()
        proposal_batch = SemanticGovernanceProposalBatch()
        proposal_error: str | None = None

        try:
            await self._run_repository.create_run(
                run_id=run_id,
                phase=phase,
                mode=mode,
                status=SemanticCurationRunStatus.INIT,
                previous_run_id=None,
                triggered_by=requested_by,
                trigger_reason=reason,
            )
            await self._run_repository.update_run(
                run_id,
                status=SemanticCurationRunStatus.EXTRACTED,
            )
        except Exception as exc:  # pragma: no cover - 依赖真实 DB DDL
            # run 主账本异常不阻断增量治理主流程；先保证治理任务可执行，再把控制面故障回填到摘要。
            run_tracking_error = f"run tracking unavailable ({exc})"

        registry_source = self._registry_source_factory()
        indexer = self._indexer_factory()
        governance_snapshot = None

        try:
            try:
                governance_snapshot = await self._semantic_field_repository.load_active_rules()
            except Exception as exc:
                proposal_error = f"governance snapshot unavailable ({exc})"

            for api_id in api_ids:
                try:
                    entry = await registry_source.get_entry_by_id(api_id)
                except Exception as exc:
                    failed_api_ids.append(api_id)
                    errors.append(f"{api_id}: registry lookup failed ({exc})")
                    continue

                if entry is None:
                    skipped += 1
                    continue

                try:
                    await indexer.index_entry(entry)
                    indexed += 1
                except Exception as exc:
                    failed_api_ids.append(api_id)
                    errors.append(f"{api_id}: index failed ({exc})")
                    continue

                if governance_snapshot is not None:
                    try:
                        batch = await self._proposal_service.build_batch(
                            entries=[entry],
                            phase=phase,
                            governance_snapshot=governance_snapshot,
                        )
                        # 逐条写库可把冲突定位到具体 API，便于后续人工审核追责。
                        persisted = await self._proposal_repository.persist_batch(run_id, batch)
                        proposal_summary.dict_written += persisted.dict_written
                        proposal_summary.alias_written += persisted.alias_written
                        proposal_summary.value_map_written += persisted.value_map_written
                        proposal_summary.rejected_by_human_lock += persisted.rejected_by_human_lock
                        proposal_summary.conflict_review_marked += persisted.conflict_review_marked
                        proposal_batch.total_fields += batch.total_fields
                        proposal_batch.high_confidence_fields += batch.high_confidence_fields
                        proposal_batch.pending_fields += batch.pending_fields
                        proposal_batch.rejected_fields += batch.rejected_fields
                    except Exception as exc:
                        # 提案链路失败不反向打断索引流程，优先确保接口召回面可持续更新。
                        proposal_error = f"proposal pipeline failed ({exc})"
        finally:
            await registry_source.close()

        status, message = _summarize_job_status(indexed=indexed, skipped=skipped, failed_count=len(failed_api_ids))
        error_summary = " | ".join(errors[:5])
        if len(errors) > 5:
            error_summary = f"{error_summary} | ... {len(errors) - 5} more"
        if run_tracking_error:
            error_summary = f"{error_summary} | {run_tracking_error}" if error_summary else run_tracking_error
        if proposal_error:
            error_summary = f"{error_summary} | {proposal_error}" if error_summary else proposal_error

        high_coverage_rate, low_pending_rate, manual_reject_rate = _build_quality_metrics(
            batch=proposal_batch,
            proposal_summary=proposal_summary,
        )
        run_status = _to_run_status(
            phase=phase,
            job_status=status,
            indexed=indexed,
            skipped=skipped,
            failed_count=len(failed_api_ids),
            pending_fields=proposal_batch.pending_fields,
        )
        try:
            await self._run_repository.update_run(
                run_id,
                status=run_status,
                high_coverage_rate=high_coverage_rate,
                low_pending_rate=low_pending_rate,
                manual_reject_rate=manual_reject_rate,
                indexed=indexed,
                skipped=skipped,
                failed_count=len(failed_api_ids),
                finished_at=self._clock(),
                error_message=error_summary or None,
            )
        except SemanticCurationRunRepositoryError as exc:  # pragma: no cover - 依赖真实 DB DDL
            append_text = f"run update failed ({exc})"
            error_summary = f"{error_summary} | {append_text}" if error_summary else append_text

        async with self._lock:
            current_snapshot = self._jobs.get(job_id)
            if current_snapshot is None:
                self._watch_tasks.pop(job_id, None)
                if self._running_job_id == job_id:
                    self._running_job_id = None
                return

            self._jobs[job_id] = current_snapshot.model_copy(
                update={
                    "status": status,
                    "message": message,
                    "finished_at": self._clock(),
                    "run_id": run_id,
                    "reason": reason,
                    "requested_by": requested_by,
                    "total_apis": len(api_ids),
                    "indexed": indexed,
                    "skipped": skipped,
                    "failed_api_ids": failed_api_ids,
                    "error_summary": _merge_job_summary(
                        error_summary=error_summary,
                        proposal_summary=proposal_summary,
                        proposal_batch=proposal_batch,
                    ),
                    "reused_existing_job": False,
                }
            )
            self._watch_tasks.pop(job_id, None)
            if self._running_job_id == job_id:
                self._running_job_id = None

    async def _resolve_incremental_api_ids(self, request: ApiCatalogIncrementalGovernanceRequest) -> list[str]:
        """解析增量治理目标 API 集。

        功能：
            稳态支持两种入口：业务系统显式传 API ID，或由网关按 `updated_at` 自动探测。
            这样既兼容“上游主动通知”，也支持定时补偿任务。
        """

        explicit_api_ids = _normalize_api_ids(request.api_ids)
        if explicit_api_ids:
            return explicit_api_ids
        if request.detect_mode != "updated_at":
            return []
        updated_since = request.updated_since
        if updated_since is None:
            latest_promoted = await self._run_repository.get_latest_promoted_run()
            updated_since = latest_promoted.started_at if latest_promoted is not None else None

        registry_source = self._registry_source_factory()
        try:
            return await registry_source.load_changed_api_ids(
                updated_since=updated_since,
                limit=request.max_scan,
            )
        finally:
            await registry_source.close()


def _normalize_api_ids(api_ids: list[str]) -> list[str]:
    """去重并过滤空值，保持原有顺序。

    功能：
        业务系统回调可能携带重复 ID。预处理可以避免同一接口在一个批次内被重复治理，
        减少不必要的 Milvus/Neo4j 写放大。
    """

    seen: set[str] = set()
    normalized: list[str] = []
    for raw_id in api_ids:
        api_id = raw_id.strip()
        if not api_id or api_id in seen:
            continue
        seen.add(api_id)
        normalized.append(api_id)
    return normalized


def _summarize_job_status(
    *,
    indexed: int,
    skipped: int,
    failed_count: int,
) -> tuple[ApiCatalogGovernanceJobStatus, str]:
    """根据处理结果生成任务状态与消息。"""

    if failed_count == 0:
        return ApiCatalogGovernanceJobStatus.SUCCESS, "增量治理任务执行完成。"
    if indexed == 0 and skipped == 0:
        return ApiCatalogGovernanceJobStatus.FAILED, "增量治理任务执行失败，请检查失败摘要。"
    return ApiCatalogGovernanceJobStatus.PARTIAL_SUCCESS, "增量治理任务部分成功，请复核失败条目。"


def _to_run_status(
    *,
    phase: SemanticCurationPhase,
    job_status: ApiCatalogGovernanceJobStatus,
    indexed: int,
    skipped: int,
    failed_count: int,
    pending_fields: int,
) -> SemanticCurationRunStatus:
    """把任务状态映射到 run 生命周期状态。"""

    if job_status == ApiCatalogGovernanceJobStatus.FAILED and indexed == 0 and skipped == 0:
        return SemanticCurationRunStatus.FAILED
    if failed_count > 0 or pending_fields > 0:
        # 发生部分失败时保留为待审态，避免自动发布带缺口的数据集。
        return SemanticCurationRunStatus.REVIEW_PENDING
    if phase == SemanticCurationPhase.PLAN_C:
        return SemanticCurationRunStatus.PROPOSED
    return SemanticCurationRunStatus.REVIEW_PENDING


def _build_quality_metrics(
    *,
    batch: SemanticGovernanceProposalBatch,
    proposal_summary: SemanticGovernancePersistSummary,
) -> tuple[float | None, float | None, float | None]:
    """构建 run 指标。"""

    if batch.total_fields <= 0:
        return None, None, None
    total_fields = float(batch.total_fields)
    high_coverage_rate = round(batch.high_confidence_fields / total_fields, 4)
    low_pending_rate = round(batch.pending_fields / total_fields, 4)
    manual_reject_rate = round(proposal_summary.rejected_by_human_lock / total_fields, 4)
    return high_coverage_rate, low_pending_rate, manual_reject_rate


def _merge_job_summary(
    *,
    error_summary: str,
    proposal_summary: SemanticGovernancePersistSummary,
    proposal_batch: SemanticGovernanceProposalBatch,
) -> str:
    """拼接任务摘要。"""

    proposal_text = (
        f"proposal=dict:{proposal_summary.dict_written},"
        f"alias:{proposal_summary.alias_written},"
        f"value:{proposal_summary.value_map_written},"
        f"pending:{proposal_batch.pending_fields},"
        f"reject:{proposal_summary.rejected_by_human_lock}"
    )
    return f"{error_summary} | {proposal_text}" if error_summary else proposal_text


def _build_curation_run_id(clock: Callable[[], datetime]) -> str:
    """生成治理 run_id。

    功能：
        run_id 采用 `R_日期时间_短随机` 结构，兼顾可读性和并发唯一性，便于运维快速定位批次。
    """

    now = clock().astimezone(UTC)
    return f"R_{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"


def _cold_start_entry_matches(entry, *, api_filter: set[str], domain_filter: set[str]) -> bool:
    """判断冷启动任务是否命中指定接口。"""

    if api_filter and entry.id not in api_filter:
        return False
    if domain_filter and (entry.domain or "") not in domain_filter:
        return False
    return True
