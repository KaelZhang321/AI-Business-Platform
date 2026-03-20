from __future__ import annotations

from statistics import mean
from typing import Any

from app.models.schemas import KnowledgeResult


class DynamicUIService:
    """根据意图构建 json-render 兼容的 UI Spec"""

    async def generate_ui_spec(self, intent: str, data: Any, context: dict | None = None) -> dict[str, Any] | None:
        if not data:
            return None

        if intent == "knowledge" and isinstance(data, list):
            return self._knowledge_spec(data, context)

        if intent == "query" and isinstance(data, list) and data and isinstance(data[0], dict):
            return self._query_spec(data, context)

        if intent == "task" and isinstance(data, list):
            return self._task_spec(data)

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
        metrics = [
            {
                "type": "Metric",
                "props": {
                    "label": column,
                    "value": f"{mean(values):.2f}",
                    "format": "number",
                },
            }
            for column, values in numeric_fields.items()
            if values
        ][:3]

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
                "actions": [{"type": "refresh", "label": "刷新待办"}],
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
                                    {"label": "进行中", "value": "processing"},
                                ],
                            },
                            {
                                "name": "system",
                                "label": "来源系统",
                                "type": "select",
                                "options": [
                                    {"label": "ERP", "value": "erp"},
                                    {"label": "CRM", "value": "crm"},
                                    {"label": "OA", "value": "oa"},
                                ],
                            },
                        ],
                        "submitLabel": "筛选",
                    },
                },
                {
                    "type": "List",
                    "props": {"title": "任务列表", "items": items, "emptyText": "暂无待办"},
                }
            ],
        }

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

        option = {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [first_numeric]},
            "xAxis": {"type": "category", "data": categories},
            "yAxis": {"type": "value"},
            "series": [
                {
                    "name": first_numeric,
                    "type": "bar",
                    "data": values,
                }
            ],
        }
        return {
            "type": "Chart",
            "props": {
                "title": f"{first_numeric} 趋势",
                "kind": "bar",
                "option": option,
            },
        }

    @staticmethod
    def _priority_color(priority: str) -> str:
        priority_value = (priority or "").lower()
        if priority_value.startswith("h"):
            return "red"
        if priority_value.startswith("l"):
            return "blue"
        return "orange"
