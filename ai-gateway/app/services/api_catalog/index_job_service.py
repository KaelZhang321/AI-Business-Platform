"""API Catalog 重建任务服务。

功能：
    把“管理端发起重建索引”与“真正执行离线索引”拆成两个边界：

    1. HTTP route 只负责触发任务和返回任务句柄
    2. 重型索引逻辑在独立 Python 子进程里运行

    这样做的核心目的不是为了炫技，而是避免 API worker 直接承载 embedding、Milvus 写入、
    Neo4j 同步这类长耗时任务，确保在线请求链路与离线重建链路的资源画像彻底分开。
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.models.schemas.catalog_governance import (
    ApiCatalogIndexJobResponse,
    ApiCatalogIndexJobStatus,
)

_MAX_OUTPUT_TAIL_CHARS = 4000

ProcessFactory = Callable[[list[str], Path], Awaitable[asyncio.subprocess.Process]]


class ApiCatalogIndexJobStartError(RuntimeError):
    """重建任务启动失败。"""


class ApiCatalogIndexJobService:
    """API Catalog 重建任务门面。

    功能：
        用一个进程内轻量任务表管理“当前是否已有重建任务在跑、如何异步查看结果”。
        这里故意不直接引入 Redis / RabbitMQ，是因为当前问题要解决的是边界错误，而不是
        先把一个本地管理入口升级成完整分布式任务系统。

    Args:
        process_factory: 子进程工厂。测试可注入 fake process，生产默认走 `create_subprocess_exec`。
        working_directory: 子进程工作目录。默认指向 `ai-gateway/` 根目录，保证 `python -m app...`
            在容器与本地开发环境中都能找到同一套包路径。
        python_executable: 运行离线索引入口的 Python 解释器。默认复用当前 API 进程解释器。
        module_name: 离线重建入口模块，默认指向 `app.services.api_catalog.indexer`。
        clock: 可注入时钟，主要用于测试中稳定断言时间字段。
    """

    def __init__(
        self,
        *,
        process_factory: ProcessFactory | None = None,
        working_directory: Path | None = None,
        python_executable: str | None = None,
        module_name: str = "app.services.api_catalog.indexer",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._process_factory = process_factory or _spawn_indexer_process
        self._working_directory = working_directory or Path(__file__).resolve().parents[3]
        self._python_executable = python_executable or sys.executable
        self._module_name = module_name
        self._clock = clock or (lambda: datetime.now(UTC))
        self._jobs: dict[str, ApiCatalogIndexJobResponse] = {}
        self._watch_tasks: dict[str, asyncio.Task[None]] = {}
        self._running_job_id: str | None = None
        self._lock = asyncio.Lock()

    async def start_rebuild(self) -> ApiCatalogIndexJobResponse:
        """触发一次 API Catalog 重建任务。

        功能：
            管理端真正需要的是“发起一次后台重建，并拿到可轮询的句柄”，而不是在 HTTP
            请求里同步等待索引全部完成。因此这里先做并发门禁，再异步拉起独立子进程。

        Returns:
            当前任务快照。若已经存在运行中的重建任务，则返回那条任务并标记 `reused_existing_job=true`。

        Raises:
            ApiCatalogIndexJobStartError: 当子进程无法启动时抛出。
        """

        async with self._lock:
            running_job = self._get_running_job_locked()
            if running_job is not None:
                return running_job.model_copy(
                    update={
                        "reused_existing_job": True,
                        "message": "已有 API Catalog 重建任务正在运行，已复用当前任务。",
                    }
                )

            command = [self._python_executable, "-m", self._module_name]
            requested_at = self._clock()
            job_id = uuid4().hex

            try:
                process = await self._process_factory(command, self._working_directory)
            except Exception as exc:  # pragma: no cover - 依赖系统子进程能力
                raise ApiCatalogIndexJobStartError(f"启动 API Catalog 重建任务失败: {exc}") from exc

            job_snapshot = ApiCatalogIndexJobResponse(
                job_id=job_id,
                status=ApiCatalogIndexJobStatus.RUNNING,
                message="API Catalog 重建任务已启动。",
                reused_existing_job=False,
                requested_at=requested_at,
                started_at=requested_at,
                finished_at=None,
                pid=getattr(process, "pid", None),
                exit_code=None,
                command=command,
                stdout_tail="",
                stderr_tail="",
            )
            self._jobs[job_id] = job_snapshot
            self._running_job_id = job_id
            self._watch_tasks[job_id] = asyncio.create_task(self._watch_process(job_id, process))
            return job_snapshot.model_copy(deep=True)

    def get_job(self, job_id: str) -> ApiCatalogIndexJobResponse | None:
        """读取任务快照。

        功能：
            状态查询接口只应暴露任务事实，而不应该反向持有子进程句柄。这里返回深拷贝，
            是为了防止调用方修改内存态对象，污染进程内任务表。
        """

        job_snapshot = self._jobs.get(job_id)
        if job_snapshot is None:
            return None
        return job_snapshot.model_copy(deep=True)

    async def wait_for_job(self, job_id: str) -> ApiCatalogIndexJobResponse | None:
        """等待指定任务完成。

        功能：
            这主要服务于测试与未来运维脚本，避免测试用例为了等后台 watch task 完成而写
            基于 `sleep()` 的脆弱轮询。
        """

        watch_task = self._watch_tasks.get(job_id)
        if watch_task is not None:
            await watch_task
        return self.get_job(job_id)

    async def close(self) -> None:
        """等待当前仍在收尾的 watch task 完成。"""

        if not self._watch_tasks:
            return
        await asyncio.gather(*self._watch_tasks.values(), return_exceptions=True)

    def _get_running_job_locked(self) -> ApiCatalogIndexJobResponse | None:
        """读取当前运行中的任务。

        功能：
            系统当前故意限制同一时刻只有一个重建任务在跑，避免多个重建子进程同时写
            Milvus / Neo4j，把“修边界”又变成“制造更难排查的并发问题”。
        """

        if self._running_job_id is None:
            return None
        running_job = self._jobs.get(self._running_job_id)
        if running_job is None or running_job.status != ApiCatalogIndexJobStatus.RUNNING:
            self._running_job_id = None
            return None
        return running_job

    async def _watch_process(self, job_id: str, process: asyncio.subprocess.Process) -> None:
        """后台观察子进程结果并回填任务状态。

        功能：
            这里必须和 `start_rebuild()` 解耦。HTTP 请求返回之后，真正的索引重建还在继续，
            所以状态迁移、输出截断和运行中标记释放只能在独立 watch task 中完成。
        """

        stdout_tail = ""
        stderr_tail = ""
        exit_code = 1
        message = "API Catalog 重建任务失败。"
        job_status = ApiCatalogIndexJobStatus.FAILED

        try:
            stdout_bytes, stderr_bytes = await process.communicate()
            stdout_tail = _decode_output_tail(stdout_bytes)
            stderr_tail = _decode_output_tail(stderr_bytes)
            exit_code = int(getattr(process, "returncode", 1) or 0)
            if exit_code == 0:
                job_status = ApiCatalogIndexJobStatus.SUCCESS
                message = "API Catalog 重建任务执行完成。"
            else:
                message = "API Catalog 重建任务执行失败，请查看输出日志。"
        except Exception as exc:  # pragma: no cover - 依赖系统子进程能力
            stderr_tail = _decode_output_tail(str(exc).encode("utf-8", errors="replace"))
            message = f"API Catalog 重建任务监控失败: {exc}"

        async with self._lock:
            current_snapshot = self._jobs.get(job_id)
            if current_snapshot is None:
                self._watch_tasks.pop(job_id, None)
                if self._running_job_id == job_id:
                    self._running_job_id = None
                return

            self._jobs[job_id] = current_snapshot.model_copy(
                update={
                    "status": job_status,
                    "message": message,
                    "finished_at": self._clock(),
                    "exit_code": exit_code,
                    "stdout_tail": stdout_tail,
                    "stderr_tail": stderr_tail,
                    "reused_existing_job": False,
                }
            )
            self._watch_tasks.pop(job_id, None)
            if self._running_job_id == job_id:
                self._running_job_id = None


async def _spawn_indexer_process(
    command: list[str],
    working_directory: Path,
) -> asyncio.subprocess.Process:
    """拉起真正的离线索引子进程。

    功能：
        这里统一封装默认子进程参数，保证生产代码和测试替身都遵循同一个工厂签名。
        之所以显式收集 stdout/stderr，是为了让管理端能看到最小必要的离线结果摘要，
        而不是只拿到一个“失败了”但完全不知道子进程输出了什么。
    """

    return await asyncio.create_subprocess_exec(
        *command,
        cwd=str(working_directory),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


def _decode_output_tail(output: bytes | None) -> str:
    """截断并解码子进程输出。

    功能：
        离线索引日志可能很长；管理端状态接口只需要最后一段上下文帮助定位失败原因，
        没必要把整段输出塞进内存和 HTTP 响应。
    """

    if not output:
        return ""
    return output.decode("utf-8", errors="replace")[-_MAX_OUTPUT_TAIL_CHARS:]
