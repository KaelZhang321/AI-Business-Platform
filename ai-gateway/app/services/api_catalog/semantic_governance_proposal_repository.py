"""字段治理提案写库仓储。

功能：
    负责把离线提案批次写入 `semantic_field_dict / semantic_field_alias / semantic_field_value_map`，
    并在写入前执行人工锁冲突熔断，避免 LLM/规则引擎在稳态阶段反复覆盖人工确认结果。
"""

from __future__ import annotations

from typing import Any

import aiomysql

from app.core.config import settings
from app.core.mysql import build_business_mysql_conn_params
from app.services.api_catalog.semantic_governance_proposal_models import (
    SemanticAliasProposal,
    SemanticDictProposal,
    SemanticGovernancePersistSummary,
    SemanticGovernanceProposalBatch,
    SemanticValueMapProposal,
)

_TABLE_DICT = "semantic_field_dict"
_TABLE_ALIAS = "semantic_field_alias"
_TABLE_VALUE_MAP = "semantic_field_value_map"


class SemanticGovernanceProposalRepositoryError(RuntimeError):
    """字段治理提案写库异常。"""


class SemanticGovernanceProposalRepository:
    """字段治理提案写库仓储。

    功能：
        在同一事务里落库本批提案，并执行人工锁冲突熔断与冲突计数推进。

    Args:
        conflict_fuse_threshold: 连续冲突达到该阈值后，把线上规则标记为 `conflict_review`。
    """

    def __init__(self, *, conflict_fuse_threshold: int = 3) -> None:
        self._pool: aiomysql.Pool | None = None
        self._columns_cache: dict[str, set[str]] = {}
        self._conflict_fuse_threshold = conflict_fuse_threshold

    async def persist_batch(self, run_id: str, batch: SemanticGovernanceProposalBatch) -> SemanticGovernancePersistSummary:
        """写入一批治理提案。

        功能：
            批次写入必须和冲突计数更新绑定到同一事务，否则会出现“提案没写进去但冲突计数已+1”
            这种审计不可解释的中间态。

        Returns:
            本次写库的聚合摘要。

        Raises:
            SemanticGovernanceProposalRepositoryError: 任一 SQL 执行失败时抛出。
        """

        summary = SemanticGovernancePersistSummary()
        pool = await self._get_pool()
        conn: aiomysql.Connection | None = None
        try:
            async with pool.acquire() as acquired_conn:
                conn = acquired_conn
                await conn.begin()
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 1) 先写主字典，保证 alias/value_map 的 semantic_key 总有可追溯落点。
                    for proposal in batch.dict_proposals:
                        written = await self._upsert_dict_proposal(cursor, run_id=run_id, proposal=proposal)
                        summary.dict_written += int(written)

                    # 2) 再写别名；这里需要先做人工锁冲突检查，避免覆盖人工确认语义。
                    for proposal in batch.alias_proposals:
                        outcome = await self._upsert_alias_proposal_with_guard(cursor, run_id=run_id, proposal=proposal)
                        summary.alias_written += int(outcome["written"])
                        summary.rejected_by_human_lock += int(outcome["rejected"])
                        summary.conflict_review_marked += int(outcome["conflict_review_marked"])

                    # 3) 最后写枚举值映射，防止 value_map 指向一个尚未落库的 semantic_key。
                    for proposal in batch.value_map_proposals:
                        written = await self._upsert_value_map_proposal(cursor, run_id=run_id, proposal=proposal)
                        summary.value_map_written += int(written)
                await conn.commit()
        except Exception as exc:
            try:
                if conn is not None:
                    await conn.rollback()
            except Exception:
                pass
            raise SemanticGovernanceProposalRepositoryError(f"写入治理提案失败: {exc}") from exc
        return summary

    async def close(self) -> None:
        """释放连接池。"""

        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def _upsert_dict_proposal(
        self,
        cursor: aiomysql.DictCursor,
        *,
        run_id: str,
        proposal: SemanticDictProposal,
    ) -> bool:
        """写入主字典提案。"""

        columns = await self._get_table_columns(_TABLE_DICT, cursor=cursor)
        payload = {
            "semantic_key": proposal.semantic_key,
            "standard_key": proposal.standard_key,
            "entity_code": proposal.entity_code,
            "canonical_name": proposal.canonical_name,
            "label": proposal.label,
            "field_type": proposal.field_type,
            "value_type": proposal.value_type,
            "category": proposal.category,
            "display_domain_code": proposal.display_domain_code,
            "display_domain_label": proposal.display_domain_label,
            "display_section_code": proposal.display_section_code,
            "display_section_label": proposal.display_section_label,
            "graph_role": proposal.graph_role,
            "is_identifier": int(proposal.is_identifier),
            "is_graph_enabled": int(proposal.is_graph_enabled),
            "description": proposal.description,
            "risk_level": proposal.risk_level,
            "run_id": run_id,
            "review_status": proposal.review_status,
            "current_flag": 0,
            "source": proposal.source,
            "confidence": proposal.confidence,
            "is_active": 1,
        }
        sql, params = _build_upsert_sql(_TABLE_DICT, payload=payload, available_columns=columns)
        if not sql:
            return False
        await cursor.execute(sql, params)
        return True

    async def _upsert_alias_proposal_with_guard(
        self,
        cursor: aiomysql.DictCursor,
        *,
        run_id: str,
        proposal: SemanticAliasProposal,
    ) -> dict[str, bool]:
        """写入别名提案并执行人工锁冲突熔断。"""

        columns = await self._get_table_columns(_TABLE_ALIAS, cursor=cursor)
        existing = await self._load_existing_alias_row(cursor, proposal=proposal, available_columns=columns)
        if existing is not None and str(existing.get("semantic_key") or "") != proposal.semantic_key:
            human_lock = _to_bool(existing.get("human_lock"))
            if human_lock:
                conflict_review_marked = await self._bump_alias_conflict_streak(
                    cursor,
                    proposal=proposal,
                    existing=existing,
                    available_columns=columns,
                )
                return {
                    "written": False,
                    "rejected": True,
                    "conflict_review_marked": conflict_review_marked,
                }

        payload = {
            "semantic_key": proposal.semantic_key,
            "alias": proposal.alias,
            "scope_type": proposal.scope_type,
            "scope_value": proposal.scope_value,
            "direction": proposal.direction,
            "location": proposal.location,
            "json_path_pattern": proposal.json_path_pattern,
            "priority": proposal.priority,
            "source": proposal.source,
            "confidence": proposal.confidence,
            "run_id": run_id,
            "review_status": proposal.review_status,
            "current_flag": 0,
            "is_active": 1,
        }
        sql, params = _build_upsert_sql(_TABLE_ALIAS, payload=payload, available_columns=columns)
        if not sql:
            return {"written": False, "rejected": False, "conflict_review_marked": False}
        await cursor.execute(sql, params)
        return {"written": True, "rejected": False, "conflict_review_marked": False}

    async def _upsert_value_map_proposal(
        self,
        cursor: aiomysql.DictCursor,
        *,
        run_id: str,
        proposal: SemanticValueMapProposal,
    ) -> bool:
        """写入值域映射提案。"""

        columns = await self._get_table_columns(_TABLE_VALUE_MAP, cursor=cursor)
        payload = {
            "semantic_key": proposal.semantic_key,
            "scope_type": proposal.scope_type,
            "scope_value": proposal.scope_value,
            "raw_value": proposal.raw_value,
            "raw_label": proposal.raw_label,
            "standard_code": proposal.standard_code,
            "standard_label": proposal.standard_label,
            "sort_order": proposal.sort_order,
            "source": proposal.source,
            "confidence": proposal.confidence,
            "run_id": run_id,
            "review_status": proposal.review_status,
            "current_flag": 0,
            "is_active": 1,
        }
        sql, params = _build_upsert_sql(_TABLE_VALUE_MAP, payload=payload, available_columns=columns)
        if not sql:
            return False
        await cursor.execute(sql, params)
        return True

    async def _load_existing_alias_row(
        self,
        cursor: aiomysql.DictCursor,
        *,
        proposal: SemanticAliasProposal,
        available_columns: set[str],
    ) -> dict[str, Any] | None:
        """加载当前在线别名规则。"""

        select_columns = ["semantic_key"]
        if "id" in available_columns:
            select_columns.append("id")
        if "human_lock" in available_columns:
            select_columns.append("human_lock")
        if "conflict_streak" in available_columns:
            select_columns.append("conflict_streak")
        if "review_status" in available_columns:
            select_columns.append("review_status")
        where_parts = [
            "alias = %s",
            "scope_type = %s",
            "scope_value = %s",
            "direction = %s",
            "location = %s",
        ]
        if "is_active" in available_columns:
            where_parts.append("is_active = 1")
        if "current_flag" in available_columns:
            where_parts.append("current_flag = 1")
        order_parts: list[str] = []
        if "current_flag" in available_columns:
            order_parts.append("current_flag DESC")
        if "id" in available_columns:
            order_parts.append("id DESC")
        order_clause = f"ORDER BY {', '.join(order_parts)} " if order_parts else ""
        sql = (
            f"SELECT {', '.join(select_columns)} FROM {_TABLE_ALIAS} "
            f"WHERE {' AND '.join(where_parts)} "
            f"{order_clause}LIMIT 1"
        )
        await cursor.execute(
            sql,
            (
                proposal.alias,
                proposal.scope_type,
                proposal.scope_value,
                proposal.direction,
                proposal.location,
            ),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def _bump_alias_conflict_streak(
        self,
        cursor: aiomysql.DictCursor,
        *,
        proposal: SemanticAliasProposal,
        existing: dict[str, Any],
        available_columns: set[str],
    ) -> bool:
        """推进冲突计数，并在达到阈值时打上复审标记。"""

        if "conflict_streak" not in available_columns and "review_status" not in available_columns:
            return False

        current_streak = int(existing.get("conflict_streak") or 0)
        new_streak = current_streak + 1
        update_parts: list[str] = []
        params: list[Any] = []
        if "conflict_streak" in available_columns:
            update_parts.append("conflict_streak = %s")
            params.append(new_streak)
        conflict_review_marked = False
        if "review_status" in available_columns and new_streak >= self._conflict_fuse_threshold:
            update_parts.append("review_status = %s")
            params.append("conflict_review")
            conflict_review_marked = True
        if not update_parts:
            return False

        # 这里优先按主键更新，是为了避免别名组合键后续被策略调整时误更新多行历史记录。
        if "id" in available_columns and existing.get("id") is not None:
            sql = f"UPDATE {_TABLE_ALIAS} SET {', '.join(update_parts)} WHERE id = %s"
            params.append(existing["id"])
        else:
            where_parts = [
                "alias = %s",
                "scope_type = %s",
                "scope_value = %s",
                "direction = %s",
                "location = %s",
            ]
            sql = f"UPDATE {_TABLE_ALIAS} SET {', '.join(update_parts)} WHERE {' AND '.join(where_parts)}"
            params.extend(
                [
                    proposal.alias,
                    proposal.scope_type,
                    proposal.scope_value,
                    proposal.direction,
                    proposal.location,
                ]
            )
        await cursor.execute(sql, tuple(params))
        return conflict_review_marked

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=3,
                **build_business_mysql_conn_params(),
            )
        return self._pool

    async def _get_table_columns(self, table_name: str, *, cursor: aiomysql.DictCursor) -> set[str]:
        """读取并缓存表结构列。"""

        cached = self._columns_cache.get(table_name)
        if cached is not None:
            return cached

        await cursor.execute(
            """
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
""",
            (settings.business_mysql_database, table_name),
        )
        rows = await cursor.fetchall()
        columns = {str(row.get("COLUMN_NAME") or "").strip() for row in rows}
        self._columns_cache[table_name] = columns
        return columns


def _build_upsert_sql(
    table_name: str,
    *,
    payload: dict[str, Any],
    available_columns: set[str],
) -> tuple[str, tuple[Any, ...]]:
    """构建按列能力降级的 UPSERT SQL。"""

    insert_items = [(column, value) for column, value in payload.items() if column in available_columns]
    if not insert_items:
        return "", ()

    insert_columns = [column for column, _ in insert_items]
    insert_values = [value for _, value in insert_items]
    insert_placeholders = ", ".join(["%s"] * len(insert_columns))
    updatable_columns = [column for column in insert_columns if column not in {"semantic_key", "alias", "raw_value"}]
    if updatable_columns:
        update_clause = ", ".join(f"{column} = VALUES({column})" for column in updatable_columns)
        sql = (
            f"INSERT INTO {table_name} ({', '.join(insert_columns)}) "
            f"VALUES ({insert_placeholders}) "
            f"ON DUPLICATE KEY UPDATE {update_clause}"
        )
    else:
        sql = f"INSERT IGNORE INTO {table_name} ({', '.join(insert_columns)}) VALUES ({insert_placeholders})"
    return sql, tuple(insert_values)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "y", "on"}
