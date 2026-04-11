"""字段治理三表仓储。

功能：
    统一从业务 MySQL 读取 `semantic_field_dict / semantic_field_alias / semantic_field_value_map`，
    并把它们转换成 GraphRAG 可直接消费的治理快照。
"""

from __future__ import annotations

import json
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

logger = logging.getLogger(__name__)

_FIELD_DICT_SQL = """
SELECT
    semantic_key,
    standard_key,
    entity_code,
    canonical_name,
    label,
    field_type,
    value_type,
    category,
    business_domain,
    display_domain_code,
    display_domain_label,
    display_section_code,
    display_section_label,
    graph_role,
    is_identifier,
    is_graph_enabled,
    CAST(value_schema AS CHAR) AS valueSchema,
    description,
    is_active
FROM semantic_field_dict
WHERE is_active = 1
"""

_FIELD_ALIAS_SQL = """
SELECT
    semantic_key,
    alias,
    scope_type,
    scope_value,
    direction,
    location,
    json_path_pattern,
    source,
    confidence,
    priority,
    is_active
FROM semantic_field_alias
WHERE is_active = 1
"""

_FIELD_VALUE_MAP_SQL = """
SELECT
    semantic_key,
    scope_type,
    scope_value,
    standard_code,
    standard_label,
    raw_value,
    raw_label,
    sort_order,
    source,
    confidence,
    is_active
FROM semantic_field_value_map
WHERE is_active = 1
"""


class SemanticFieldRepositoryError(RuntimeError):
    """字段治理仓储异常。"""


class SemanticFieldRepository:
    """字段治理仓储。

    功能：
        把治理三表装载成一次只读快照，供 resolver 在同一轮解析里复用。

    Edge Cases:
        - JSON 字段统一 `CAST(... AS CHAR)` 后再解析，避免不同驱动返回 `bytes/dict/str` 混杂
    """

    def __init__(self) -> None:
        self._pool: aiomysql.Pool | None = None

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
                await cursor.execute(_FIELD_DICT_SQL)
                field_dict_rows = [dict(row) for row in await cursor.fetchall()]
                await cursor.execute(_FIELD_ALIAS_SQL)
                alias_rows = [dict(row) for row in await cursor.fetchall()]
                await cursor.execute(_FIELD_VALUE_MAP_SQL)
                value_map_rows = [dict(row) for row in await cursor.fetchall()]
                return field_dict_rows, alias_rows, value_map_rows

    async def _get_pool(self) -> aiomysql.Pool:
        """懒加载业务 MySQL 连接池。"""
        if self._pool is None:
            logger.info(
                "Connecting semantic field repository host=%s port=%s db=%s timeout=%ss",
                settings.business_mysql_host,
                settings.business_mysql_port,
                settings.business_mysql_database,
                settings.api_catalog_mysql_connect_timeout_seconds,
            )
            self._pool = await aiomysql.create_pool(minsize=1, maxsize=3, **_build_business_mysql_conn_params())
        return self._pool

    async def close(self) -> None:
        """释放连接池。"""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None


def _build_business_mysql_conn_params() -> dict[str, str | int | float]:
    """复用业务 MySQL 配置构造治理仓储连接参数。"""
    return {
        "host": settings.business_mysql_host,
        "port": settings.business_mysql_port,
        "user": settings.business_mysql_user,
        "password": settings.business_mysql_password,
        "db": settings.business_mysql_database,
        "charset": "utf8mb4",
        "connect_timeout": settings.api_catalog_mysql_connect_timeout_seconds,
    }


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
        value_schema=_safe_json_loads(row.get("valueSchema")),
        description=_as_optional_text(row.get("description")),
        is_active=_as_bool(row.get("is_active"), default=True),
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
    )


def _as_optional_text(value: Any) -> str | None:
    """把数据库字段规整成可选文本。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _safe_json_loads(value: Any) -> dict[str, Any] | None:
    """安全解析治理表里的 JSON 字段。"""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None

