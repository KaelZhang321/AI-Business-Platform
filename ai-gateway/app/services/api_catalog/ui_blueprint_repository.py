"""UI 分区字典仓储。

功能：
    从 `ui_blueprint_dict` 读取“展示域 + 展示分区 + 典型字段”规则，供字段治理提案阶段
    统一落位 `display_domain_code/display_section_code`，避免分区编码在代码里硬编码漂移。
"""

from __future__ import annotations

import json
from typing import Any

import aiomysql

from app.core.config import settings
from app.core.mysql import build_business_mysql_conn_params
from app.services.api_catalog.semantic_governance_proposal_models import (
    UiBlueprintSectionRule,
    UiBlueprintSnapshot,
)

_TABLE_UI_BLUEPRINT = "ui_blueprint_dict"


class UiBlueprintRepositoryError(RuntimeError):
    """UI 分区字典仓储异常。"""


class UiBlueprintRepository:
    """UI 分区字典仓储。

    功能：
        以“列能力探测 + 运行时映射”的方式兼容不同阶段 DDL，避免因为字段命名差异导致治理任务
        直接失败。
    """

    def __init__(self) -> None:
        self._pool: aiomysql.Pool | None = None
        self._columns_cache: set[str] | None = None
        self._table_exists_cache: bool | None = None

    async def load_snapshot(self) -> UiBlueprintSnapshot:
        """加载 UI 分区规则快照。

        Returns:
            `UiBlueprintSnapshot`；当表不存在或无有效数据时返回空快照。
        """

        table_exists = await self._table_exists()
        if not table_exists:
            return UiBlueprintSnapshot()

        columns = await self._get_columns()
        select_columns = _build_select_columns(columns)
        where_clause = "WHERE is_active = 1" if "is_active" in columns else ""
        order_clause = _build_order_clause(columns)
        sql = f"SELECT {', '.join(select_columns)} FROM {_TABLE_UI_BLUEPRINT} {where_clause} {order_clause}".strip()

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql)
                    rows = await cursor.fetchall()
        except Exception as exc:
            raise UiBlueprintRepositoryError(f"读取 ui_blueprint_dict 失败: {exc}") from exc

        rules: list[UiBlueprintSectionRule] = []
        for raw_row in rows:
            row = dict(raw_row)
            rule = _build_rule_from_row(row)
            if rule is None:
                continue
            rules.append(rule)
        return UiBlueprintSnapshot(rules=rules)

    async def close(self) -> None:
        """关闭连接池。"""

        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def _table_exists(self) -> bool:
        if self._table_exists_cache is not None:
            return self._table_exists_cache

        query = """
SELECT 1
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
LIMIT 1
"""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, (settings.business_mysql_database, _TABLE_UI_BLUEPRINT))
                    row = await cursor.fetchone()
        except Exception as exc:
            raise UiBlueprintRepositoryError(f"探测 ui_blueprint_dict 是否存在失败: {exc}") from exc
        self._table_exists_cache = row is not None
        return self._table_exists_cache

    async def _get_columns(self) -> set[str]:
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
                    await cursor.execute(query, (settings.business_mysql_database, _TABLE_UI_BLUEPRINT))
                    rows = await cursor.fetchall()
        except Exception as exc:
            raise UiBlueprintRepositoryError(f"读取 ui_blueprint_dict 列结构失败: {exc}") from exc

        self._columns_cache = {str(row.get("COLUMN_NAME") or "").strip() for row in rows}
        return self._columns_cache

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=2,
                **build_business_mysql_conn_params(),
            )
        return self._pool


def _build_select_columns(columns: set[str]) -> list[str]:
    selected = []
    for candidate in [
        "id",
        "display_domain_code",
        "display_domain_label",
        "display_section_code",
        "display_section_label",
        "domain_code",
        "domain_label",
        "section_code",
        "section_label",
        "typical_fields",
        "priority",
        "sort_order",
        "is_active",
    ]:
        if candidate in columns:
            selected.append(candidate)
    if not selected:
        selected = ["1 as placeholder"]
    return selected


def _build_order_clause(columns: set[str]) -> str:
    order_fields = []
    if "priority" in columns:
        order_fields.append("priority ASC")
    if "sort_order" in columns:
        order_fields.append("sort_order ASC")
    if "id" in columns:
        order_fields.append("id ASC")
    if not order_fields:
        return ""
    return f"ORDER BY {', '.join(order_fields)}"


def _build_rule_from_row(row: dict[str, Any]) -> UiBlueprintSectionRule | None:
    domain_code = _pick_text(row, "display_domain_code", "domain_code")
    section_code = _pick_text(row, "display_section_code", "section_code")
    if not domain_code or not section_code:
        return None
    domain_label = _pick_text(row, "display_domain_label", "domain_label")
    section_label = _pick_text(row, "display_section_label", "section_label")
    typical_fields = _parse_typical_fields(row.get("typical_fields"))
    priority = _to_int(row.get("priority"))
    if priority is None:
        priority = _to_int(row.get("sort_order")) or 100
    is_active = _to_bool(row.get("is_active"), default=True)
    return UiBlueprintSectionRule(
        display_domain_code=domain_code,
        display_domain_label=domain_label,
        display_section_code=section_code,
        display_section_label=section_label,
        typical_fields=typical_fields,
        priority=priority,
        is_active=is_active,
    )


def _pick_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _parse_typical_fields(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    # 兼容两类配置：JSON 数组（推荐）与逗号分隔字符串（历史）。
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
    return [item.strip() for item in text.replace("，", ",").split(",") if item.strip()]


def _to_bool(value: Any, *, default: bool) -> bool:
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


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None

