from __future__ import annotations

import json
from typing import Any, TypeVar

T = TypeVar("T")


def strip_json_comments(text: str) -> str:
    """删除 JSON 字符串之外的行注释与块注释。"""
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False
    length = len(text)

    while index < length:
        char = text[index]
        next_char = text[index + 1] if index + 1 < length else ""

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            index += 2
            while index < length and text[index] not in ("\n", "\r"):
                index += 1
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result)


def strip_trailing_commas(text: str) -> str:
    """删除对象和数组闭合前的尾逗号，同时保留字符串原文。"""
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False
    length = len(text)

    while index < length:
        char = text[index]

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == ",":
            lookahead = index + 1
            while lookahead < length and text[lookahead].isspace():
                lookahead += 1
            if lookahead < length and text[lookahead] in ("]", "}"):
                index += 1
                continue

        result.append(char)
        index += 1

    return "".join(result)


def extract_first_json_object_text(raw_text: str) -> str:
    """从模型输出或脏文本中剥离首个 JSON 对象文本。"""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or start >= end:
        return ""

    return strip_trailing_commas(strip_json_comments(text[start : end + 1]))


def parse_dirty_json_object(raw_text: str) -> dict[str, Any]:
    """尽量把脏输出恢复成 JSON 对象，失败时返回空对象。"""
    json_text = extract_first_json_object_text(raw_text)
    if not json_text:
        return {}

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def summarize_log_text(text: str | None, *, limit: int = 240) -> str:
    """压缩日志文本长度，避免把整段脏输出原样写入日志。"""
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def load_json_value(value: Any, default: T) -> T:
    """把可能来自字符串字段的 JSON 还原成 Python 值。"""
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def load_json_object(value: Any, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """把输入稳定规整成 JSON 对象，失败时返回默认值或空对象。"""
    if isinstance(value, dict):
        return dict(value)

    resolved_default = dict(default) if isinstance(default, dict) else {}
    parsed = load_json_value(value, resolved_default)
    return dict(parsed) if isinstance(parsed, dict) else resolved_default


def load_json_object_or_none(value: Any) -> dict[str, Any] | None:
    """把输入解析成 JSON 对象；若不是对象则返回 `None`。"""
    if isinstance(value, dict):
        return dict(value)

    parsed = load_json_value(value, None)
    return dict(parsed) if isinstance(parsed, dict) else None
