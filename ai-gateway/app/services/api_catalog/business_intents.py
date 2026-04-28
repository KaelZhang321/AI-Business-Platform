"""API Query 第二阶段业务意图目录服务。

功能：
    将第二阶段对外暴露的 canonical business intents、历史别名和风险等级判断，
    从代码常量迁移为“业务 MySQL + 进程内快照”模式。

设计意图：
    业务意图已经不只是 Prompt 文案，它同时影响：
    1. Router 白名单
    2. 对外响应契约
    3. 高危写审计判定
    因此它更适合作为治理元数据托管在 MySQL，由网关在启动时预热到内存快照中。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import aiomysql

logger = logging.getLogger(__name__)

NOOP_BUSINESS_INTENT = "none"


@dataclass(frozen=True)
class BusinessIntentDefinition:
    """单个 canonical business intent 定义。"""

    code: str
    name: str
    category: str
    description: str
    risk_level: str = "none"
    enabled: bool = True
    status: str = "active"
    allow_in_router: bool = True
    allow_in_response: bool = True
    sort_order: int = 100
    is_builtin: bool = False


@dataclass(frozen=True)
class BusinessIntentAliasDefinition:
    """历史业务意图编码到 canonical code 的映射定义。"""

    alias_code: str
    canonical_code: str
    risk_level_override: str | None = None
    status: str = "active"


@dataclass(frozen=True)
class BusinessIntentSnapshot:
    """当前进程内可见的业务意图快照。"""

    definitions: dict[str, BusinessIntentDefinition]
    aliases: dict[str, BusinessIntentAliasDefinition] = field(default_factory=dict)


class BusinessIntentCatalogService:
    """业务意图目录服务。

    功能：
        统一从 `ui_business_intents / ui_business_intent_aliases` 读取治理元数据，并暴露：
        1. Router 可用的 allowlist
        2. canonical intent 定义查询
        3. 历史别名到新契约的折叠能力

    Edge Cases:
        - MySQL 不可用、表未建齐或字段不完整时，会保留内置快照兜底
        - 首次加载失败后不再重复击穿数据库，避免每个请求都放大治理库故障
        - 业务库连接池必须由应用级组合根或测试桩注入，目录服务本身不再自建连接
    """

    def __init__(self, *, pool: aiomysql.Pool | None = None) -> None:
        self._snapshot = _build_builtin_snapshot()
        self._pool = pool
        self._load_attempted = False
        self._load_lock = asyncio.Lock()

    async def warmup(self, *, force_refresh: bool = False) -> None:
        """尝试从 MySQL 预热业务意图快照。

        Args:
            force_refresh: 是否忽略已有加载结果并强制重拉。

        Returns:
            无返回值；成功时更新内存快照，失败时保留现有兜底定义。
        """
        if self._load_attempted and not force_refresh:
            return

        async with self._load_lock:
            if self._load_attempted and not force_refresh:
                return

            try:
                intent_definitions = await self._load_intent_definitions()
                alias_definitions = await self._load_alias_definitions()
            except Exception as exc:  # pragma: no cover - 失败路径依赖集成环境
                logger.warning("Business intent catalog load failed, fallback to builtins: %s", exc)
                self._load_attempted = True
                return

            self._snapshot = _merge_snapshot(
                base_snapshot=_build_builtin_snapshot(),
                intent_definitions=intent_definitions,
                alias_definitions=alias_definitions,
            )
            self._load_attempted = True

    def get_definition(self, code: str) -> BusinessIntentDefinition | None:
        """按 canonical code 读取业务意图定义。"""
        return self._snapshot.definitions.get(code)

    def get_allowed_codes(self) -> set[str]:
        """返回 Router 当前允许识别并保留的业务意图编码集合。

        设计意图：
            `none` 是第二阶段最关键的安全回落语义。即便后台误把它配置成禁用，
            网关也必须继续允许它存在，避免路由失败时没有只读降级出口。
        """
        allowed_codes = {
            definition.code
            for definition in self._snapshot.definitions.values()
            if definition.enabled and definition.status == "active" and definition.allow_in_router
        }
        if NOOP_BUSINESS_INTENT in self._snapshot.definitions:
            allowed_codes.add(NOOP_BUSINESS_INTENT)
        return allowed_codes

    def normalize_code(self, raw_code: str | None) -> str:
        """将单个业务意图编码折叠成 canonical code。"""
        normalized = (raw_code or "").strip()
        if not normalized:
            return normalized
        alias_definition = self._snapshot.aliases.get(normalized)
        return alias_definition.canonical_code if alias_definition else normalized

    def get_alias_risk_override(self, raw_code: str | None) -> str | None:
        """读取别名级风险覆盖。

        设计意图：
            高危更新往往会被折叠成通用写意图 `saveToServer`，如果不保留 alias 层风险覆盖，
            审计链路就会错误地把高危写降成普通写。
        """
        normalized = (raw_code or "").strip()
        if not normalized:
            return None
        alias_definition = self._snapshot.aliases.get(normalized)
        if alias_definition is None:
            return None
        risk_level = (alias_definition.risk_level_override or "").strip().lower()
        return risk_level or None

    async def close(self) -> None:
        """目录服务不持有连接池所有权，因此 close 为 no-op。"""

    async def _load_intent_definitions(self) -> dict[str, BusinessIntentDefinition]:
        """从 `ui_business_intents` 读取激活态业务意图。"""
        rows = await self._fetch_mysql_rows(
            """
            SELECT
                code,
                name,
                category,
                description,
                risk_level,
                enabled,
                status,
                allow_in_router,
                allow_in_response,
                sort_order,
                is_builtin
            FROM ui_business_intents
            WHERE status = 'active'
            ORDER BY sort_order, code
            """
        )

        definitions: dict[str, BusinessIntentDefinition] = {}
        for row in rows:
            code = str(row.get("code") or "").strip()
            if not code:
                continue

            definitions[code] = BusinessIntentDefinition(
                code=code,
                name=str(row.get("name") or code).strip(),
                category=_normalize_category(row.get("category")),
                description=str(row.get("description") or code).strip(),
                risk_level=_normalize_risk_level(row.get("risk_level")),
                enabled=bool(row.get("enabled", True)),
                status=str(row.get("status") or "active").strip().lower(),
                allow_in_router=bool(row.get("allow_in_router", True)),
                allow_in_response=bool(row.get("allow_in_response", True)),
                sort_order=int(row.get("sort_order") or 100),
                is_builtin=bool(row.get("is_builtin", False)),
            )
        return definitions

    async def _load_alias_definitions(self) -> dict[str, BusinessIntentAliasDefinition]:
        """从 `ui_business_intent_aliases` 读取激活态别名映射。"""
        rows = await self._fetch_mysql_rows(
            """
            SELECT
                a.alias_code,
                i.code AS canonical_code,
                a.risk_level_override,
                a.status
            FROM ui_business_intent_aliases a
            INNER JOIN ui_business_intents i ON i.id = a.intent_id
            WHERE a.status = 'active'
              AND i.status = 'active'
            ORDER BY a.alias_code
            """
        )

        definitions: dict[str, BusinessIntentAliasDefinition] = {}
        for row in rows:
            alias_code = str(row.get("alias_code") or "").strip()
            canonical_code = str(row.get("canonical_code") or "").strip()
            if not alias_code or not canonical_code:
                continue

            definitions[alias_code] = BusinessIntentAliasDefinition(
                alias_code=alias_code,
                canonical_code=canonical_code,
                risk_level_override=_normalize_optional_risk_level(row.get("risk_level_override")),
                status=str(row.get("status") or "active").strip().lower(),
            )
        return definitions

    async def _fetch_mysql_rows(self, sql: str) -> list[dict[str, object]]:
        """执行治理元数据 SQL，并返回字典行结果。"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def _get_pool(self) -> aiomysql.Pool:
        """读取应用级注入的业务库连接池。"""
        if self._pool is None:
            raise RuntimeError("业务库连接池未注入，请通过 AppResources 或测试桩显式提供。")
        return self._pool


_catalog_service: BusinessIntentCatalogService | None = None


def set_business_intent_catalog_service(service: BusinessIntentCatalogService | None) -> None:
    """替换进程级业务意图目录实例。

    功能：
        应用资源容器通过该入口注入共享业务库连接池，历史调用方继续使用 getter。
    """

    global _catalog_service
    _catalog_service = service


def get_business_intent_catalog_service() -> BusinessIntentCatalogService:
    """获取进程级业务意图目录单例。"""
    global _catalog_service
    if _catalog_service is None:
        raise RuntimeError("BusinessIntentCatalogService 尚未初始化，请先完成 AppResources.start()")
    return _catalog_service


async def close_business_intent_catalog_service() -> None:
    """关闭进程级业务意图目录单例。"""
    global _catalog_service
    if _catalog_service is not None:
        await _catalog_service.close()
        _catalog_service = None


def normalize_business_intent_code(raw_code: str | None) -> str:
    """将单个业务意图编码折叠成 canonical code。

    Args:
        raw_code: LLM、旧 Prompt 或历史 catalog 中出现的原始业务意图编码。

    Returns:
        对外稳定的 canonical business intent code；未知值原样返回，由上层白名单决定是否丢弃。
    """
    return get_business_intent_catalog_service().normalize_code(raw_code)


def normalize_business_intent_codes(raw_codes: list[str]) -> list[str]:
    """将一组业务意图折叠成设计文档约定的稳定集合。

    Args:
        raw_codes: 第二阶段原始业务意图编码列表，可能混入历史别名和旧只读编码。

    Returns:
        只包含 canonical write intents 的去重列表；若没有合法写意图，则返回 `["none"]`。

    Edge Cases:
        - 历史读意图会经 alias 折叠为 `none`
        - 已下线、禁用或不存在的业务意图不会被透传到外部响应
    """
    catalog_service = get_business_intent_catalog_service()
    normalized_codes: list[str] = []
    saw_read_intent = False

    for raw_code in raw_codes:
        canonical_code = catalog_service.normalize_code(raw_code)
        definition = catalog_service.get_definition(canonical_code)
        if definition is None or definition.status != "active" or not definition.enabled:
            continue

        if definition.category == "read":
            saw_read_intent = True
            continue

        if definition.allow_in_response:
            normalized_codes.append(canonical_code)

    if normalized_codes:
        return list(dict.fromkeys(normalized_codes))

    if saw_read_intent:
        return [NOOP_BUSINESS_INTENT]

    noop_definition = catalog_service.get_definition(NOOP_BUSINESS_INTENT)
    return [NOOP_BUSINESS_INTENT] if noop_definition is not None else []


def resolve_business_intent_risk_level(code: str, raw_codes: list[str]) -> str | None:
    """根据 canonical code 与历史别名推导审计风险等级。

    Args:
        code: 已归一化后的 canonical business intent。
        raw_codes: 第二阶段产生的原始业务意图编码列表。

    Returns:
        风险等级字符串；当前至少支持 `high`，也允许未来从治理表扩展出 `low/medium`。
    """
    catalog_service = get_business_intent_catalog_service()
    for raw_code in raw_codes:
        alias_risk_level = catalog_service.get_alias_risk_override(raw_code)
        if alias_risk_level is not None and alias_risk_level != "none":
            return alias_risk_level

    definition = catalog_service.get_definition(code)
    if definition is not None and definition.risk_level != "none":
        return definition.risk_level
    return None


def _build_builtin_snapshot() -> BusinessIntentSnapshot:
    """构造进程级兜底快照。

    设计意图：
        即便业务库表尚未初始化，网关也必须继续维持第二阶段最小稳定契约，
        不能因为治理元数据缺席就把合法写意图全部误判成 `none`。
    """
    definitions = {
        "none": BusinessIntentDefinition(
            code="none",
            name="纯查询",
            category="read",
            description="当前请求仅包含读取诉求，不携带写前确认意图。",
            risk_level="none",
            enabled=True,
            status="active",
            allow_in_router=True,
            allow_in_response=True,
            sort_order=10,
            is_builtin=True,
        ),
        "saveToServer": BusinessIntentDefinition(
            code="saveToServer",
            name="保存业务数据",
            category="write",
            description="用户希望保存、修改或写入业务数据，但不会在 api_query 中直接执行。",
            risk_level="none",
            enabled=True,
            status="active",
            allow_in_router=True,
            allow_in_response=True,
            sort_order=20,
            is_builtin=True,
        ),
        "deleteCustomer": BusinessIntentDefinition(
            code="deleteCustomer",
            name="删除客户数据",
            category="write",
            description="用户希望删除或废弃客户相关记录，但不会在 api_query 中直接执行。",
            risk_level="high",
            enabled=True,
            status="active",
            allow_in_router=True,
            allow_in_response=True,
            sort_order=30,
            is_builtin=True,
        ),
    }
    aliases = {
        "query_business_data": BusinessIntentAliasDefinition(
            alias_code="query_business_data",
            canonical_code="none",
            status="active",
        ),
        "query_detail_data": BusinessIntentAliasDefinition(
            alias_code="query_detail_data",
            canonical_code="none",
            status="active",
        ),
        "prepare_record_update": BusinessIntentAliasDefinition(
            alias_code="prepare_record_update",
            canonical_code="saveToServer",
            status="active",
        ),
        "prepare_high_risk_change": BusinessIntentAliasDefinition(
            alias_code="prepare_high_risk_change",
            canonical_code="saveToServer",
            risk_level_override="high",
            status="active",
        ),
        "update_contract_amount": BusinessIntentAliasDefinition(
            alias_code="update_contract_amount",
            canonical_code="saveToServer",
            risk_level_override="high",
            status="active",
        ),
        "delete_customer_record": BusinessIntentAliasDefinition(
            alias_code="delete_customer_record",
            canonical_code="deleteCustomer",
            risk_level_override="high",
            status="active",
        ),
    }
    return BusinessIntentSnapshot(definitions=definitions, aliases=aliases)


def _merge_snapshot(
    *,
    base_snapshot: BusinessIntentSnapshot,
    intent_definitions: dict[str, BusinessIntentDefinition],
    alias_definitions: dict[str, BusinessIntentAliasDefinition],
) -> BusinessIntentSnapshot:
    """用 MySQL 元数据覆盖内置兜底快照。"""
    merged_definitions = dict(base_snapshot.definitions)
    merged_definitions.update(intent_definitions)

    merged_aliases = dict(base_snapshot.aliases)
    # 只有当目标 canonical code 真实存在时，才允许 alias 进入快照，避免挂出悬空映射。
    for alias_code, alias_definition in alias_definitions.items():
        if alias_definition.canonical_code in merged_definitions:
            merged_aliases[alias_code] = alias_definition

    return BusinessIntentSnapshot(definitions=merged_definitions, aliases=merged_aliases)


def _normalize_category(value: object) -> str:
    """收敛业务意图分类，非法值回退到 `read`。"""
    normalized = str(value or "read").strip().lower()
    return normalized if normalized in {"read", "write"} else "read"


def _normalize_risk_level(value: object) -> str:
    """收敛风险等级，空值统一视为 `none`。"""
    normalized = str(value or "none").strip().lower()
    return normalized or "none"


def _normalize_optional_risk_level(value: object) -> str | None:
    """收敛可选风险等级；空值返回 `None`。"""
    normalized = str(value or "").strip().lower()
    return normalized or None
