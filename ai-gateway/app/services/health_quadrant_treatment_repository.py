"""治疗四象限知识库召回仓储。"""

from __future__ import annotations

import logging
from typing import Any

import aiomysql

from app.services.health_quadrant_mysql_pools import HealthQuadrantMySQLPools

logger = logging.getLogger(__name__)
_TABLE_NAME = "function_medicine_ai_mapping"


class HealthQuadrantTreatmentRepositoryError(RuntimeError):
    """治疗四象限知识库仓储异常。"""


class HealthQuadrantTreatmentRepository:
    """治疗四象限知识库召回仓储。

    功能：
        基于 triage 输出的系统归属与异常项，查询功能医学映射表并返回候选项目。
        该仓储只负责“召回事实”，不承担安全过滤与装填决策。
    """

    def __init__(self, *, mysql_pools: HealthQuadrantMySQLPools | None = None) -> None:
        self._mysql_pools = mysql_pools or HealthQuadrantMySQLPools(minsize=1, maxsize=3)
        self._owned_pool = mysql_pools is None

    async def match_candidates(self, *, triage_items: list[Any]) -> list[dict[str, Any]]:
        """根据 triage 条目召回候选项目。

        Args:
            triage_items: `HealthQuadrantService` 内部 triage 条目数组，至少包含
                `item_name/value_or_desc/quadrant/belong_system`。

        Returns:
            候选项目数组，每条包含：
            `project_name/package_version/quadrant/belong_system/trigger_item/contraindications/match_source`。

        Raises:
            HealthQuadrantTreatmentRepositoryError: 当数据库查询失败时抛出。
        """

        if not triage_items:
            return []

        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        try:
            pool = await self._mysql_pools.get_business_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    for item in triage_items:
                        rows = await self._query_one_triage_item(
                            cursor=cursor,
                            belong_system=str(getattr(item, "belong_system", "")),
                            trigger_item=str(getattr(item, "item_name", "")),
                            quadrant=str(getattr(item, "quadrant", "")),
                        )
                        for row in rows:
                            dedupe_key = (
                                str(row.get("project_name") or "").strip(),
                                str(row.get("package_version") or "").strip(),
                                str(row.get("quadrant") or "").strip(),
                                str(row.get("belong_system") or "").strip(),
                            )
                            if not dedupe_key[0]:
                                continue
                            if dedupe_key in seen:
                                continue
                            seen.add(dedupe_key)
                            results.append(row)
        except Exception as exc:
            logger.error("health quadrant treatment repository query failed error=%s", exc, exc_info=True)
            raise HealthQuadrantTreatmentRepositoryError(f"治疗知识库召回失败: {exc}") from exc
        return results

    async def close(self) -> None:
        """关闭内部持有的连接池。

        功能：
            当仓储内部自行创建连接池时，服务关闭阶段需显式释放资源；
            若由外部注入共享池，则不重复关闭，避免误伤其它链路。
        """

        if not self._owned_pool:
            return
        await self._mysql_pools.close()

    async def _query_one_triage_item(
        self,
        *,
        cursor: aiomysql.DictCursor,
        belong_system: str,
        trigger_item: str,
        quadrant: str,
    ) -> list[dict[str, Any]]:
        """查询单条 triage 条目对应候选项目。

        功能：
            先走 `indicator_name` 精确匹配，再用 `indications LIKE` 补召回，
            用 UNION ALL 保留来源并在 Python 侧做去重，便于后续调试召回质量。
        """

        if not belong_system:
            return []

        sql = f"""
        SELECT DISTINCT
          t.project_name,
          t.package_version,
          t.core_effect, 
	      t.indications,
          t.contraindications
        FROM {_TABLE_NAME} t
        WHERE t.status = 'active'
          AND t.system_name = %s
        """.strip()
        await cursor.execute(sql, belong_system)
        rows = await cursor.fetchall()

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            project_name = str(row.get("project_name") or "").strip()
            package_version = str(row.get("package_version") or "").strip() or "-"
            if not project_name:
                continue
            key = (project_name, package_version)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(
                {
                    "project_name": project_name,
                    "package_version": package_version,
                    "core_effect": row.get("core_effect") or "",
                    "indications": row.get("indications") or "",
                    "contraindications": row.get("contraindications") or "",
                    "quadrant": quadrant,
                    "belong_system": belong_system
                }
            )
        return deduped
