from __future__ import annotations

import logging
from statistics import mean
from typing import Any

from app.core.config import settings
from app.models.schemas import KnowledgeResult

logger = logging.getLogger(__name__)


class DynamicUIService:
    """根据意图构建 json-render 兼容的 UI Spec。

    支持两种模式：
    - 规则模式（默认）：基于硬编码模板，根据数据特征自动生成 UI Spec
    - LLM 模式（实验性）：通过 LLM 生成 UI Spec，需设置 LLM_UI_SPEC_ENABLED=true
    """

    async def generate_ui_spec(self, intent: str, data: Any, context: dict | None = None) -> dict[str, Any] | None:
        if not data:
            return None

        # LLM 模式：启用后优先尝试 LLM 生成，失败时回退到规则模式
        if settings.llm_ui_spec_enabled:
            try:
                spec = await self._llm_generate_spec(intent, data, context)
                if spec:
                    return spec
            except Exception as exc:
                logger.warning("LLM UI Spec 生成失败，回退规则模式: %s", exc)

        # 规则模式（默认）
        if intent == "knowledge" and isinstance(data, list):
            return self._knowledge_spec(data, context)

        if intent == "query" and isinstance(data, list) and data and isinstance(data[0], dict):
            return self._query_spec(data, context)

        if intent == "task" and isinstance(data, list):
            return self._task_spec(data)

        return None

    async def _llm_generate_spec(self, intent: str, data: Any, context: dict | None) -> dict[str, Any] | None:
        """通过 LLM 生成 UI Spec（实验性）。

        将数据摘要和意图发送给 LLM，要求返回 json-render 兼容的 JSON Spec。
        支持的组件类型：Card / Table / Metric / List / Form / Tag / Chart。

        返回 None 表示 LLM 未生成有效 Spec，调用方应回退到规则模式。
        """
        import json as _json

        from app.services.llm_service import LLMService

        llm = LLMService()

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
            if isinstance(spec, dict) and "type" in spec:
                return spec
        except _json.JSONDecodeError:
            logger.debug("LLM 返回的 UI Spec 不是有效 JSON: %s", cleaned[:200])

        return None

    def _knowledge_spec(self, results: list[KnowledgeResult], context: dict | None) -> dict[str, Any]:
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

    def _query_spec(self, rows: list[dict[str, Any]], context: dict | None) -> dict[str, Any]:
        columns = list(rows[0].keys())
        dataset = [[row.get(column) for column in columns] for row in rows]
        numeric_fields = {
            column: [value for value in (row.get(column) for row in rows) if isinstance(value, (int, float))]
            for column in columns
        }

        metrics = self._build_metrics(numeric_fields)
        chart_spec = self._build_chart(columns, rows, numeric_fields)

        children: list[dict[str, Any]] = []
        if metrics:
            children.extend(metrics)
        if chart_spec:
            children.append(chart_spec)

        children.append(
            {
                "type": "Table",
                "props": {
                    "title": "查询结果",
                    "columns": columns,
                    "data": dataset,
                    "actions": [{"type": "export", "label": "导出 CSV"}],
                },
            }
        )

        return {
            "type": "Card",
            "props": {
                "title": (context or {}).get("question", "数据查询结果"),
                "actions": [
                    {"type": "export", "label": "导出表格"},
                    {"type": "refresh", "label": "重新查询"},
                ],
            },
            "children": children,
        }

    def _task_spec(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
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
        priority_value = (priority or "").lower()
        if priority_value in ("urgent", "紧急"):
            return "red"
        if priority_value in ("high", "高"):
            return "volcano"
        if priority_value in ("low", "低"):
            return "blue"
        return "orange"
