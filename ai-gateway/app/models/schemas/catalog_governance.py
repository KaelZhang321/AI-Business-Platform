from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ApiCatalogIndexJobStatus(str, Enum):
    """API Catalog 重建任务状态。

    功能：
        管理端重建入口已经从“同步执行重活”改成“异步触发后台子进程”，因此必须把任务状态
        提炼成正式枚举，避免前端或运维脚本继续通过字符串猜测当前任务是否还在运行。
    """

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ApiCatalogIndexJobResponse(BaseModel):
    """API Catalog 重建任务响应。

    功能：
        统一承载“任务是否刚创建、是否复用了正在运行的任务、当前执行到哪一步、最后输出了什么”
        这些管理端事实，让 HTTP 层不再暴露子进程实现细节。

    返回值约束：
        - `job_id` 必须稳定存在，便于后续轮询状态
        - `status` 只表达任务生命周期，不表达索引业务语义
        - `stdout_tail/stderr_tail` 只保留尾部片段，避免把完整离线日志塞回 API 响应

    Edge Cases:
        - 同一时刻只允许一个重建任务运行；复用已有任务时 `reused_existing_job=true`
        - 子进程还未结束时 `finished_at`、`exit_code` 允许为空
    """

    job_id: str = Field(..., min_length=1, description="重建任务唯一标识")
    status: ApiCatalogIndexJobStatus = Field(..., description="当前任务状态")
    message: str = Field(..., description="面向管理端的任务说明")
    reused_existing_job: bool = Field(False, description="是否复用了当前正在运行的任务")
    requested_at: datetime = Field(..., description="任务被路由层受理的时间")
    started_at: datetime | None = Field(None, description="子进程真正启动的时间")
    finished_at: datetime | None = Field(None, description="任务结束时间")
    pid: int | None = Field(None, description="后台索引子进程 PID")
    exit_code: int | None = Field(None, description="子进程退出码")
    command: list[str] = Field(default_factory=list, description="实际执行的命令")
    stdout_tail: str = Field("", description="标准输出尾部日志")
    stderr_tail: str = Field("", description="标准错误尾部日志")


class ApiCatalogGovernanceJobStatus(str, Enum):
    """API 数据治理任务状态。

    功能：
        面向“业务系统主动回调触发增量治理”的异步任务状态枚举。和索引重建任务拆分，
        是为了避免后续把“目录重建”和“治理增量收敛”混成同一条运维语义。
    """

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


class SemanticCurationPhase(str, Enum):
    """字段治理阶段。

    功能：
        统一表达当前 run 处于冷启动（LLM 主导）还是稳态（规则主导）的治理阶段，便于后续
        门槛判定、审计报表和回放工具共享同一口径。
    """

    PLAN_C = "C"
    PLAN_B = "B"


class SemanticCurationMode(str, Enum):
    """字段治理执行模式。"""

    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"
    DRY_RUN = "DRY_RUN"


class SemanticCurationRunStatus(str, Enum):
    """字段治理 run 生命周期状态。

    功能：
        这组状态用于表达“本批数据是否仅完成提取、是否已进入待审、是否已完成发布/回滚”，
        防止调用方把“任务触发成功”误判成“规则已上线”。
    """

    INIT = "INIT"
    EXTRACTED = "EXTRACTED"
    PROPOSED = "PROPOSED"
    REVIEW_PENDING = "REVIEW_PENDING"
    PROMOTED = "PROMOTED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ApiCatalogIncrementalGovernanceRequest(BaseModel):
    """增量治理触发请求。

    功能：
        业务系统接口元数据发生变更后，通过该请求体显式告知网关“哪几条 API 需要重新治理”。
        这比全量重建更可控，也更符合稳态阶段的增量探测策略。

    返回值约束：
        - `api_ids` 至少包含 1 个接口 ID
        - 同一批次允许重复传入，服务层会在任务内做去重
    """

    api_ids: list[str] = Field(default_factory=list, description="本次需要增量治理的接口 ID 列表")
    detect_mode: Literal["explicit", "updated_at"] = Field(
        "explicit",
        description="增量探测模式：explicit=显式传 ID，updated_at=按接口更新时间自动探测",
    )
    updated_since: datetime | None = Field(
        None,
        description="updated_at 探测窗口起点；为空时默认从最近已发布 run 开始",
    )
    max_scan: int = Field(500, ge=1, le=5000, description="updated_at 模式最大扫描 API 数")
    reason: str | None = Field(None, description="触发原因，便于审计与复盘")


class ApiCatalogColdStartGovernanceRequest(BaseModel):
    """冷启动治理触发请求（Plan C）。

    功能：
        用于全量或范围化初始化语义字典提案，主要给首次上线或大规模重构后的重建场景使用。
    """

    api_ids: list[str] = Field(default_factory=list, description="可选，指定只对这些 API 执行冷启动治理")
    domains: list[str] = Field(default_factory=list, description="可选，限定治理的业务域")
    dry_run: bool = Field(False, description="是否仅生成提案不执行后续发布动作")
    reason: str | None = Field(None, description="触发原因")


class ApiCatalogGovernanceJobResponse(BaseModel):
    """增量治理任务响应。

    功能：
        给业务系统和运维平台返回统一任务句柄与处理摘要，避免调用方误把“触发成功”
        当成“治理已完成”。
    """

    job_id: str = Field(..., min_length=1, description="治理任务唯一标识")
    run_id: str | None = Field(None, description="本次任务关联的字段治理 run_id")
    status: ApiCatalogGovernanceJobStatus = Field(..., description="当前任务状态")
    message: str = Field(..., description="任务状态说明")
    reused_existing_job: bool = Field(False, description="是否复用了当前运行中的任务")
    requested_at: datetime = Field(..., description="任务受理时间")
    started_at: datetime | None = Field(None, description="任务开始执行时间")
    finished_at: datetime | None = Field(None, description="任务结束时间")
    reason: str | None = Field(None, description="触发原因")
    requested_by: str | None = Field(None, description="触发人或触发系统标识")
    total_apis: int = Field(0, ge=0, description="本次任务输入 API 数")
    indexed: int = Field(0, ge=0, description="治理成功并完成索引/图同步的 API 数")
    skipped: int = Field(0, ge=0, description="跳过处理的 API 数（如不存在）")
    failed_api_ids: list[str] = Field(default_factory=list, description="治理失败的 API ID 列表")
    error_summary: str = Field("", description="失败摘要")


class ApiCatalogGovernanceRunResponse(BaseModel):
    """字段治理 run 快照。

    功能：
        面向控制面返回单次治理 run 的生命周期事实，供运维平台判断“是否可发布”“是否可回滚”。
    """

    run_id: str = Field(..., min_length=1, description="治理 run 唯一标识")
    phase: SemanticCurationPhase = Field(..., description="治理阶段：C 冷启动 / B 稳态")
    mode: SemanticCurationMode = Field(..., description="执行模式：FULL / INCREMENTAL / DRY_RUN")
    status: SemanticCurationRunStatus = Field(..., description="run 生命周期状态")
    previous_run_id: str | None = Field(None, description="上一个已发布 run_id，用于回滚锚点")
    triggered_by: str | None = Field(None, description="触发人或触发系统")
    trigger_reason: str | None = Field(None, description="触发原因")
    high_coverage_rate: float | None = Field(None, ge=0.0, le=1.0, description="高置信覆盖率")
    low_pending_rate: float | None = Field(None, ge=0.0, le=1.0, description="低置信待审率")
    manual_reject_rate: float | None = Field(None, ge=0.0, le=1.0, description="人工驳回率")
    indexed: int = Field(0, ge=0, description="本次成功处理的 API 数")
    skipped: int = Field(0, ge=0, description="本次跳过 API 数")
    failed_count: int = Field(0, ge=0, description="本次失败 API 数")
    started_at: datetime = Field(..., description="run 开始时间")
    finished_at: datetime | None = Field(None, description="run 结束时间")
    error_message: str | None = Field(None, description="失败摘要")


class ApiCatalogGovernancePromoteRequest(BaseModel):
    """发布请求。

    功能：
        控制面确认某个 run 可以切为在线版本时使用。发布动作会触发三表 current_flag 原子切流。
    """

    reviewer: str | None = Field(None, description="审核人")
    note: str | None = Field(None, description="审核备注")


class ApiCatalogGovernanceRollbackRequest(BaseModel):
    """回滚请求。

    功能：
        当新版本规则导致图谱或渲染异常时，控制面通过指定历史 `run_id` 一键回滚在线版本。
    """

    target_run_id: str = Field(..., min_length=1, description="需要恢复为在线版本的目标 run_id")
    reason: str | None = Field(None, description="回滚原因")
