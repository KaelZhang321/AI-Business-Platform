from __future__ import annotations

from typing import Any


def read_state_value(state: Any, state_path: str) -> Any:
    """按 `/form/email` 形式读取嵌套 state 值。"""
    if not state_path.startswith("/"):
        return None

    current = state
    for segment in [item for item in state_path.split("/") if item]:
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                return None
            index = int(segment)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def write_state_value(state: dict[str, Any], state_path: str, value: Any) -> None:
    """按 `/form/email` 形式写入嵌套 state 值。"""
    if not isinstance(state, dict) or not state_path.startswith("/"):
        return

    segments = [item for item in state_path.split("/") if item]
    if not segments:
        return

    current = state
    for segment in segments[:-1]:
        child = current.get(segment)
        if not isinstance(child, dict):
            child = {}
            current[segment] = child
        current = child
    current[segments[-1]] = value


def state_path_exists(state: dict[str, Any], state_path: str) -> bool:
    """判断 JSON Pointer 风格路径是否存在于 state 中。"""
    if state_path in {"", "/"}:
        return True
    if not state_path.startswith("/"):
        return False

    current: Any = state
    for segment in [item for item in state_path.split("/") if item]:
        if isinstance(current, dict):
            if segment not in current:
                return False
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                return False
            index = int(segment)
            if index < 0 or index >= len(current):
                return False
            current = current[index]
            continue
        return False
    return True
