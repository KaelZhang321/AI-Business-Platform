from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.schemas import ApiQueryUIAction, ApiQueryUIRuntime
from app.services.ui_catalog_service import UICatalogService


@dataclass(frozen=True, slots=True)
class UISpecValidationError:
    """单条 UI Spec 校验错误。"""

    code: str
    path: str
    message: str


@dataclass(slots=True)
class UISpecValidationResult:
    """UI Spec 校验结果。

    功能：
        第五阶段的关键不是“尽量渲染出来”，而是“绝不把残缺绑定的半成品交给前端”。
        因此这里统一把所有错误收口成结构化列表，供渲染器决定是否冻结视图。
    """

    errors: list[UISpecValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """当前 Spec 是否通过校验。"""
        return not self.errors


class UISpecGuard:
    """第五阶段 UI Spec 安全校验器。

    功能：
        负责在 Spec 出口做最后一道“安全气闸”，重点拦截：
        1. 未注册组件或未启用组件
        2. 未注册动作或未启用动作
        3. `$bindState` / `$state` 路径断裂
        4. 动作 `params_schema.required` 缺失

    Edge Cases:
        - 只校验 `root/state/elements` flat spec，避免把旧协议继续放大
        - 对于当前 runtime 未启用的动作，直接视为非法，而不是默默放行
        - 即使动作参数值来自 `$bindState`，也必须先保证绑定路径本身存在
    """

    def __init__(self, catalog_service: UICatalogService | None = None) -> None:
        self._catalog_service = catalog_service or UICatalogService()

    def validate(
        self,
        spec: dict[str, Any] | None,
        *,
        intent: str,
        runtime: ApiQueryUIRuntime | None = None,
    ) -> UISpecValidationResult:
        """校验单份 UI Spec。

        Args:
            spec: 待校验的 flat spec。
            intent: 当前渲染意图，用于兜底组件范围。
            runtime: 当前请求的运行时能力目录，优先级高于全局 Catalog。

        Returns:
            `UISpecValidationResult`。调用方应以 `is_valid` 决定是否冻结视图。
        """
        errors: list[UISpecValidationError] = []
        if not isinstance(spec, dict):
            errors.append(
                UISpecValidationError(
                    code="spec_not_object",
                    path="$",
                    message="UI Spec 必须是对象。",
                )
            )
            return UISpecValidationResult(errors=errors)

        root_id = spec.get("root")
        state = spec.get("state")
        elements = spec.get("elements")

        if not isinstance(root_id, str) or not root_id:
            errors.append(
                UISpecValidationError(
                    code="root_invalid",
                    path="$.root",
                    message="UI Spec 缺少合法的根节点 ID。",
                )
            )
        if not isinstance(state, dict):
            errors.append(
                UISpecValidationError(
                    code="state_invalid",
                    path="$.state",
                    message="UI Spec 的 state 必须是对象。",
                )
            )
            state = {}
        if not isinstance(elements, dict):
            errors.append(
                UISpecValidationError(
                    code="elements_invalid",
                    path="$.elements",
                    message="UI Spec 的 elements 必须是对象字典。",
                )
            )
            return UISpecValidationResult(errors=errors)

        if isinstance(root_id, str) and root_id not in elements:
            errors.append(
                UISpecValidationError(
                    code="root_missing",
                    path="$.root",
                    message=f"根节点 `{root_id}` 不存在于 elements 中。",
                )
            )

        all_component_codes = self._catalog_service.get_all_component_codes()
        allowed_component_codes = (
            set(runtime.components)
            if runtime and runtime.components
            else (set(self._catalog_service.get_component_codes(intent=intent)))
        )
        runtime_actions = {action.code: action for action in (runtime.ui_actions if runtime else []) if action.enabled}
        all_action_codes = self._catalog_service.get_all_action_codes()
        allowed_action_codes = set(runtime_actions) if runtime_actions else set(all_action_codes)

        for element_id, element in elements.items():
            element_path = f"$.elements.{element_id}"
            if not isinstance(element, dict):
                errors.append(
                    UISpecValidationError(
                        code="element_invalid",
                        path=element_path,
                        message="元素定义必须是对象。",
                    )
                )
                continue

            element_type = element.get("type")
            if not isinstance(element_type, str) or not element_type:
                errors.append(
                    UISpecValidationError(
                        code="element_type_missing",
                        path=f"{element_path}.type",
                        message="元素缺少合法的组件类型。",
                    )
                )
            elif element_type not in all_component_codes:
                errors.append(
                    UISpecValidationError(
                        code="unknown_component",
                        path=f"{element_path}.type",
                        message=f"组件 `{element_type}` 未注册。",
                    )
                )
            elif element_type not in allowed_component_codes:
                errors.append(
                    UISpecValidationError(
                        code="component_not_enabled",
                        path=f"{element_path}.type",
                        message=f"组件 `{element_type}` 不在当前运行时允许范围内。",
                    )
                )

            children = element.get("children")
            if children is not None:
                if not isinstance(children, list):
                    errors.append(
                        UISpecValidationError(
                            code="children_invalid",
                            path=f"{element_path}.children",
                            message="children 必须是字符串 ID 数组。",
                        )
                    )
                else:
                    for index, child_id in enumerate(children):
                        if not isinstance(child_id, str) or child_id not in elements:
                            errors.append(
                                UISpecValidationError(
                                    code="child_missing",
                                    path=f"{element_path}.children[{index}]",
                                    message=f"子节点 `{child_id}` 未在 elements 中注册。",
                                )
                            )

        self._walk_payload(
            current=spec,
            path="$",
            state=state,
            all_component_codes=all_component_codes,
            all_action_codes=all_action_codes,
            allowed_action_codes=allowed_action_codes,
            runtime_actions=runtime_actions,
            errors=errors,
        )
        return UISpecValidationResult(errors=errors)

    def _walk_payload(
        self,
        *,
        current: Any,
        path: str,
        state: dict[str, Any],
        all_component_codes: set[str],
        all_action_codes: set[str],
        allowed_action_codes: set[str],
        runtime_actions: dict[str, ApiQueryUIAction],
        errors: list[UISpecValidationError],
    ) -> None:
        """递归扫描绑定和动作定义。"""
        if isinstance(current, dict):
            bind_state_path = current.get("$bindState")
            if isinstance(bind_state_path, str):
                self._validate_state_pointer(
                    pointer=bind_state_path,
                    state=state,
                    path=f"{path}.$bindState",
                    pointer_kind="$bindState",
                    errors=errors,
                )

            visible_state_path = current.get("$state")
            if isinstance(visible_state_path, str):
                self._validate_state_pointer(
                    pointer=visible_state_path,
                    state=state,
                    path=f"{path}.$state",
                    pointer_kind="$state",
                    errors=errors,
                )

            self._validate_action_candidate(
                current=current,
                path=path,
                all_component_codes=all_component_codes,
                all_action_codes=all_action_codes,
                allowed_action_codes=allowed_action_codes,
                runtime_actions=runtime_actions,
                errors=errors,
            )

            for key, value in current.items():
                next_path = f"{path}.{key}"
                self._walk_payload(
                    current=value,
                    path=next_path,
                    state=state,
                    all_component_codes=all_component_codes,
                    all_action_codes=all_action_codes,
                    allowed_action_codes=allowed_action_codes,
                    runtime_actions=runtime_actions,
                    errors=errors,
                )
            return

        if isinstance(current, list):
            for index, item in enumerate(current):
                self._walk_payload(
                    current=item,
                    path=f"{path}[{index}]",
                    state=state,
                    all_component_codes=all_component_codes,
                    all_action_codes=all_action_codes,
                    allowed_action_codes=allowed_action_codes,
                    runtime_actions=runtime_actions,
                    errors=errors,
                )

    def _validate_action_candidate(
        self,
        *,
        current: dict[str, Any],
        path: str,
        all_component_codes: set[str],
        all_action_codes: set[str],
        allowed_action_codes: set[str],
        runtime_actions: dict[str, ApiQueryUIAction],
        errors: list[UISpecValidationError],
    ) -> None:
        """校验动作节点是否合法。

        功能：
            当前网关存在两类动作表达：
            1. `{"type": "remoteQuery", "params": {...}}`
            2. `{"action": "saveToServer", "params": {...}}`
            这里只校验这些“看起来像动作”的对象，避免把组件 `type` 误判成动作。
        """
        action_code: str | None = None
        action_path: str | None = None

        action_name = current.get("action")
        if isinstance(action_name, str):
            action_code = action_name
            action_path = f"{path}.action"
        else:
            node_type = current.get("type")
            if (
                isinstance(node_type, str)
                and node_type not in all_component_codes
                and self._looks_like_action_object(current, path)
            ):
                action_code = node_type
                action_path = f"{path}.type"

        if not action_code or not action_path:
            return

        if action_code not in all_action_codes:
            errors.append(
                UISpecValidationError(
                    code="unknown_action",
                    path=action_path,
                    message=f"动作 `{action_code}` 未注册。",
                )
            )
            return

        if action_code not in allowed_action_codes:
            errors.append(
                UISpecValidationError(
                    code="action_not_enabled",
                    path=action_path,
                    message=f"动作 `{action_code}` 不在当前运行时允许范围内。",
                )
            )

        action_schema = runtime_actions.get(action_code)
        if action_schema is None:
            catalog_definition = self._catalog_service.get_action_definition(action_code)
            if catalog_definition is not None:
                action_schema = ApiQueryUIAction(
                    code=catalog_definition.code,
                    description=catalog_definition.description,
                    enabled=catalog_definition.enabled,
                    params_schema=dict(catalog_definition.params_schema),
                )

        required_fields = _extract_required_fields(action_schema.params_schema if action_schema else {})
        if not required_fields:
            return

        params = current.get("params")
        if not isinstance(params, dict):
            errors.append(
                UISpecValidationError(
                    code="action_params_missing",
                    path=f"{path}.params",
                    message=f"动作 `{action_code}` 缺少对象类型的 params。",
                )
            )
            return

        for required_field in required_fields:
            value = params.get(required_field)
            if value in (None, "", [], {}):
                errors.append(
                    UISpecValidationError(
                        code="action_required_param_missing",
                        path=f"{path}.params.{required_field}",
                        message=f"动作 `{action_code}` 缺少必填参数 `{required_field}`。",
                    )
                )

    @staticmethod
    def _looks_like_action_object(current: dict[str, Any], path: str) -> bool:
        """判断当前对象是否更像动作配置而不是普通数据对象。"""
        if any(key in current for key in ("props", "children")):
            return False
        if any(key in current for key in ("params", "label", "on")):
            return True
        return path.endswith(".action")

    @staticmethod
    def _validate_state_pointer(
        *,
        pointer: str,
        state: dict[str, Any],
        path: str,
        pointer_kind: str,
        errors: list[UISpecValidationError],
    ) -> None:
        """校验状态路径是否真实存在。"""
        if not _state_path_exists(state, pointer):
            errors.append(
                UISpecValidationError(
                    code="state_path_missing",
                    path=path,
                    message=f"{pointer_kind} 指向的状态路径 `{pointer}` 不存在。",
                )
            )


def _extract_required_fields(schema: dict[str, Any]) -> list[str]:
    """从动作参数 Schema 中提取必填字段。"""
    required = schema.get("required")
    if not isinstance(required, list):
        return []
    return [str(item) for item in required if isinstance(item, str) and item]


def _state_path_exists(state: dict[str, Any], pointer: str) -> bool:
    """判断 JSON Pointer 风格路径是否存在于 state 中。

    功能：
        `$bindState` 的正确性不是靠前端兜底，而是服务端先判定“这条路有没有通”。
        这里只支持当前网关真实会产出的 `/a/b/c` 风格，避免引入过度复杂的表达式解析。
    """
    if pointer in {"", "/"}:
        return True
    if not pointer.startswith("/"):
        return False

    current: Any = state
    for segment in [item for item in pointer.split("/") if item]:
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
