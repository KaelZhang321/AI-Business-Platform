"""字段治理发布控制服务。

功能：
    负责把“草稿 run”切换为“在线版本”以及执行一键回滚。该服务只操作治理三表的发布态字段，
    不承担 LLM 清洗或索引写入逻辑，避免控制面职责扩散。
"""

from __future__ import annotations

from datetime import UTC, datetime
import aiomysql

from app.core.config import settings
from app.core.mysql import build_business_mysql_conn_params
from app.models.schemas import ApiCatalogGovernanceRunResponse, SemanticCurationRunStatus
from app.services.api_catalog.semantic_curation_run_repository import (
    SemanticCurationRunRepository,
    SemanticCurationRunRepositoryError,
)

_TABLE_DICT = "semantic_field_dict"
_TABLE_ALIAS = "semantic_field_alias"
_TABLE_VALUE_MAP = "semantic_field_value_map"
_GOVERNANCE_TABLES = (_TABLE_DICT, _TABLE_ALIAS, _TABLE_VALUE_MAP)


class SemanticGovernancePublicationError(RuntimeError):
    """字段治理发布控制异常。"""


class SemanticGovernancePublicationService:
    """字段治理发布与回滚服务。

    功能：
        以单事务执行三表 `current_flag` 切流，保证运行期读取规则不会看到半更新状态。

    Args:
        run_repository: run 控制面仓储，用于补充发布状态回写。
        clock: 可注入时钟，便于测试稳定断言。
    """

    def __init__(
        self,
        *,
        run_repository: SemanticCurationRunRepository | None = None,
        clock: callable | None = None,
    ) -> None:
        self._run_repository = run_repository or SemanticCurationRunRepository()
        self._pool: aiomysql.Pool | None = None
        self._columns_cache: dict[str, set[str]] = {}
        self._clock = clock or (lambda: datetime.now(UTC))

    async def promote_run(self, run_id: str, *, reviewer: str | None = None) -> ApiCatalogGovernanceRunResponse | None:
        """发布指定 run。

        功能：
            把 run 内已审核通过的数据切换为在线版本。切流前先读取最近已发布 run，作为回滚锚点
            写回 `previous_run_id`，这样后续异常时可直接定位上一个稳定版本。
        """

        previous_promoted = await self._run_repository.get_latest_promoted_run()
        previous_run_id = previous_promoted.run_id if previous_promoted is not None else None
        await self._promote_three_tables(run_id)

        try:
            await self._run_repository.update_run(
                run_id,
                status=SemanticCurationRunStatus.PROMOTED,
                previous_run_id=previous_run_id,
                finished_at=self._clock(),
                error_message=None if reviewer is None else f"approved by {reviewer}",
            )
        except SemanticCurationRunRepositoryError as exc:
            raise SemanticGovernancePublicationError(f"发布成功但回写 run 状态失败: {exc}") from exc
        return await self._run_repository.get_run(run_id)

    async def rollback_to_run(
        self,
        target_run_id: str,
        *,
        reason: str | None = None,
    ) -> ApiCatalogGovernanceRunResponse | None:
        """回滚到指定历史 run。

        功能：
            把当前在线版本统一降级，再把目标 run 切回在线，保证回滚操作和正常发布使用同一套
            原子机制，避免“发布和回滚逻辑各写一套”造成行为分叉。
        """

        await self._rollback_three_tables(target_run_id)
        note = f"rolled back: {reason}" if reason else "rolled back"
        try:
            await self._run_repository.update_run(
                target_run_id,
                status=SemanticCurationRunStatus.PROMOTED,
                finished_at=self._clock(),
                error_message=note,
            )
        except SemanticCurationRunRepositoryError as exc:
            raise SemanticGovernancePublicationError(f"回滚成功但回写 run 状态失败: {exc}") from exc
        return await self._run_repository.get_run(target_run_id)

    async def close(self) -> None:
        """释放服务连接。"""

        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
        await self._run_repository.close()

    async def _promote_three_tables(self, run_id: str) -> None:
        """执行三表原子切流。

        功能：
            1. 先按 `run_id + review_status` 找出本轮要上线的 semantic_key
            2. 旧版本 `current_flag=1` 降级为 0
            3. 本轮记录切换为 `current_flag=1`
        """

        await self._ensure_table_capabilities()
        pool = await self._get_pool()
        conn: aiomysql.Connection | None = None
        try:
            async with pool.acquire() as acquired_conn:
                conn = acquired_conn
                await conn.begin()
                async with conn.cursor() as cursor:
                    # 1) 构建待发布语义键临时表；把 key 集合预先落地，可以确保三表切流使用同一批 key。
                    await cursor.execute("DROP TEMPORARY TABLE IF EXISTS tmp_semantic_promote_keys")
                    await cursor.execute(
                        """
CREATE TEMPORARY TABLE tmp_semantic_promote_keys AS
SELECT DISTINCT semantic_key
FROM semantic_field_dict
WHERE run_id = %s
  AND is_active = 1
  AND review_status = 'approved'
""",
                        (run_id,),
                    )

                    # 2) 降级旧版本，避免同一个 semantic_key 出现多个 current_flag=1 的并存状态。
                    for table_name in _GOVERNANCE_TABLES:
                        await cursor.execute(
                            f"""
UPDATE {table_name}
SET current_flag = 0
WHERE current_flag = 1
  AND semantic_key IN (SELECT semantic_key FROM tmp_semantic_promote_keys)
""",
                        )

                    # 3) 发布新版本，只放行本轮审核通过的数据。
                    for table_name in _GOVERNANCE_TABLES:
                        await cursor.execute(
                            f"""
UPDATE {table_name}
SET current_flag = 1
WHERE run_id = %s
  AND is_active = 1
  AND review_status = 'approved'
""",
                            (run_id,),
                        )

                    # 4) 若主字典支持冲突计数，发布成功后重置 streak，避免历史冲突阻塞后续自动化。
                    dict_columns = self._columns_cache.get(_TABLE_DICT, set())
                    if "conflict_streak" in dict_columns:
                        await cursor.execute(
                            """
UPDATE semantic_field_dict
SET conflict_streak = 0
WHERE run_id = %s
  AND current_flag = 1
""",
                            (run_id,),
                        )
                await conn.commit()
        except Exception as exc:
            try:
                if conn is not None:
                    await conn.rollback()
            except Exception:
                pass
            raise SemanticGovernancePublicationError(f"发布 run 失败: {exc}") from exc

    async def _rollback_three_tables(self, target_run_id: str) -> None:
        """执行三表原子回滚。"""

        await self._ensure_table_capabilities()
        pool = await self._get_pool()
        conn: aiomysql.Connection | None = None
        try:
            async with pool.acquire() as acquired_conn:
                conn = acquired_conn
                await conn.begin()
                async with conn.cursor() as cursor:
                    # 1) 先清空当前在线标记，确保回滚动作不会和当前在线版本叠加。
                    for table_name in _GOVERNANCE_TABLES:
                        await cursor.execute(f"UPDATE {table_name} SET current_flag = 0 WHERE current_flag = 1")

                    # 2) 再把目标 run 切回在线，仅恢复审核通过的数据。
                    for table_name in _GOVERNANCE_TABLES:
                        await cursor.execute(
                            f"""
UPDATE {table_name}
SET current_flag = 1
WHERE run_id = %s
  AND is_active = 1
  AND review_status = 'approved'
""",
                            (target_run_id,),
                        )
                await conn.commit()
        except Exception as exc:
            try:
                if conn is not None:
                    await conn.rollback()
            except Exception:
                pass
            raise SemanticGovernancePublicationError(f"回滚 run 失败: {exc}") from exc

    async def _ensure_table_capabilities(self) -> None:
        """校验发布所需列能力。

        功能：
            文档里的切流依赖 `run_id/review_status/current_flag/semantic_key`。如果缺任何一个，
            发布结果就不再可预测，因此这里必须前置硬校验并明确报错。
        """

        required_columns = {"run_id", "review_status", "current_flag", "semantic_key", "is_active"}
        for table_name in _GOVERNANCE_TABLES:
            columns = await self._get_table_columns(table_name)
            missing = required_columns - columns
            if missing:
                raise SemanticGovernancePublicationError(
                    f"{table_name} 缺少发布所需列: {sorted(missing)}，请先完成治理 DDL 升级。"
                )

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=3,
                **build_business_mysql_conn_params(),
            )
        return self._pool

    async def _get_table_columns(self, table_name: str) -> set[str]:
        """读取并缓存表结构列集合。"""

        cached = self._columns_cache.get(table_name)
        if cached is not None:
            return cached

        query = """
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
"""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, (settings.business_mysql_database, table_name))
                    rows = await cursor.fetchall()
        except Exception as exc:
            raise SemanticGovernancePublicationError(f"读取 {table_name} 结构失败: {exc}") from exc

        columns = {str(row.get("COLUMN_NAME") or "").strip() for row in rows}
        self._columns_cache[table_name] = columns
        return columns
