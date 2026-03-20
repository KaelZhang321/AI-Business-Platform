from __future__ import annotations

from typing import Any


class DynamicUIService:
    """动态UI Spec生成服务

    根据AI响应内容生成前端可渲染的UI规格，支持:
    - 表格展示
    - 图表可视化
    - 表单收集
    - 卡片列表
    """

    async def generate_ui_spec(self, intent: str, data: Any, context: dict | None = None) -> dict[str, Any] | None:
        """根据意图和数据生成UI规格"""
        if not data:
            return None

        if intent == "query" and isinstance(data, list) and isinstance(data[0], dict):
            columns = list(data[0].keys())
            rows = [[row.get(col) for col in columns] for row in data]
            return {
                "type": "Card",
                "props": {"title": context.get("question") if context else "查询结果"},
                "children": [
                    {
                        "type": "Table",
                        "props": {
                            "title": "结果明细",
                            "columns": columns,
                            "data": rows,
                        },
                    }
                ],
            }

        if intent == "knowledge" and isinstance(data, list):
            return {
                "type": "List",
                "props": {
                    "items": [
                        {
                            "id": item.doc_id if hasattr(item, "doc_id") else str(idx),
                            "title": getattr(item, "title", ""),
                            "description": getattr(item, "content", "")[:120],
                            "status": getattr(item, "doc_type", "") or None,
                        }
                        for idx, item in enumerate(data)
                    ]
                },
            }

        if isinstance(data, dict) and {"label", "value"}.issubset(data.keys()):
            return {
                "type": "Metric",
                "props": {
                    "label": data.get("label"),
                    "value": data.get("value"),
                    "format": data.get("format"),
                },
            }

        return None
