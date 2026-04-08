from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

import aiomysql

from app.core.config import settings
from app.models.schemas import ApiQueryUIAction

logger = logging.getLogger(__name__)

_QUERY_DEFAULT_COMPONENT_CODES = [
    "PlannerCard",
    "PlannerMetric",
    "PlannerTable",
    "PlannerDetailCard",
    "PlannerForm",
    "PlannerInput",
    "PlannerSelect",
    "PlannerButton",
    "PlannerNotice",
]
_GENERIC_DEFAULT_COMPONENT_CODES = [
    "Card",
    "Table",
    "Metric",
    "List",
    "Form",
    "Tag",
    "Chart",
]
_FALLBACK_COMPONENT_DESCRIPTION = "运行时组件已被引用，但目录中暂无详细说明。"
_FALLBACK_ACTION_DESCRIPTION = "运行时动作已被引用，但目录中暂无详细说明。"


@dataclass(frozen=True)
class UIComponentDefinition:
    """单个 UI 组件的目录定义。"""

    code: str
    name: str
    description: str
    props_schema: dict[str, Any] = field(default_factory=dict)
    is_container: bool = False
    status: str = "active"


@dataclass(frozen=True)
class UIActionDefinition:
    """单个前端动作的目录定义。"""

    code: str
    name: str
    description: str
    params_schema: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    status: str = "active"


@dataclass(frozen=True)
class UICatalogSnapshot:
    """当前进程内可见的 UI 目录快照。"""

    components: dict[str, UIComponentDefinition]
    actions: dict[str, UIActionDefinition]
    template_scenarios: list[dict[str, Any]]


class UICatalogService:
    """集中管理 Renderer 与 `api_query` 共享的 UI 目录。

    功能：
        把过去散落在路由层和渲染层的组件/动作硬编码收口到一个服务中，并提供：
        1. 进程内快照缓存，避免每次请求都访问 MySQL
        2. `ui_components / ui_actions` 的直连读取能力
        3. MySQL 不可用时的内置兜底，保证主链路不因治理元数据缺席而中断

    Edge Cases:
        - MySQL 不可达、表未创建或字段为脏 JSON 时，自动回退到内置目录
        - 只读取一次失败结果，避免每个请求都重复击穿数据库并刷日志
        - 目录中不存在的运行时引用仍会返回占位说明，防止 Prompt 侧静默丢失约束
    """

    def __init__(self) -> None:
        self._snapshot = _build_builtin_snapshot()
        self._pool: aiomysql.Pool | None = None
        self._load_attempted = False
        self._load_lock = asyncio.Lock()

    async def warmup(self, *, force_refresh: bool = False) -> None:
        """尝试从 MySQL 预热 UI 目录快照。

        Args:
            force_refresh: 是否忽略已有加载结果并强制重拉。适合未来接入失效通知后使用。

        Returns:
            无返回值；成功时更新进程内快照，失败时保留现有兜底目录。

        Edge Cases:
            - 首次加载失败后会保留内置目录，避免把 `runtime-metadata` 也拖成 500
            - 并发请求通过异步锁串行化，防止多个协程重复建连接池和打同一批 SQL
        """
        if self._load_attempted and not force_refresh:
            return

        async with self._load_lock:
            if self._load_attempted and not force_refresh:
                return

            try:
                component_definitions = await self._load_component_definitions()
                action_definitions = await self._load_action_definitions()
            except Exception as exc:  # pragma: no cover - 失败路径由集成测试间接覆盖
                logger.warning("UI catalog load failed, fallback to builtins: %s", exc)
                self._load_attempted = True
                return

            self._snapshot = _merge_snapshot(
                base_snapshot=_build_builtin_snapshot(),
                component_definitions=component_definitions,
                action_definitions=action_definitions,
            )
            self._load_attempted = True

    def get_component_codes(
        self,
        *,
        intent: str | None = None,
        requested_codes: Sequence[str] | None = None,
    ) -> list[str]:
        """返回当前场景可见的组件编码列表。

        Args:
            intent: 当前渲染意图。`query` 使用 `Planner*` 默认目录，其余链路维持旧泛化目录。
            requested_codes: 调用方已知的目标组件列表。传入后优先保留这个顺序。

        Returns:
            组件编码有序列表，适合作为前端 `ui_runtime.components` 或 Renderer Prompt 输入。
        """
        if requested_codes:
            return _dedupe_codes(requested_codes)
        if intent == "query":
            return list(_QUERY_DEFAULT_COMPONENT_CODES)
        return list(_GENERIC_DEFAULT_COMPONENT_CODES)

    def get_component_catalog(
        self,
        *,
        intent: str | None = None,
        requested_codes: Sequence[str] | None = None,
    ) -> dict[str, str]:
        """返回当前场景的组件说明目录。

        功能：
            Renderer Prompt 需要“受控组件说明”，而不是原始 SQL 行。这里统一把快照转换成
            `code -> description` 的轻量映射，减少 Prompt 拼装逻辑在多个模块间散落。
        """
        catalog: dict[str, str] = {}
        for code in self.get_component_codes(intent=intent, requested_codes=requested_codes):
            definition = self._snapshot.components.get(code)
            catalog[code] = definition.description if definition else _FALLBACK_COMPONENT_DESCRIPTION
        return catalog

    def build_runtime_actions(self, action_codes: set[str] | None = None) -> list[ApiQueryUIAction]:
        """构造前端运行时动作定义。

        Args:
            action_codes: 本次请求真正允许暴露的动作编码集合。为空时返回完整目录及默认启用态。

        Returns:
            适配 `ApiQueryUIAction` 的动作定义数组。

        Edge Cases:
            - 当调用方只给出部分动作时，未命中的动作不会下发，避免前端误以为可调用
            - 运行时引用到未注册动作时，仍会补一个占位定义，保证诊断链路可见
        """
        definitions = self._snapshot.actions
        ordered_codes = (
            list(definitions.keys())
            if action_codes is None
            else [code for code in definitions.keys() if code in action_codes]
        )

        if action_codes is not None:
            for code in sorted(action_codes):
                if code not in definitions and code not in ordered_codes:
                    ordered_codes.append(code)

        actions: list[ApiQueryUIAction] = []
        for code in ordered_codes:
            definition = definitions.get(code)
            if definition is None:
                actions.append(
                    ApiQueryUIAction(
                        code=code,
                        description=_FALLBACK_ACTION_DESCRIPTION,
                        enabled=True,
                        params_schema={},
                    )
                )
                continue

            actions.append(
                ApiQueryUIAction(
                    code=definition.code,
                    description=definition.description,
                    enabled=definition.enabled if action_codes is None else definition.code in action_codes,
                    params_schema=dict(definition.params_schema),
                )
            )
        return actions

    def get_all_action_codes(self) -> set[str]:
        """返回当前目录中的全部动作编码。

        功能：
            第五阶段回填 `ui_runtime` 时，需要把最终 Spec 中出现的动作识别出来。这里统一
            暴露动作全集，避免路由层再维护一份手写白名单。
        """
        return set(self._snapshot.actions.keys())

    def get_all_component_codes(self) -> set[str]:
        """返回当前目录中的全部组件编码。

        功能：
            渲染安全校验不能只依赖当前 runtime 的局部视图，还需要知道“系统真正认识哪些组件”，
            这样才能把“组件未注册”和“组件未在当前运行时启用”区分开来。
        """
        return set(self._snapshot.components.keys())

    def get_action_definition(self, code: str) -> UIActionDefinition | None:
        """按动作编码读取目录定义。

        功能：
            `UI Spec Guard` 需要根据动作目录读取 `params_schema.required`，
            这里统一暴露查询入口，避免外部直接窥探内部快照结构。
        """
        return self._snapshot.actions.get(code)

    def get_template_scenarios(self) -> list[dict[str, Any]]:
        """返回 `runtime-metadata` 对外暴露的模板场景说明。"""
        return [dict(item) for item in self._snapshot.template_scenarios]

    async def close(self) -> None:
        """释放内部连接池。

        功能：
            当前服务通常以进程级单例形式存在。预留 `close` 是为了后续接入应用关闭钩子时，
            避免热重载或测试进程留下悬挂的 MySQL 连接。
        """
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def _load_component_definitions(self) -> dict[str, UIComponentDefinition]:
        """从 `ui_components` 读取活跃组件定义。"""
        rows = await self._fetch_mysql_rows(
            """
            SELECT
                code,
                name,
                description,
                props_schema,
                is_container,
                status
            FROM ui_components
            WHERE status = 'active'
            ORDER BY code
            """
        )

        definitions: dict[str, UIComponentDefinition] = {}
        for row in rows:
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            definitions[code] = UIComponentDefinition(
                code=code,
                name=str(row.get("name") or code).strip(),
                description=str(row.get("description") or code).strip(),
                props_schema=_coerce_json_object(row.get("props_schema")),
                is_container=bool(row.get("is_container")),
                status=str(row.get("status") or "active").strip().lower(),
            )
        return definitions

    async def _load_action_definitions(self) -> dict[str, UIActionDefinition]:
        """从 `ui_actions` 读取活跃动作定义。"""
        rows = await self._fetch_mysql_rows(
            """
            SELECT
                code,
                name,
                description,
                params_schema,
                status
            FROM ui_actions
            WHERE status = 'active'
            ORDER BY code
            """
        )

        definitions: dict[str, UIActionDefinition] = {}
        for row in rows:
            code = str(row.get("code") or "").strip()
            if not code:
                continue

            builtin_definition = self._snapshot.actions.get(code)
            definitions[code] = UIActionDefinition(
                code=code,
                name=str(row.get("name") or code).strip(),
                description=str(row.get("description") or code).strip(),
                params_schema=_coerce_json_object(row.get("params_schema")),
                # MySQL 目录表只负责声明能力，不负责请求级启用态，因此默认启用态沿用内置策略。
                enabled=builtin_definition.enabled if builtin_definition else True,
                status=str(row.get("status") or "active").strip().lower(),
            )
        return definitions

    async def _fetch_mysql_rows(self, sql: str) -> list[dict[str, Any]]:
        """执行元数据 SQL 并返回字典行。

        功能：
            UI 目录和 API Catalog 共享同一组 `BUSINESS_MYSQL_*` 配置，这里复用相同连接参数，
            让治理元数据与接口目录能够被同一套部署参数驱动。
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def _get_pool(self) -> aiomysql.Pool:
        """懒加载内部 MySQL 连接池。"""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=3,
                host=settings.business_mysql_host,
                port=settings.business_mysql_port,
                user=settings.business_mysql_user,
                password=settings.business_mysql_password,
                db=settings.business_mysql_database,
                charset="utf8mb4",
            )
        return self._pool


def _build_builtin_snapshot() -> UICatalogSnapshot:
    """构造进程级兜底目录。

    功能：
        企业级方案的治理元数据最终应该由 MySQL 托管，但在迁移未完成、表未建齐或本地
        开发环境缺库时，网关仍必须能返回稳定契约。这份快照就是安全气囊。
    """
    components = {
        "PlannerCard": UIComponentDefinition(
            code="PlannerCard",
            name="规划卡片",
            description="顶级卡片容器，props: title, subtitle",
            is_container=True,
        ),
        "PlannerTable": UIComponentDefinition(
            code="PlannerTable",
            name="规划表格",
            description="同质列表展示，props: columns, dataSource",
        ),
        "PlannerMetric": UIComponentDefinition(
            code="PlannerMetric",
            name="规划指标",
            description="只读指标展示，props: label, value",
        ),
        "PlannerDetailCard": UIComponentDefinition(
            code="PlannerDetailCard",
            name="详情卡片",
            description="单对象详情展示，props: title, items",
        ),
        "PlannerForm": UIComponentDefinition(
            code="PlannerForm",
            name="规划表单",
            description="表单容器，负责组织可编辑字段",
            is_container=True,
        ),
        "PlannerInput": UIComponentDefinition(
            code="PlannerInput",
            name="规划输入框",
            description="文本输入组件，props: label, value, placeholder",
        ),
        "PlannerSelect": UIComponentDefinition(
            code="PlannerSelect",
            name="规划下拉框",
            description="单选下拉组件，props: label, value, options",
        ),
        "PlannerButton": UIComponentDefinition(
            code="PlannerButton",
            name="规划按钮",
            description="触发动作的按钮组件，props: label",
        ),
        "PlannerNotice": UIComponentDefinition(
            code="PlannerNotice",
            name="状态提示",
            description="状态提示条，props: text, tone(info/success)",
        ),
        "Card": UIComponentDefinition(
            code="Card",
            name="通用卡片",
            description="通用容器卡片，props: title, subtitle, actions",
            is_container=True,
        ),
        "Table": UIComponentDefinition(
            code="Table",
            name="通用表格",
            description="通用表格，props: columns, dataSource, rowKey",
        ),
        "Metric": UIComponentDefinition(
            code="Metric",
            name="指标卡",
            description="指标展示，props: label, value, trend",
        ),
        "List": UIComponentDefinition(
            code="List",
            name="通用列表",
            description="列表展示，props: title, items, emptyText",
        ),
        "Form": UIComponentDefinition(
            code="Form",
            name="通用表单",
            description="表单容器，props: fields, submitLabel",
            is_container=True,
        ),
        "Tag": UIComponentDefinition(
            code="Tag",
            name="标签",
            description="标签展示，props: label, color",
        ),
        "Chart": UIComponentDefinition(
            code="Chart",
            name="图表",
            description="图表容器，props: option",
        ),
    }
    actions = {
        "view_detail": UIActionDefinition(
            code="view_detail",
            name="查看详情",
            description="查看当前结果详情",
            params_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                },
                "required": ["id"],
            },
        ),
        "refresh": UIActionDefinition(
            code="refresh",
            name="刷新查询",
            description="重新发起当前查询",
            params_schema={"type": "object", "properties": {}},
        ),
        "export": UIActionDefinition(
            code="export",
            name="导出结果",
            description="导出当前查询结果",
            params_schema={"type": "object", "properties": {}},
        ),
        "trigger_task": UIActionDefinition(
            code="trigger_task",
            name="触发任务",
            description="触发任务型操作",
            params_schema={"type": "object", "properties": {}},
        ),
        "remoteQuery": UIActionDefinition(
            code="remoteQuery",
            name="远程只读查询",
            description="用于详情拉取或分页刷新的通用查询动作",
            enabled=False,
            params_schema={
                "type": "object",
                "properties": {
                    "api_id": {"type": "string"},
                    "route_url": {"type": "string"},
                    "params": {"type": "object"},
                    "mutation_target": {"type": "string"},
                },
                "required": ["api_id"],
            },
        ),
        "remoteMutation": UIActionDefinition(
            code="remoteMutation",
            name="远程写入",
            description="用于确认式写入的通用动作，仅保留契约，不在 api_query 中执行",
            enabled=False,
            params_schema={
                "type": "object",
                "properties": {
                    "api_id": {"type": "string"},
                    "payload": {"type": "object"},
                    "snapshot_id": {"type": "string"},
                },
                "required": ["api_id", "payload"],
            },
        ),
    }
    template_scenarios = [
        {
            "code": "list_detail_template",
            "description": "列表 + 详情页模板快路，命中模板时可直接落到固定详情 Spec。",
            "enabled": False,
        },
        {
            "code": "pagination_patch",
            "description": "分页场景的数据数组局部刷新契约。",
            "enabled": False,
        },
        {
            "code": "wysiwyg_audit",
            "description": "高危写场景的 UI 快照审计契约。",
            "enabled": False,
        },
    ]
    return UICatalogSnapshot(
        components=components,
        actions=actions,
        template_scenarios=template_scenarios,
    )


def _merge_snapshot(
    *,
    base_snapshot: UICatalogSnapshot,
    component_definitions: dict[str, UIComponentDefinition],
    action_definitions: dict[str, UIActionDefinition],
) -> UICatalogSnapshot:
    """把 MySQL 目录覆盖到内置兜底快照上。

    功能：
        这样做的关键不是“把内置配置删掉”，而是确保治理元数据分批迁移时不会出现
        半张目录表把整个 Prompt 或运行时契约打残的问题。
    """
    merged_components = dict(base_snapshot.components)
    merged_components.update(component_definitions)
    merged_actions = dict(base_snapshot.actions)
    merged_actions.update(action_definitions)
    return UICatalogSnapshot(
        components=merged_components,
        actions=merged_actions,
        template_scenarios=[dict(item) for item in base_snapshot.template_scenarios],
    )


def _coerce_json_object(value: Any) -> dict[str, Any]:
    """把 MySQL JSON 字段稳定转换成对象。

    功能：
        MySQL 驱动在不同环境下可能返回 Python 字典，也可能返回字符串。
        这里统一收口成对象，避免上游代码为了兼容连接器差异到处写类型分支。
    """
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON payload found in UI catalog metadata: %s", value[:120])
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _dedupe_codes(codes: Sequence[str]) -> list[str]:
    """按原始顺序对编码列表去重。"""
    ordered_codes: list[str] = []
    for code in codes:
        normalized = str(code).strip()
        if not normalized or normalized in ordered_codes:
            continue
        ordered_codes.append(normalized)
    return ordered_codes
