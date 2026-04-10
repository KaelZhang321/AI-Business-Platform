"""DAG 参数绑定工具。

功能：
    为第三阶段 Planner 产出的 JSONPath 风格绑定表达式提供最小可控实现，
    只支持设计文档明确要求的语法子集：

    - `$[step_x.data].field`
    - `$[step_x.data][*].field`

设计动机：
    这里没有直接引入通用 JSONPath 解释器，而是实现一个受限子集。
    原因不是“偷懒”，而是企业工作流链路更需要可审计、可预测的绑定规则。
    支持越多自由语法，越难对白名单、依赖校验和空上游短路做强约束。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_BINDING_PREFIX = "$["
_DATA_SEGMENT = ".data]"
_WILDCARD_SEGMENT = "[*]"


class DagBindingSyntaxError(ValueError):
    """DAG 参数绑定表达式语法错误。"""


@dataclass(frozen=True)
class DagBindingExpression:
    """受限 JSONPath 绑定表达式的解析结果。

    Args:
        step_id: 绑定引用的上游步骤 ID。
        tokens: 绑定尾部的路径标记，仅支持字段访问与数组通配。

    Returns:
        不直接返回业务值；该对象只承担“已验证语法”的作用，供校验和执行阶段复用。

    Edge Cases:
        - 仅允许访问 `step_id.data`，不允许绑定 error/meta 等运行时字段
        - 不支持任意索引、过滤表达式或函数调用，避免语义失控
    """

    step_id: str
    tokens: tuple[str, ...]


def is_dag_binding(value: Any) -> bool:
    """判断当前值是否是第三阶段使用的 JSONPath 绑定表达式。"""
    return isinstance(value, str) and value.strip().startswith(_BINDING_PREFIX)


def collect_binding_step_ids(payload: Any) -> set[str]:
    """递归收集参数载荷中引用到的上游步骤。

    功能：
        在执行前先从 `params` 中抽出所有 JSONPath 依赖，确保每个引用都能在
        `depends_on` 和 DAG 步骤表中找到合法来源。

    Args:
        payload: 步骤参数对象，可能是 dict / list / 标量混合结构。

    Returns:
        当前参数载荷中引用到的全部步骤 ID 集合。

    Edge Cases:
        非绑定值会被静默忽略；语法非法的绑定会抛出 `DagBindingSyntaxError`，
        交给 Planner 校验阶段阻断。
    """
    referenced_steps: set[str] = set()

    if isinstance(payload, dict):
        for value in payload.values():
            referenced_steps.update(collect_binding_step_ids(value))
        return referenced_steps

    if isinstance(payload, list):
        for item in payload:
            referenced_steps.update(collect_binding_step_ids(item))
        return referenced_steps

    if is_dag_binding(payload):
        referenced_steps.add(parse_binding_expression(payload).step_id)

    return referenced_steps


def evaluate_binding_expression(expression: str, step_data_by_id: dict[str, Any]) -> Any:
    """执行受限 JSONPath 绑定表达式。

    Args:
        expression: Planner 产出的绑定表达式。
        step_data_by_id: 上游步骤 ID -> 原始 `data` 的映射。

    Returns:
        解析出的业务值。若表达式经过数组通配，返回列表；否则返回单值或 `None`。

    Edge Cases:
        - 上游步骤不存在或无数据时，返回 `None`/`[]`，由执行器决定是否短路
        - 字段路径不存在时不抛异常，统一降级为空值，避免坏数据把整条链路打爆
    """
    parsed = parse_binding_expression(expression)
    current_value: Any = step_data_by_id.get(parsed.step_id)
    saw_wildcard = False

    for token in parsed.tokens:
        if token == _WILDCARD_SEGMENT:
            saw_wildcard = True
            if isinstance(current_value, list):
                current_value = list(current_value)
            else:
                current_value = []
            continue

        field_name = token.removeprefix(".")
        if saw_wildcard:
            if not isinstance(current_value, list):
                return []

            # 这里按“宽容读取、严格降级”处理：单个元素缺字段不会报错，但也不会伪造默认值。
            extracted_items = []
            for item in current_value:
                if isinstance(item, dict) and field_name in item:
                    extracted_items.append(item[field_name])
            current_value = extracted_items
            continue

        if isinstance(current_value, dict):
            current_value = current_value.get(field_name)
            continue

        return None

    if saw_wildcard:
        return current_value if isinstance(current_value, list) else []
    return current_value


def parse_binding_expression(expression: str) -> DagBindingExpression:
    """解析第三阶段允许的 JSONPath 绑定表达式。

    Args:
        expression: Planner 输出的绑定字符串。

    Returns:
        经过语法校验的 `DagBindingExpression`。

    Raises:
        DagBindingSyntaxError: 绑定表达式不符合受限 JSONPath 语法。

    Edge Cases:
        - 不允许空 `step_id`
        - 只接受 `[*]` 通配，不接受 `[0]`、`[1]` 等任意索引
        - 字段访问必须使用 `.field` 的显式形式，避免含糊路径
    """
    text = expression.strip()
    if not text.startswith(_BINDING_PREFIX) or _DATA_SEGMENT not in text:
        raise DagBindingSyntaxError(f"Unsupported DAG binding expression: {expression}")

    prefix_end = text.find(_DATA_SEGMENT)
    step_id = text[len(_BINDING_PREFIX):prefix_end].strip()
    if not step_id:
        raise DagBindingSyntaxError(f"Missing step_id in DAG binding expression: {expression}")

    tail = text[prefix_end + len(_DATA_SEGMENT):]
    tokens: list[str] = []
    index = 0

    while index < len(tail):
        if tail.startswith(_WILDCARD_SEGMENT, index):
            tokens.append(_WILDCARD_SEGMENT)
            index += len(_WILDCARD_SEGMENT)
            continue

        if tail[index] != ".":
            raise DagBindingSyntaxError(f"Unsupported DAG binding token near '{tail[index:]}'")

        next_index = index + 1
        while next_index < len(tail) and tail[next_index] not in ".[":
            next_index += 1

        field_name = tail[index + 1:next_index].strip()
        if not field_name:
            raise DagBindingSyntaxError(f"Empty field token in DAG binding expression: {expression}")

        tokens.append(f".{field_name}")
        index = next_index

    return DagBindingExpression(step_id=step_id, tokens=tuple(tokens))
