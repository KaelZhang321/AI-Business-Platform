from __future__ import annotations

import logging
import re
from statistics import mean
from typing import Any

from app.core.config import settings
from app.models.schemas import ApiQueryExecutionStatus, ApiQueryUIRuntime, KnowledgeResult

logger = logging.getLogger(__name__)


class DynamicUIService:
    """根据意图构建 json-render 兼容的 UI Spec。

    支持两种模式：
    - 规则模式（默认）：基于硬编码模板，根据数据特征自动生成 UI Spec
    - LLM 模式（实验性）：通过 LLM 生成 UI Spec，需设置 LLM_UI_SPEC_ENABLED=true
    """

    async def generate_ui_spec(
        self,
        intent: str,
        data: Any,
        context: dict | None = None,
        *,
        status: ApiQueryExecutionStatus | str | None = None,
        runtime: ApiQueryUIRuntime | None = None,
    ) -> dict[str, Any] | None:
        """按执行状态和数据形状生成 json-render 规范。

        功能：
            将 `api_query` 的执行状态机翻译为可渲染的 UI 结果，避免前端直接暴露
            上游报错、空结果或网关跳过执行等底层细节。

        Args:
            intent: 当前 UI 生成意图，例如 `query`、`knowledge`。
            data: 已经过网关裁剪后的渲染数据。
            context: 渲染上下文，至少可包含 `user_query`、`context_pool`、提示文案等。
            status: 当前主步骤的执行状态。
            runtime: 当前查询可用的前端运行时能力定义。

        Returns:
            合法的 json-render Spec；若当前场景不适合生成 UI，则返回 `None`。

        Edge Cases:
            - `ERROR` / `EMPTY` / `SKIPPED` 优先返回 Notice，防止前端误渲染半成品表格
            - `PARTIAL_SUCCESS` 会在正常内容上叠加风险提示，而不是直接吞掉成功数据
            - 旧版规则渲染器仍会先产出树形节点，本方法负责在出口统一折叠为
              `root/state/elements`，避免 route 层同时兼容两套 Spec 契约
        """
        execution_status = ApiQueryExecutionStatus(status) if status else None

        if execution_status == ApiQueryExecutionStatus.ERROR:
            return self._notice_spec(
                title=(context or {}).get("title", "查询失败"),
                message=(context or {}).get("error", "业务接口调用失败"),
                tone="info",
            )
        if execution_status == ApiQueryExecutionStatus.EMPTY:
            return self._notice_spec(
                title=(context or {}).get("title", "暂无数据"),
                message=(context or {}).get("empty_message", "未查到符合条件的数据"),
                tone="info",
            )
        if execution_status == ApiQueryExecutionStatus.SKIPPED:
            return self._notice_spec(
                title=(context or {}).get("title", "查询已跳过"),
                message=(context or {}).get("skip_message", "由于缺少必要条件，当前查询未被执行。"),
                tone="info",
            )
        if not data:
            return None

        # 规则模式是当前生产兜底，LLM 只是在满足开关时尝试提升展示质量。
        if settings.llm_ui_spec_enabled:
            try:
                spec = await self._llm_generate_spec(intent, data, context)
                if spec:
                    normalized_spec = self._normalize_spec_shape(spec)
                    if normalized_spec:
                        return normalized_spec
            except Exception as exc:
                logger.warning("LLM UI Spec 生成失败，回退规则模式: %s", exc)

        # 规则模式（默认）
        if intent == "knowledge" and isinstance(data, list):
            return self._normalize_spec_shape(self._knowledge_spec(data, context))

        if intent == "query" and isinstance(data, list) and data and isinstance(data[0], dict):
            return self._query_spec(
                data,
                context,
                runtime,
                include_partial_notice=execution_status == ApiQueryExecutionStatus.PARTIAL_SUCCESS,
            )

        if intent == "task" and isinstance(data, list):
            return self._normalize_spec_shape(self._task_spec(data))

        return None

    def _get_llm_service(self):
        """懒加载 LLMService 单例，避免规则模式也承担额外初始化成本。"""
        if not hasattr(self, "_llm_service") or self._llm_service is None:
            from app.services.llm_service import LLMService
            self._llm_service = LLMService()
        return self._llm_service

    async def _llm_generate_spec(self, intent: str, data: Any, context: dict | None) -> dict[str, Any] | None:
        """通过 LLM 生成 UI Spec（实验性）。

        将数据摘要和意图发送给 LLM，要求返回 json-render 兼容的 JSON Spec。
        支持的组件类型：Card / Table / Metric / List / Form / Tag / Chart。

        返回 None 表示 LLM 未生成有效 Spec，调用方应回退到规则模式。
        """
        import json as _json

        llm = self._get_llm_service()

        # 构造数据摘要（避免发送完整数据给 LLM）
        if isinstance(data, list):
            sample = data[:3]
            data_summary = f"共 {len(data)} 条记录，前3条样例：{_json.dumps(sample, ensure_ascii=False, default=str)[:800]}"
        else:
            data_summary = str(data)[:500]

        prompt = (
            "你是一个 UI 生成器。根据以下信息生成一个 json-render 兼容的 JSON UI Spec。\n"
            f"意图：{intent}\n"
            f"上下文：{_json.dumps(context or {}, ensure_ascii=False)}\n"
            f"数据摘要：{data_summary}\n\n"
            "可用组件类型：Card, Table, Metric, List, Form, Tag, Chart。\n"
            "Chart 的 option 遵循 ECharts 格式，支持 bar/line/pie 类型。\n"
            "请直接返回 JSON，不要包含 markdown 代码块或解释文字。"
        )

        reply = await llm.chat(messages=[{"role": "user", "content": prompt}])
        if not reply:
            return None

        # 尝试从 LLM 回复中提取 JSON
        cleaned = reply.strip()
        if cleaned.startswith("```"):
            # 移除 markdown 代码块
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            spec = _json.loads(cleaned)
            if isinstance(spec, dict) and (
                "type" in spec
                or (
                    isinstance(spec.get("root"), str)
                    and isinstance(spec.get("elements"), dict)
                )
            ):
                return spec
        except _json.JSONDecodeError:
            logger.debug("LLM 返回的 UI Spec 不是有效 JSON: %s", cleaned[:200])

        return None

    def _normalize_spec_shape(self, spec: dict[str, Any] | None) -> dict[str, Any] | None:
        """将第五阶段输出统一折叠为 flat spec。

        功能：
            当前 `ai-gateway` 正处于旧树形 Spec 向 `root/state/elements` 过渡的阶段。
            这里把所有出口统一成 flat spec，目的是让 route 层、测试和后续 `json-render`
            主链只消费一套结构，而不是继续在边界层维护双协议。

        Args:
            spec: 规则模式或 LLM 模式生成的原始 Spec。

        Returns:
            标准化后的 flat spec；若输入无法识别，则返回 `None`。

        Edge Cases:
            - 已经是 flat spec 时只补齐空 `state`
            - 旧树形 Spec 会被稳定转换，元素 ID 使用确定性命名，便于测试断言和快照比对
        """
        if not isinstance(spec, dict):
            return None

        if self._is_flat_spec(spec):
            state = spec.get("state")
            return {
                **spec,
                "state": state if isinstance(state, dict) else {},
            }

        if "type" not in spec:
            return None

        return self._legacy_tree_to_flat_spec(spec)

    @staticmethod
    def _is_flat_spec(spec: dict[str, Any]) -> bool:
        """判断当前 Spec 是否已经符合 `root/state/elements` 契约。"""
        return isinstance(spec.get("root"), str) and isinstance(spec.get("elements"), dict)

    def _legacy_tree_to_flat_spec(self, root_node: dict[str, Any]) -> dict[str, Any]:
        """把旧树形 UI 结构转换成 flat spec。

        功能：
            任务 1 的目标是“先统一契约，再继续演进组件语义”。因此这里不重写现有规则
            渲染逻辑，而是在出口做一次结构归一化，让旧实现也能立刻进入新协议。

        Args:
            root_node: 旧版 `type/props/children` 根节点。

        Returns:
            `root/state/elements` 形态的 flat spec。

        Edge Cases:
            - 仅递归转换真正的子组件树，不会错误下钻到 `props.actions` 这类配置数组
            - 子元素 ID 采用确定性前缀 + 递增序号，避免每次生成随机 ID 造成测试抖动
        """
        element_counter = 0
        elements: dict[str, Any] = {}

        def next_element_id(node_type: Any) -> str:
            nonlocal element_counter
            element_counter += 1
            prefix = self._build_element_id_prefix(node_type)
            return f"{prefix}_{element_counter}"

        def materialize(node: dict[str, Any], *, element_id: str) -> None:
            element_payload = {
                key: value
                for key, value in node.items()
                if key != "children"
            }
            raw_children = node.get("children")
            child_ids: list[str] = []

            if isinstance(raw_children, list):
                for child in raw_children:
                    if not isinstance(child, dict) or "type" not in child:
                        continue
                    child_id = next_element_id(child.get("type"))
                    child_ids.append(child_id)
                    materialize(child, element_id=child_id)

            if child_ids:
                element_payload["children"] = child_ids

            elements[element_id] = element_payload

        root_id = "root"
        materialize(root_node, element_id=root_id)
        return {
            "root": root_id,
            "state": {},
            "elements": elements,
        }

    @staticmethod
    def _build_element_id_prefix(node_type: Any) -> str:
        """生成稳定的元素 ID 前缀。

        功能：
            这里故意不用 UUID。第五阶段 Spec 在测试、日志和审计快照里都需要可对比性，
            稳定前缀能显著降低调试噪音。
        """
        normalized = re.sub(r"[^a-z0-9]+", "_", str(node_type or "element").strip().lower()).strip("_")
        return normalized or "element"

    def _knowledge_spec(self, results: list[KnowledgeResult], context: dict | None) -> dict[str, Any]:
        """把知识检索结果渲染成列表卡片。"""
        items = [
            {
                "id": result.doc_id,
                "title": result.title,
                "description": result.content[:160],
                "status": result.doc_type,
                "tags": [
                    {"label": result.doc_type or "知识库", "color": "blue"},
                    *(
                        [{"label": tag, "color": "purple"} for tag in result.metadata.get("tags", [])]
                        if isinstance(result.metadata, dict)
                        else []
                    ),
                ],
                "meta": {
                    "source": result.metadata.get("source") if isinstance(result.metadata, dict) else "知识库",
                    "score": f"{result.score:.2f}",
                },
            }
            for result in results
        ]
        return {
            "type": "Card",
            "props": {
                "title": (context or {}).get("title", "知识检索结果"),
                "subtitle": f"命中 {len(items)} 条",
                "actions": [
                    {"type": "view_detail", "label": "查看来源"},
                    {"type": "refresh", "label": "刷新"},
                ],
            },
            "children": [
                {
                    "type": "List",
                    "props": {"title": "相关知识", "items": items, "emptyText": "暂无匹配内容"},
                }
            ],
        }

    def _query_spec(
        self,
        rows: list[dict[str, Any]],
        context: dict | None,
        runtime: ApiQueryUIRuntime | None,
        *,
        include_partial_notice: bool = False,
    ) -> dict[str, Any]:
        """把结构化查询结果渲染成 `Planner*` 读态视图。

        功能：
            第五阶段任务 2 的目标不是“让页面更花哨”，而是把 `api_query` 的读态输出
            收口到稳定的宏观原语：

            - 同质列表 → `PlannerTable`
            - 单对象详情 → `PlannerDetailCard`
            - 局部失败提示 → `PlannerNotice`

            这样做的核心收益是：先把网关对外的 UI 语言稳定下来，后续无论是规则渲染
            还是 LLM Renderer，都不需要再围绕旧的 `Card/Table/Notice` 兼容层打补丁。

        Args:
            rows: 已经过网关裁剪后的结果行。
            context: `api_query` 传入的渲染上下文，包含标题、提示语和渲染模式。
            runtime: 当前查询的运行时动作与交互能力。
            include_partial_notice: 是否需要在成功内容前额外挂载一条局部成功提示。

        Returns:
            `root/state/elements` 形态的 flat spec。

        Edge Cases:
            - 单条列表结果不自动升格为详情卡，只有 route 层显式标记 `detail` 才切详情视图
            - 多步骤摘要表仍然走 `PlannerTable`，但会通过 notice 显式暴露“只展示安全结果”
        """
        render_mode = (context or {}).get("query_render_mode") or "table"
        root_props = {
            "title": (context or {}).get("question", "数据查询结果"),
            "subtitle": self._build_query_subtitle(rows, context, render_mode),
        }
        children: list[dict[str, Any]] = []

        if include_partial_notice:
            children.append(
                {
                    "type": "PlannerNotice",
                    "props": {
                        "text": (context or {}).get("partial_message", "部分步骤执行失败，当前仅展示成功返回的数据。"),
                        "tone": "info",
                    },
                }
            )

        if render_mode == "detail":
            children.append(
                {
                    "type": "PlannerDetailCard",
                    "props": {
                        "title": (context or {}).get("detail_title", "详情信息"),
                        "items": self._build_detail_items(rows[0]),
                    },
                }
            )
            return self._build_flat_card_spec(root_props=root_props, children=children)

        table_props: dict[str, Any] = {
            "columns": self._build_table_columns(rows[0]),
            "dataSource": rows,
        }
        if runtime and runtime.detail.enabled:
            # 详情动作只下发运行时契约，不在网关 UI 层硬编码具体业务参数。
            table_props["rowActions"] = [
                {
                    "type": runtime.detail.ui_action or "remoteQuery",
                    "label": "查看详情",
                    "params": {
                        "api_id": runtime.detail.api_id,
                        "route_url": runtime.detail.route_url,
                        "identifier_field": runtime.detail.identifier_field,
                        "query_param": runtime.detail.query_param,
                        "template_code": runtime.detail.template_code,
                        "fallback_mode": runtime.detail.fallback_mode,
                    },
                }
            ]
        if runtime and runtime.pagination.enabled:
            # 分页后续走 remoteQuery + mutation_target 做局部补丁，不重新生成整页 UI。
            table_props["pagination"] = {
                "enabled": True,
                "total": runtime.pagination.total,
                "currentPage": runtime.pagination.current_page,
                "pageSize": runtime.pagination.page_size,
                "action": {
                    "type": runtime.pagination.ui_action or "remoteQuery",
                    "params": {
                        "api_id": runtime.pagination.api_id,
                        "page_param": runtime.pagination.page_param,
                        "page_size_param": runtime.pagination.page_size_param,
                        "mutation_target": runtime.pagination.mutation_target,
                    },
                },
            }
        if runtime and runtime.template.enabled:
            table_props["templateHint"] = runtime.template.model_dump(exclude_none=True)

        children.append({"type": "PlannerTable", "props": table_props})
        return self._build_flat_card_spec(root_props=root_props, children=children)

    def _notice_spec(self, title: str, message: str, tone: str) -> dict[str, Any]:
        """构造统一 `PlannerNotice` 读态卡片。

        功能：
            任务 2 之后，读态异常不再继续沿用旧的 `Notice` 组件名。
            这里统一输出 `PlannerCard + PlannerNotice`，确保空结果、错误和跳过场景
            与正常读态页面使用同一套组件语义。
        """
        return self._build_flat_card_spec(
            root_props={"title": title, "subtitle": None},
            children=[
                {
                    "type": "PlannerNotice",
                    "props": {
                        "text": message,
                        "tone": tone,
                    },
                }
            ],
        )

    def _task_spec(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        """将待办列表渲染成带筛选器的工作台视图。"""
        items = [
            {
                "id": task.get("id", task.get("sourceId", str(index))),
                "title": task.get("title", "任务"),
                "description": task.get("description", ""),
                "status": task.get("status", "pending"),
                "tags": [
                    {"label": task.get("priority", "普通"), "color": self._priority_color(task.get("priority", ""))},
                    *(
                        [{"label": task.get("sourceSystem", ""), "color": "cyan"}]
                        if task.get("sourceSystem")
                        else []
                    ),
                ],
                "assignee": task.get("owner"),
                "dueDate": task.get("deadline"),
            }
            for index, task in enumerate(tasks)
        ]
        return {
            "type": "Card",
            "props": {
                "title": "最新待办",
                "subtitle": f"共 {len(items)} 条待办",
                "actions": [
                    {"type": "refresh", "label": "刷新待办"},
                    {"type": "trigger_task", "label": "批量处理"},
                ],
            },
            "children": [
                {
                    "type": "Form",
                    "props": {
                        "fields": [
                            {
                                "name": "status",
                                "label": "状态",
                                "type": "select",
                                "options": [
                                    {"label": "全部", "value": "all"},
                                    {"label": "待处理", "value": "pending"},
                                    {"label": "进行中", "value": "in_progress"},
                                    {"label": "已完成", "value": "completed"},
                                ],
                            },
                            {
                                "name": "system",
                                "label": "来源系统",
                                "type": "select",
                                "options": [
                                    {"label": "全部", "value": "all"},
                                    {"label": "ERP", "value": "erp"},
                                    {"label": "CRM", "value": "crm"},
                                    {"label": "OA", "value": "oa"},
                                    {"label": "预约系统", "value": "reservation"},
                                    {"label": "360系统", "value": "system360"},
                                ],
                            },
                        ],
                        "submitLabel": "筛选",
                    },
                },
                {
                    "type": "List",
                    "props": {"title": "任务列表", "items": items, "emptyText": "暂无待办"},
                },
            ],
        }

    def _build_flat_card_spec(
        self,
        *,
        root_props: dict[str, Any],
        children: list[dict[str, Any]],
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构造 `PlannerCard` 根节点的 flat spec。

        功能：
            第五阶段后续还会继续引入 `PlannerForm / PlannerSelect / PlannerButton`。
            先把 flat spec 的根结构抽成一个 helper，后面任务 3、4、5 可以直接复用，
            避免每次都手搓 `root/elements` 造成协议细节再次分散。

        Args:
            root_props: 根卡片展示属性。
            children: 已准备好的子元素列表。
            state: 当前视图初始状态；读态页面通常为空对象。

        Returns:
            合法的 `root/state/elements` flat spec。
        """
        elements: dict[str, Any] = {
            "root": {
                "type": "PlannerCard",
                "props": root_props,
                "children": [],
            }
        }
        for index, child in enumerate(children, start=1):
            child_id = f"child_{index}"
            elements["root"]["children"].append(child_id)
            elements[child_id] = child
        return {
            "root": "root",
            "state": state or {},
            "elements": elements,
        }

    @staticmethod
    def _build_table_columns(sample_row: dict[str, Any]) -> list[dict[str, str]]:
        """把行对象字段映射成 `PlannerTable.columns`。

        功能：
            这里输出稳定的列元数据而不是裸字符串，是为了给后续前端表格实现预留
            `title / dataIndex / key` 三元组契约，避免任务 2 做完后任务 5 又得返工改列结构。
        """
        return [
            {
                "key": key,
                "title": key,
                "dataIndex": key,
            }
            for key in sample_row.keys()
        ]

    @staticmethod
    def _build_detail_items(row: dict[str, Any]) -> list[dict[str, str]]:
        """把对象详情映射成 `PlannerDetailCard.items`。

        功能：
            详情视图的目标是“稳定展示事实”，不是透传原始对象结构。
            因此这里统一把值折叠成可读字符串，避免复杂嵌套对象直接把详情卡 props 撑穿。
        """
        return [
            {
                "label": key,
                "value": DynamicUIService._stringify_detail_value(value),
            }
            for key, value in row.items()
        ]

    @staticmethod
    def _stringify_detail_value(value: Any) -> str:
        """将详情值折叠为可展示文本。"""
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _build_query_subtitle(
        rows: list[dict[str, Any]],
        context: dict[str, Any] | None,
        render_mode: str,
    ) -> str | None:
        """为读态查询页面生成副标题。

        功能：
            `PlannerCard` 的 `subtitle` 是读态页面补充上下文的关键位置。
            这里把“当前是详情还是列表”和“展示条数”压成一句稳定文案，帮助用户快速建立心智。
        """
        total = (context or {}).get("total")
        if render_mode == "detail":
            return "当前展示单条记录详情"
        if render_mode == "summary_table":
            return f"当前展示 {len(rows)} 个执行步骤的汇总结果"
        if isinstance(total, int) and total > len(rows):
            return f"共 {total} 条，当前展示 {len(rows)} 条"
        return f"当前展示 {len(rows)} 条"

    # ── 指标构建 ──

    @staticmethod
    def _build_metrics(numeric_fields: dict[str, list[float]]) -> list[dict[str, Any]]:
        """为数值字段生成多种聚合指标（sum/avg/count）。"""
        metrics: list[dict[str, Any]] = []
        for column, values in numeric_fields.items():
            if not values:
                continue
            total = sum(values)
            avg = mean(values)
            count = len(values)

            # 根据值的分布选择最有意义的聚合方式
            if count > 1 and total != avg:
                # 有多行数据，展示合计
                metrics.append({
                    "type": "Metric",
                    "props": {"label": f"{column} (合计)", "value": f"{total:,.2f}", "format": "number"},
                })
                metrics.append({
                    "type": "Metric",
                    "props": {"label": f"{column} (均值)", "value": f"{avg:,.2f}", "format": "number"},
                })
            else:
                metrics.append({
                    "type": "Metric",
                    "props": {"label": column, "value": f"{total:,.2f}", "format": "number"},
                })

            if len(metrics) >= 4:
                break
        return metrics

    # ── 图表构建 ──

    def _build_chart(
        self,
        columns: list[str],
        rows: list[dict[str, Any]],
        numeric_fields: dict[str, list[float]],
    ) -> dict[str, Any] | None:
        """从查询结果中推导一个最小可用图表。"""
        if not rows or not numeric_fields:
            return None

        first_numeric = next((col for col in columns if numeric_fields.get(col)), None)
        category_field = next((col for col in columns if col != first_numeric), None)
        if not first_numeric or not category_field:
            return None

        categories = [str(row.get(category_field, "-")) for row in rows]
        values = [row.get(first_numeric) for row in rows]
        if not any(isinstance(v, (int, float)) for v in values):
            return None

        chart_kind = self._detect_chart_type(categories, values, rows)
        option = self._build_chart_option(chart_kind, categories, values, first_numeric)

        return {
            "type": "Chart",
            "props": {
                "title": f"{first_numeric} 分布",
                "kind": chart_kind,
                "option": option,
            },
        }

    @staticmethod
    def _detect_chart_type(
        categories: list[str],
        values: list[Any],
        rows: list[dict[str, Any]],
    ) -> str:
        """根据数据特征自动选择最合适的图表类型。"""
        num_categories = len(set(categories))
        num_rows = len(rows)

        # 类别较少（<=6）且数据行数较少 → 饼图
        if num_categories <= 6 and num_rows <= 10:
            return "pie"

        # 类别是时间序列特征（包含年/月/日/季等关键词） → 折线图
        time_keywords = ["年", "月", "日", "季", "周", "2024", "2025", "2026", "Q1", "Q2", "Q3", "Q4"]
        if any(any(kw in cat for kw in time_keywords) for cat in categories[:3]):
            return "line"

        # 默认柱状图
        return "bar"

    @staticmethod
    def _build_chart_option(
        kind: str,
        categories: list[str],
        values: list[Any],
        series_name: str,
    ) -> dict[str, Any]:
        """根据图表类型生成 ECharts option。"""
        if kind == "pie":
            return {
                "tooltip": {"trigger": "item"},
                "legend": {"orient": "vertical", "left": "left"},
                "series": [
                    {
                        "name": series_name,
                        "type": "pie",
                        "radius": "60%",
                        "data": [
                            {"name": cat, "value": val}
                            for cat, val in zip(categories, values)
                            if isinstance(val, (int, float))
                        ],
                    }
                ],
            }

        if kind == "line":
            return {
                "tooltip": {"trigger": "axis"},
                "legend": {"data": [series_name]},
                "xAxis": {"type": "category", "data": categories},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": series_name,
                        "type": "line",
                        "data": values,
                        "smooth": True,
                    }
                ],
            }

        # bar (default)
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [series_name]},
            "xAxis": {"type": "category", "data": categories},
            "yAxis": {"type": "value"},
            "series": [
                {
                    "name": series_name,
                    "type": "bar",
                    "data": values,
                }
            ],
        }

    @staticmethod
    def _priority_color(priority: str) -> str:
        """把业务优先级映射成前端约定颜色。"""
        priority_value = (priority or "").lower()
        if priority_value in ("urgent", "紧急"):
            return "red"
        if priority_value in ("high", "高"):
            return "volcano"
        if priority_value in ("low", "低"):
            return "blue"
        return "orange"
