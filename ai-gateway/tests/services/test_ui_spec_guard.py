from __future__ import annotations

from app.models.schemas import ApiQueryUIAction, ApiQueryUIRuntime
from app.services.ui_spec_guard import UISpecGuard


def _make_runtime() -> ApiQueryUIRuntime:
    return ApiQueryUIRuntime(
        components=["PlannerCard", "PlannerTable", "PlannerDetailCard", "PlannerNotice"],
        ui_actions=[
            ApiQueryUIAction(
                code="remoteQuery",
                description="分页与详情拉取",
                enabled=True,
                params_schema={
                    "type": "object",
                    "required": ["api_id"],
                },
            )
        ],
    )


def _make_spec(*, child_type: str = "PlannerNotice") -> dict[str, object]:
    return {
        "root": "root",
        "state": {"form": {"customerId": "C001"}},
        "elements": {
            "root": {
                "type": "PlannerCard",
                "props": {"title": "测试页面"},
                "children": ["child_1"],
            },
            "child_1": {
                "type": child_type,
                "props": {"text": "提示信息", "tone": "info"},
            },
        },
    }


def test_ui_spec_guard_rejects_unknown_component() -> None:
    guard = UISpecGuard()

    result = guard.validate(
        _make_spec(child_type="UnknownWidget"),
        intent="query",
        runtime=_make_runtime(),
    )

    assert result.is_valid is False
    assert {error.code for error in result.errors} >= {"unknown_component"}


def test_ui_spec_guard_rejects_unknown_action() -> None:
    guard = UISpecGuard()
    spec = _make_spec()
    spec["elements"]["child_1"]["props"]["action"] = {
        "type": "imaginaryAction",
        "label": "非法动作",
        "params": {},
    }

    result = guard.validate(spec, intent="query", runtime=_make_runtime())

    assert result.is_valid is False
    assert {error.code for error in result.errors} >= {"unknown_action"}


def test_ui_spec_guard_rejects_missing_bind_state_path() -> None:
    guard = UISpecGuard()
    spec = _make_spec()
    spec["elements"]["child_1"]["props"]["action"] = {
        "type": "remoteQuery",
        "label": "查看详情",
        "params": {
            "api_id": {"$bindState": "/form/missingApiId"},
        },
    }

    result = guard.validate(spec, intent="query", runtime=_make_runtime())

    assert result.is_valid is False
    assert {error.code for error in result.errors} >= {"state_path_missing"}


def test_ui_spec_guard_rejects_missing_required_action_param() -> None:
    guard = UISpecGuard()
    spec = _make_spec()
    spec["elements"]["child_1"]["props"]["action"] = {
        "type": "remoteQuery",
        "label": "查看详情",
        "params": {},
    }

    result = guard.validate(spec, intent="query", runtime=_make_runtime())

    assert result.is_valid is False
    assert {error.code for error in result.errors} >= {"action_required_param_missing"}
