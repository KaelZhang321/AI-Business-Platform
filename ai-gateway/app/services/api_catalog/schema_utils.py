from __future__ import annotations

from typing import Any


def resolve_schema_at_data_path(
    response_schema: dict[str, Any],
    response_data_path: str,
) -> tuple[dict[str, Any], bool]:
    """按 `response_data_path` 定位响应 schema 节点。"""
    current: dict[str, Any] = response_schema
    array_mode = False
    for segment in [part for part in response_data_path.split(".") if part]:
        properties = current.get("properties") if isinstance(current, dict) else None
        next_schema = properties.get(segment) if isinstance(properties, dict) else None
        if not isinstance(next_schema, dict):
            return {}, False
        if str(next_schema.get("type") or "").strip().lower() == "array":
            items = next_schema.get("items")
            if not isinstance(items, dict):
                return {}, False
            current = items
            array_mode = True
            continue
        current = next_schema
    return current if isinstance(current, dict) else {}, array_mode


def describe_schema_type(field_schema: dict[str, Any]) -> str | None:
    """把 schema 原始类型压成稳定字符串。"""
    schema_type = str(field_schema.get("type") or "").strip().lower()
    schema_format = str(field_schema.get("format") or "").strip().lower()
    if schema_type == "array":
        items = field_schema.get("items")
        if isinstance(items, dict):
            item_type = str(items.get("type") or "object").strip().lower() or "object"
            return f"list<{item_type}>"
        return "list<object>"
    if schema_type == "string" and schema_format:
        return schema_format
    if schema_type == "integer" and schema_format:
        return schema_format
    if schema_type:
        return schema_type
    return None


def extract_schema_description(field_schema: dict[str, Any], *, fallback_label: str | None = None) -> str | None:
    """提取字段原始描述。"""
    label = field_schema.get("description") or field_schema.get("title") or fallback_label
    if isinstance(label, str) and label.strip():
        return label.strip()
    return None


def schema_is_array(field_schema: dict[str, Any]) -> bool:
    """判断字段是否数组。"""
    return str(field_schema.get("type") or "").strip().lower() == "array"
