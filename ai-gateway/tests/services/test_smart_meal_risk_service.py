from __future__ import annotations

import pytest

from app.services.smart_meal_risk_service import (
    SmartMealRiskService,
)


class StubLLM:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    async def chat(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        return self.raw

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_identify_risks_uses_llm_output_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService(
        llm_service=StubLLM(
            """{
              "has_risk": true,
              "risk_items": [
                {"ingredient":"西兰花","intolerance_level":"2级","source_dish":"蒜蓉西兰花"},
                {"ingredient":"西兰花","intolerance_level":"2级","source_dish":"清炒时蔬"}
              ]
            }"""
        )
    )

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return [{"ingredient": "西兰花", "intolerance_level": "2级"}]

    async def stub_query_package_ingredients(**kwargs):  # noqa: ANN003
        return [
            {"dish_name": "蒜蓉西兰花", "ingredient_name": "西兰花"},
            {"dish_name": "清炒时蔬", "ingredient_name": "西兰花"},
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)
    monkeypatch.setattr(service, "_query_package_ingredients", stub_query_package_ingredients)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        sex="男",
        age=36,
        package_code="TC202604180001",
        trace_id="trace-1",
    )
    assert result == [
        {
            "ingredient": "西兰花",
            "intolerance_level": "2级",
            "source_dish": "清炒时蔬，蒜蓉西兰花",
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_fallback_to_rule_match_when_llm_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService(llm_service=StubLLM("not json"))

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return [
            {"ingredient": "小麦", "intolerance_level": "IgG抗体3级"},
            {"ingredient": "牛奶", "intolerance_level": "1级"},
        ]

    async def stub_query_package_ingredients(**kwargs):  # noqa: ANN003
        return [
            {"dish_name": "奶香意面", "ingredient_name": "小麦粉"},
            {"dish_name": "奶香意面", "ingredient_name": "牛奶"},
            {"dish_name": "时蔬沙拉", "ingredient_name": "生菜"},
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)
    monkeypatch.setattr(service, "_query_package_ingredients", stub_query_package_ingredients)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        sex="女",
        age=30,
        package_code="TC202604180001",
        trace_id="trace-2",
    )
    assert result == [
        {
            "ingredient": "小麦",
            "intolerance_level": "IgG抗体3级",
            "source_dish": "奶香意面",
        },
        {
            "ingredient": "牛奶",
            "intolerance_level": "1级",
            "source_dish": "奶香意面",
        },
    ]
