"""字段治理 run 控制面仓储。

功能：
    管理 `semantic_curation_run` 的生命周期读写，把“离线任务状态”和“线上发布状态”
    从 API 触发逻辑里拆出来，避免控制面事实散落在多个 service 的内存对象中。
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

import aiomysql

from app.core.config import settings
from app.models.schemas import (
    ApiCatalogGovernanceRunResponse,
    SemanticCurationMode,
    SemanticCurationPhase,
    SemanticCurationRunStatus,
)

_RUN_TABLE = "semantic_curation_run"
_RUN_KNOWN_COLUMNS = {
    "id",
    "run_id",
    "phase",
    "mode",
    "status",
    "previous_run_id",
    "triggered_by",
    "trigger_reason",
    "high_coverage_rate",
    "low_pending_rate",
    "manual_reject_rate",
    "indexed",
    "skipped",
    "failed_count",
    "started_at",
    "finished_at",
    "error_message",
    "created_at",
}

_EnumType = TypeVar("_EnumType", bound=Enum)


class SemanticCurationRunRepositoryError(RuntimeError):
    """字段治理 run 仓储异常。"""


class SemanticCurationRunRepository:
    """字段治理 run 仓储。

    功能：
        提供 run 的创建、状态推进和快照查询能力。该仓储显式做了列能力探测，保证在
        数据库 DDL 尚未完全升级时，服务层可以给出明确错误而不是返回隐晦 SQL 异常。

    Args:
        clock: 可注入时钟，方便测试稳定断言时间字段。

    Edge Cases:
        业务库连接池必须由上层注入，避免控制面仓储在运行期隐式创建第二套连接生命周期。
    """

    def __init__(self, *, clock: callable | None = None, pool: aiomysql.Pool | None = None) -> None:
        self._pool = pool
        self._columns_cache: set[str] | None = None
        self._clock = clock or (lambda: datetime.now(UTC))

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
        """创建新的治理 run。

        Returns:
            刚创建完成的 run 快照。

        Raises:
            SemanticCurationRunRepositoryError: 当 run 表不可写或关键列缺失时抛出。
        """

        columns = await self._get_columns()
        if "run_id" not in columns:
            raise SemanticCurationRunRepositoryError("semantic_curation_run 缺少 run_id 列，无法写入治理 run。")

        now = self._clock()
        payload: dict[str, Any] = {
            "run_id": run_id,
            "phase": phase.value,
            "mode": mode.value,
            "status": status.value,
            "previous_run_id": previous_run_id,
            "triggered_by": triggered_by,
            "trigger_reason": trigger_reason,
            "started_at": now,
        }
        insert_payload = {key: value for key, value in payload.items() if key in columns}
        sql = (
            f"INSERT INTO {_RUN_TABLE} ({', '.join(insert_payload.keys())}) "
            f"VALUES ({', '.join(['%s'] * len(insert_payload))})"
        )

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, tuple(insert_payload.values()))
                await conn.commit()
        except Exception as exc:
            raise SemanticCurationRunRepositoryError(f"创建治理 run 失败: {exc}") from exc

        snapshot = await self.get_run(run_id)
        if snapshot is None:
            # DDL 不完整时可能没有可读列，兜底返回最小可用快照，避免上层链路彻底丢 run 句柄。
            return ApiCatalogGovernanceRunResponse(
                run_id=run_id,
                phase=phase,
                mode=mode,
                status=status,
                previous_run_id=previous_run_id,
                triggered_by=triggered_by,
                trigger_reason=trigger_reason,
                started_at=now,
                finished_at=None,
                error_message=None,
            )
        return snapshot

    async def update_run(
        self,
        run_id: str,
        *,
        status: SemanticCurationRunStatus | None = None,
        previous_run_id: str | None = None,
        high_coverage_rate: float | None = None,
        low_pending_rate: float | None = None,
        manual_reject_rate: float | None = None,
        indexed: int | None = None,
        skipped: int | None = None,
        failed_count: int | None = None,
        finished_at: datetime | None = None,
        error_message: str | None = None,
    ) -> ApiCatalogGovernanceRunResponse | None:
        """更新 run 状态与统计。

        功能：
            治理执行中会多次推进状态；这里用单入口更新是为了把“可变字段白名单”固定住，
            避免调用方直接拼 SQL 导致状态机被绕开。
        """

        columns = await self._get_columns()
        updates: dict[str, Any] = {}
        if status is not None and "status" in columns:
            updates["status"] = status.value
        if previous_run_id is not None and "previous_run_id" in columns:
            updates["previous_run_id"] = previous_run_id
        if high_coverage_rate is not None and "high_coverage_rate" in columns:
            updates["high_coverage_rate"] = high_coverage_rate
        if low_pending_rate is not None and "low_pending_rate" in columns:
            updates["low_pending_rate"] = low_pending_rate
        if manual_reject_rate is not None and "manual_reject_rate" in columns:
            updates["manual_reject_rate"] = manual_reject_rate
        if indexed is not None and "indexed" in columns:
            updates["indexed"] = indexed
        if skipped is not None and "skipped" in columns:
            updates["skipped"] = skipped
        if failed_count is not None and "failed_count" in columns:
            updates["failed_count"] = failed_count
        if finished_at is not None and "finished_at" in columns:
            updates["finished_at"] = finished_at
        if error_message is not None and "error_message" in columns:
            updates["error_message"] = error_message

        if not updates:
            return await self.get_run(run_id)

        set_clause = ", ".join(f"{field} = %s" for field in updates.keys())
        sql = f"UPDATE {_RUN_TABLE} SET {set_clause} WHERE run_id = %s ORDER BY id DESC LIMIT 1"
        params = [*updates.values(), run_id]

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, tuple(params))
                await conn.commit()
        except Exception as exc:
            raise SemanticCurationRunRepositoryError(f"更新治理 run 失败: {exc}") from exc

        return await self.get_run(run_id)

    async def get_run(self, run_id: str) -> ApiCatalogGovernanceRunResponse | None:
        """按 run_id 查询快照。"""

        columns = await self._get_columns()
        if "run_id" not in columns:
            return None

        selected_columns = [column for column in _RUN_KNOWN_COLUMNS if column in columns]
        sql = (
            f"SELECT {', '.join(selected_columns)} "
            f"FROM {_RUN_TABLE} WHERE run_id = %s ORDER BY id DESC LIMIT 1"
        )

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, (run_id,))
                    row = await cursor.fetchone()
        except Exception as exc:
            raise SemanticCurationRunRepositoryError(f"查询治理 run 失败: {exc}") from exc

        if not row:
            return None
        return _row_to_run_snapshot(dict(row))

    async def get_latest_promoted_run(self) -> ApiCatalogGovernanceRunResponse | None:
        """查询最近一次已发布的 run。"""

        columns = await self._get_columns()
        if "status" not in columns:
            return None
        selected_columns = [column for column in _RUN_KNOWN_COLUMNS if column in columns]
        sql = (
            f"SELECT {', '.join(selected_columns)} "
            f"FROM {_RUN_TABLE} "
            "WHERE status = %s "
            "ORDER BY COALESCE(finished_at, started_at) DESC, id DESC LIMIT 1"
        )

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, (SemanticCurationRunStatus.PROMOTED.value,))
                    row = await cursor.fetchone()
        except Exception as exc:
            raise SemanticCurationRunRepositoryError(f"查询最近已发布 run 失败: {exc}") from exc

        if not row:
            return None
        return _row_to_run_snapshot(dict(row))

    async def close(self) -> None:
        """仓储不持有连接池所有权，因此 close 为 no-op。"""

    async def _get_pool(self) -> aiomysql.Pool:
        """读取应用级注入的治理 run 连接池。"""

        if self._pool is None:
            raise SemanticCurationRunRepositoryError("业务库连接池未注入，请通过 AppResources 或测试桩显式提供。")
        return self._pool

    async def _get_columns(self) -> set[str]:
        """读取 run 表列能力。

        功能：
            当前项目处于迭代迁移期，DDL 可能并未一次性到位。把列探测结果缓存下来可以让
            服务层在运行期做能力降级，而不是让每次写入都碰运气。
        """

        if self._columns_cache is not None:
            return self._columns_cache

        query = """
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
"""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, (settings.business_mysql_database, _RUN_TABLE))
                    rows = await cursor.fetchall()
        except Exception as exc:
            raise SemanticCurationRunRepositoryError(f"读取 run 表结构失败: {exc}") from exc

        self._columns_cache = {str(row.get("COLUMN_NAME") or "").strip() for row in rows}
        return self._columns_cache


def _row_to_run_snapshot(row: dict[str, Any]) -> ApiCatalogGovernanceRunResponse:
    """把数据库行映射成治理 run 快照。"""

    return ApiCatalogGovernanceRunResponse(
        run_id=str(row.get("run_id") or ""),
        phase=_parse_enum(SemanticCurationPhase, row.get("phase"), SemanticCurationPhase.PLAN_B),
        mode=_parse_enum(SemanticCurationMode, row.get("mode"), SemanticCurationMode.INCREMENTAL),
        status=_parse_enum(SemanticCurationRunStatus, row.get("status"), SemanticCurationRunStatus.INIT),
        previous_run_id=_as_optional_text(row.get("previous_run_id")),
        triggered_by=_as_optional_text(row.get("triggered_by")),
        trigger_reason=_as_optional_text(row.get("trigger_reason")),
        high_coverage_rate=_as_optional_float(row.get("high_coverage_rate")),
        low_pending_rate=_as_optional_float(row.get("low_pending_rate")),
        manual_reject_rate=_as_optional_float(row.get("manual_reject_rate")),
        indexed=_as_int(row.get("indexed")),
        skipped=_as_int(row.get("skipped")),
        failed_count=_as_int(row.get("failed_count")),
        started_at=_as_datetime(row.get("started_at")) or datetime.now(UTC),
        finished_at=_as_datetime(row.get("finished_at")),
        error_message=_as_optional_text(row.get("error_message")),
    )


def _parse_enum(enum_type: type[_EnumType], value: Any, default: _EnumType) -> _EnumType:
    """把数据库值解析为枚举，失败时回退默认值。"""

    text = _as_optional_text(value)
    if not text:
        return default
    try:
        return enum_type(text)
    except Exception:
        return default


def _as_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except Exception:
        return 0


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    # MySQL DATETIME 常见形态：YYYY-MM-DD HH:MM:SS 或 ISO8601。
    for layout in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(text, layout)
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except Exception:
            continue
    return None
