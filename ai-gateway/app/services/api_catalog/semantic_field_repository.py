"""字段治理三表仓储。

功能：
    统一从业务 MySQL 读取 `semantic_field_dict / semantic_field_alias / semantic_field_value_map`，
    并把它们转换成 GraphRAG 可直接消费的治理快照。
"""

from __future__ import annotations

import logging
from typing import Any

import aiomysql

from app.core.config import settings
from app.services.api_catalog.graph_models import (
    SemanticFieldAliasRecord,
    SemanticFieldDictRecord,
    SemanticFieldValueMapRecord,
    SemanticGovernanceSnapshot,
)
from app.utils.json_utils import load_json_object_or_none

logger = logging.getLogger(__name__)

_TABLE_DICT = "semantic_field_dict"
_TABLE_ALIAS = "semantic_field_alias"
_TABLE_VALUE_MAP = "semantic_field_value_map"

_DICT_BASE_COLUMNS = [
    "semantic_key",
    "standard_key",
    "entity_code",
    "canonical_name",
    "label",
    "field_type",
    "value_type",
    "category",
    "business_domain",
    "display_domain_code",
    "display_domain_label",
    "display_section_code",
    "display_section_label",
    "graph_role",
    "is_identifier",
    "is_graph_enabled",
    "description",
    "is_active",
]
_ALIAS_BASE_COLUMNS = [
    "semantic_key",
    "alias",
    "scope_type",
    "scope_value",
    "direction",
    "location",
    "json_path_pattern",
    "source",
    "confidence",
    "priority",
    "is_active",
]
_VALUE_MAP_BASE_COLUMNS = [
    "semantic_key",
    "scope_type",
    "scope_value",
    "standard_code",
    "standard_label",
    "raw_value",
    "raw_label",
    "sort_order",
    "source",
    "confidence",
    "is_active",
]
_GOVERNANCE_CONTROL_COLUMNS = ["run_id", "review_status", "current_flag", "human_lock", "conflict_streak"]
_DICT_EXTRA_COLUMNS = ["risk_level"]


class SemanticFieldRepositoryError(RuntimeError):
    """字段治理仓储异常。"""


class SemanticFieldRepository:
    """字段治理仓储。

    功能：
        把治理三表装载成一次只读快照，供 resolver 在同一轮解析里复用。

    Edge Cases:
        - JSON 字段统一 `CAST(... AS CHAR)` 后再解析，避免不同驱动返回 `bytes/dict/str` 混杂
        - 业务库连接池必须由上层注入，治理快照仓储不再运行期自建连接池
    """

    def __init__(self, *, pool: aiomysql.Pool | None = None) -> None:
        self._pool = pool
        self._columns_cache: dict[str, set[str]] = {}

    async def load_active_rules(self) -> SemanticGovernanceSnapshot:
        """加载当前启用的字段治理规则快照。"""
        try:
            field_dict_rows, alias_rows, value_map_rows = await self._load_all_rows()
        except Exception as exc:
            raise SemanticFieldRepositoryError(f"无法加载字段治理规则: {exc}") from exc

        return SemanticGovernanceSnapshot(
            field_dicts=[_build_field_dict_record(row) for row in field_dict_rows],
            aliases=[_build_alias_record(row) for row in alias_rows],
            value_maps=[_build_value_map_record(row) for row in value_map_rows],
        )

    async def _load_all_rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """一次性读取三张治理表。

        功能：
            Resolver 一轮解析通常会处理多条接口。如果三张表拆成多个零碎查询，后续缓存与
            错误排查都会被“到底是哪张表这次读到了旧值”这种问题拖累。
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                dict_columns = await self._get_table_columns(_TABLE_DICT, cursor=cursor)
                alias_columns = await self._get_table_columns(_TABLE_ALIAS, cursor=cursor)
                value_map_columns = await self._get_table_columns(_TABLE_VALUE_MAP, cursor=cursor)

                dict_sql = _build_select_sql(
                    table_name=_TABLE_DICT,
                    available_columns=dict_columns,
                    base_columns=[*_DICT_BASE_COLUMNS, *_GOVERNANCE_CONTROL_COLUMNS, *_DICT_EXTRA_COLUMNS],
                    cast_json_columns={"value_schema": "valueSchema"},
                )
                alias_sql = _build_select_sql(
                    table_name=_TABLE_ALIAS,
                    available_columns=alias_columns,
                    base_columns=[*_ALIAS_BASE_COLUMNS, *_GOVERNANCE_CONTROL_COLUMNS],
                )
                value_map_sql = _build_select_sql(
                    table_name=_TABLE_VALUE_MAP,
                    available_columns=value_map_columns,
                    base_columns=[*_VALUE_MAP_BASE_COLUMNS, *_GOVERNANCE_CONTROL_COLUMNS],
                )

                # 统一发布态过滤：有 `current_flag/review_status` 列时只读线上已审核版本。
                await cursor.execute(dict_sql)
                field_dict_rows = [dict(row) for row in await cursor.fetchall()]
                await cursor.execute(alias_sql)
                alias_rows = [dict(row) for row in await cursor.fetchall()]
                await cursor.execute(value_map_sql)
                value_map_rows = [dict(row) for row in await cursor.fetchall()]
                return field_dict_rows, alias_rows, value_map_rows

    async def _get_table_columns(
        self,
        table_name: str,
        *,
        cursor: aiomysql.Cursor,
    ) -> set[str]:
        """读取并缓存表结构列。

        功能：
            治理 DDL 正在演进，仓储需要在运行期探测“当前库到底有哪些列”，避免把新逻辑
            强绑到未升级实例上导致全链路不可用。
        """

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

    async def _get_pool(self) -> aiomysql.Pool:
        """读取应用级注入的字段治理业务库连接池。"""
        if self._pool is None:
            raise SemanticFieldRepositoryError("业务库连接池未注入，请通过 AppResources 或测试桩显式提供。")
        return self._pool

    async def close(self) -> None:
        """仓储不持有连接池所有权，因此 close 为 no-op。"""


def _build_field_dict_record(row: dict[str, Any]) -> SemanticFieldDictRecord:
    """把治理主表行转换成类型化记录。"""
    return SemanticFieldDictRecord(
        semantic_key=str(row.get("semantic_key") or ""),
        standard_key=_as_optional_text(row.get("standard_key")),
        entity_code=_as_optional_text(row.get("entity_code")),
        canonical_name=_as_optional_text(row.get("canonical_name")),
        label=_as_optional_text(row.get("label")),
        field_type=_as_optional_text(row.get("field_type")),
        value_type=_as_optional_text(row.get("value_type")),
        category=_as_optional_text(row.get("category")),
        business_domain=_as_optional_text(row.get("business_domain")),
        display_domain_code=_as_optional_text(row.get("display_domain_code")),
        display_domain_label=_as_optional_text(row.get("display_domain_label")),
        display_section_code=_as_optional_text(row.get("display_section_code")),
        display_section_label=_as_optional_text(row.get("display_section_label")),
        graph_role=_as_optional_text(row.get("graph_role")) or "none",
        is_identifier=_as_bool(row.get("is_identifier")),
        is_graph_enabled=_as_bool(row.get("is_graph_enabled"), default=True),
        value_schema=load_json_object_or_none(row.get("valueSchema")),
        description=_as_optional_text(row.get("description")),
        is_active=_as_bool(row.get("is_active"), default=True),
        run_id=_as_optional_text(row.get("run_id")),
        review_status=_as_optional_text(row.get("review_status")),
        current_flag=_as_optional_bool(row.get("current_flag")),
        risk_level=_as_optional_text(row.get("risk_level")),
        human_lock=_as_bool(row.get("human_lock"), default=False),
        conflict_streak=int(row.get("conflict_streak") or 0),
    )


def _build_alias_record(row: dict[str, Any]) -> SemanticFieldAliasRecord:
    """把别名规则行转换成类型化记录。"""
    return SemanticFieldAliasRecord(
        semantic_key=str(row.get("semantic_key") or ""),
        alias=str(row.get("alias") or ""),
        scope_type=_as_optional_text(row.get("scope_type")) or "global",
        scope_value=_as_optional_text(row.get("scope_value")) or "*",
        direction=_as_optional_text(row.get("direction")) or "both",
        location=_as_optional_text(row.get("location")) or "any",
        json_path_pattern=_as_optional_text(row.get("json_path_pattern")),
        source=_as_optional_text(row.get("source")) or "manual",
        confidence=float(row.get("confidence") or 1.0),
        priority=int(row.get("priority") or 100),
        is_active=_as_bool(row.get("is_active"), default=True),
        run_id=_as_optional_text(row.get("run_id")),
        review_status=_as_optional_text(row.get("review_status")),
        current_flag=_as_optional_bool(row.get("current_flag")),
        human_lock=_as_bool(row.get("human_lock"), default=False),
        conflict_streak=int(row.get("conflict_streak") or 0),
    )


def _build_value_map_record(row: dict[str, Any]) -> SemanticFieldValueMapRecord:
    """把值映射行转换成类型化记录。"""
    return SemanticFieldValueMapRecord(
        semantic_key=str(row.get("semantic_key") or ""),
        scope_type=_as_optional_text(row.get("scope_type")) or "global",
        scope_value=_as_optional_text(row.get("scope_value")) or "*",
        standard_code=str(row.get("standard_code") or ""),
        standard_label=str(row.get("standard_label") or ""),
        raw_value=str(row.get("raw_value") or ""),
        raw_label=_as_optional_text(row.get("raw_label")),
        sort_order=int(row.get("sort_order") or 0),
        source=_as_optional_text(row.get("source")) or "manual",
        confidence=float(row.get("confidence") or 1.0),
        is_active=_as_bool(row.get("is_active"), default=True),
        run_id=_as_optional_text(row.get("run_id")),
        review_status=_as_optional_text(row.get("review_status")),
        current_flag=_as_optional_bool(row.get("current_flag")),
        human_lock=_as_bool(row.get("human_lock"), default=False),
        conflict_streak=int(row.get("conflict_streak") or 0),
    )


def _as_optional_text(value: Any) -> str | None:
    """把数据库字段规整成可选文本。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return _as_bool(value)


def _as_bool(value: Any, *, default: bool = False) -> bool:
    """把 MySQL 常见布尔表示统一规整成 bool。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _build_select_sql(
    *,
    table_name: str,
    available_columns: set[str],
    base_columns: list[str],
    cast_json_columns: dict[str, str] | None = None,
) -> str:
    """构建兼容 DDL 演进的查询 SQL。

    功能：
        `semantic_field_*` 三表在不同环境可能还没统一到最新列集。这里按“列存在才查询”的策略
        动态拼 SQL，再叠加统一发布态过滤，确保旧库能跑、新库能用。
    """

    selected_parts: list[str] = []
    for column in base_columns:
        if column in available_columns:
            selected_parts.append(column)
    for json_column, alias in (cast_json_columns or {}).items():
        if json_column in available_columns:
            selected_parts.append(f"CAST({json_column} AS CHAR) AS {alias}")
    if not selected_parts:
        raise ValueError(f"{table_name} 无可读取列，请检查治理表 DDL。")

    where_clauses = []
    if "is_active" in available_columns:
        where_clauses.append("is_active = 1")
    # 这里优先按发布态读“线上生效版本”，避免 resolver 混读草稿/历史规则导致图事实抖动。
    if "current_flag" in available_columns:
        where_clauses.append("current_flag = 1")
    if "review_status" in available_columns:
        where_clauses.append("review_status = 'approved'")
    if not where_clauses:
        where_clauses.append("1 = 1")

    return f"SELECT {', '.join(selected_parts)} FROM {table_name} WHERE {' AND '.join(where_clauses)}"
