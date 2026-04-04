from __future__ import annotations

import pytest

from app.core.config import settings
from app.models.schemas import ApiQueryUIAction, ApiQueryUIRuntime
from app.services.dynamic_ui_service import DynamicUIService


class RecordingLLM:
    """记录 Renderer 调用入参的测试替身。"""

    def __init__(self, replies: list[str] | None = None, *, fail_on_json_mode: bool = False) -> None:
        self._replies = list(replies or [])
        self._fail_on_json_mode = fail_on_json_mode
        self.calls: list[dict[str, object]] = []

    async def chat(self, messages, temperature=0.7, *, response_format=None, timeout_seconds=None) -> str:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "response_format": response_format,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self._fail_on_json_mode and response_format:
            raise RuntimeError("response_format unsupported")
        if not self._replies:
            return ""
        return self._replies.pop(0)


def _make_runtime() -> ApiQueryUIRuntime:
    return ApiQueryUIRuntime(
        components=["PlannerCard", "PlannerTable", "PlannerDetailCard", "PlannerNotice"],
        ui_actions=[
            ApiQueryUIAction(
                code="remoteQuery",
                description="详情和分页刷新动作",
                enabled=True,
                params_schema={"type": "object"},
            )
        ],
    )


def _root_element(spec: dict[str, object]) -> dict[str, object]:
    root_id = spec["root"]
    elements = spec["elements"]
    assert isinstance(root_id, str)
    assert isinstance(elements, dict)
    root = elements[root_id]
    assert isinstance(root, dict)
    return root


def _root_child_by_type(spec: dict[str, object], component_type: str) -> dict[str, object]:
    """按根卡片下的组件类型取回元素，便于断言规则回退是否命中。"""
    root = _root_element(spec)
    elements = spec["elements"]
    child_ids = root.get("children", [])
    assert isinstance(elements, dict)
    assert isinstance(child_ids, list)
    for child_id in child_ids:
        assert isinstance(child_id, str)
        child = elements[child_id]
        assert isinstance(child, dict)
        if child.get("type") == component_type:
            return child
    raise AssertionError(f"missing child type: {component_type}")


@pytest.mark.asyncio
async def test_generate_ui_spec_uses_renderer_prompt_json_mode_and_pruned_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """任务3核心验证：首轮必须走 JSON Mode，且 prompt 输入不能原样塞完整 context_pool。"""
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService()
    service._llm_service = RecordingLLM(
        [
            """
            {
              "root": "root",
              "state": {},
              "elements": {
                "root": {
                  "type": "PlannerCard",
                  "props": {"title": "LLM 详情视图"},
                  "children": []
                }
              }
            }
            """
        ]
    )

    context = {
        "question": "查询客户详情",
        "user_query": "查询客户详情",
        "title": "客户详情",
        "query_render_mode": "detail",
        "business_intents": [{"code": "none", "category": "read", "risk_level": "none"}],
        "context_pool": {
            "step_customer_list": {
                "status": "SUCCESS",
                "domain": "crm",
                "api_id": "customer_list",
                "total": 6,
                "data": [
                    {"customerId": "C001", "customerName": "张三"},
                    {"customerId": "C002", "customerName": "李四"},
                    {"customerId": "C003", "customerName": "王五"},
                    {"customerId": "C004", "customerName": "赵六"},
                ],
                "meta": {
                    "raw_row_count": 6,
                    "render_row_count": 5,
                    "render_row_limit": 5,
                    "truncated": True,
                    "truncated_count": 1,
                    "resolved_params": {"pageNum": 1},
                },
            }
        },
    }

    spec = await service.generate_ui_spec(
        intent="query",
        data=[
            {"customerId": "C001", "customerName": "张三"},
            {"customerId": "C002", "customerName": "李四"},
            {"customerId": "C003", "customerName": "王五"},
            {"customerId": "C004", "customerName": "赵六"},
        ],
        context=context,
        runtime=_make_runtime(),
    )

    assert spec is not None
    llm_call = service._llm_service.calls[0]
    assert llm_call["response_format"] == {"type": "json_object"}
    messages = llm_call["messages"]
    assert isinstance(messages, list)
    system_prompt = messages[0]["content"]
    user_prompt = messages[1]["content"]
    assert "Renderer Agent" in system_prompt
    assert "UI Catalog" in system_prompt
    assert "PlannerDetailCard" in system_prompt
    assert "business_intents" in user_prompt
    assert "context_pool" in user_prompt
    assert "C004" not in user_prompt
    assert "resolved_params" not in user_prompt
    assert spec["elements"]["root"]["props"]["title"] == "LLM 详情视图"


@pytest.mark.asyncio
async def test_generate_ui_spec_retries_without_json_mode_when_backend_rejects_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService()
    service._llm_service = RecordingLLM(
        [
            """
            {
              "root": "root",
              "elements": {
                "root": {
                  "type": "PlannerCard",
                  "props": {"title": "纯文本兜底成功"},
                  "children": []
                }
              }
            }
            """
        ],
        fail_on_json_mode=True,
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"customerId": "C001", "customerName": "张三"}],
        context={"question": "查询客户"},
        runtime=_make_runtime(),
    )

    assert spec is not None
    assert len(service._llm_service.calls) == 2
    assert service._llm_service.calls[0]["response_format"] == {"type": "json_object"}
    assert service._llm_service.calls[1]["response_format"] is None
    assert spec["elements"]["root"]["props"]["title"] == "纯文本兜底成功"


@pytest.mark.asyncio
async def test_generate_ui_spec_parses_dirty_renderer_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService()
    service._llm_service = RecordingLLM(
        [
            """```json
            {
              // 这是一个说明注释
              "root": "root",
              "state": {},
              "elements": {
                "root": {
                  "type": "PlannerCard",
                  "props": {
                    "title": "脏 JSON 也要能解析",
                  },
                  "children": [],
                },
              },
            }
            ```"""
        ]
    )

    spec = await service.generate_ui_spec(
        intent="query",
        data=[{"customerId": "C001"}],
        context={"question": "查询客户"},
        runtime=_make_runtime(),
    )

    assert spec is not None
    assert spec["elements"]["root"]["props"]["title"] == "脏 JSON 也要能解析"
    assert spec["state"] == {}


@pytest.mark.asyncio
async def test_generate_ui_spec_falls_back_to_rule_renderer_when_llm_output_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_ui_spec_enabled", True)
    service = DynamicUIService()
    service._llm_service = RecordingLLM(["not json", "still not json"])

    spec = await service.generate_ui_spec(
        intent="query",
        data=[
            {"customerId": "C001", "customerName": "张三"},
            {"customerId": "C002", "customerName": "李四"},
        ],
        context={"question": "查询客户列表"},
        runtime=_make_runtime(),
    )

    assert spec is not None
    assert len(service._llm_service.calls) == 2
    table = _root_child_by_type(spec, "PlannerTable")
    assert table["props"]["dataSource"][0]["customerId"] == "C001"
