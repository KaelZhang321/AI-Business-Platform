from __future__ import annotations

import pytest

from app.services.smart_meal_risk_service import (
    SmartMealRiskService,
    _extract_dish_ingredients,
)


class StubLLM:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    async def chat(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        return self.raw

    async def close(self) -> None:
        return None


class StubMysqlPools:
    def __init__(self) -> None:
        self.get_business_pool_calls = 0
        self.close_calls = 0

    async def get_business_pool(self):  # noqa: ANN201
        self.get_business_pool_calls += 1
        return object()

    async def close(self) -> None:
        self.close_calls += 1


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
        return ["西兰花（2级）"]

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
async def test_close_does_not_close_shared_mysql_pools() -> None:
    pools = StubMysqlPools()
    service = SmartMealRiskService(llm_service=StubLLM("{}"), mysql_pools=pools)

    await service.close()

    assert pools.close_calls == 0


@pytest.mark.asyncio
async def test_warmup_uses_shared_business_pool() -> None:
    pools = StubMysqlPools()
    service = SmartMealRiskService(llm_service=StubLLM("{}"), mysql_pools=pools)

    await service.warmup()

    assert pools.get_business_pool_calls == 1


@pytest.mark.asyncio
async def test_close_closes_owned_mysql_pools() -> None:
    service = SmartMealRiskService(llm_service=StubLLM("{}"))
    owned_pools = StubMysqlPools()
    service._mysql_pools = owned_pools
    service._owned_mysql_pools = True

    await service.close()

    assert owned_pools.close_calls == 1


@pytest.mark.asyncio
async def test_identify_risks_fallback_to_rule_match_when_llm_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService(llm_service=StubLLM("not json"))

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["小麦（IgG抗体3级）", "牛奶（1级）"]

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


def test_extract_dish_ingredients_from_ingredient_json() -> None:
    rows = _extract_dish_ingredients(
        dish_name="清蒸香菇鸡腿肉",
        ingredient_json=[
            {"seqNo": 1, "ingredientName": "鸡腿肉", "ingredientCategory": "肉类"},
            {"seqNo": 2, "ingredientName": "香菇", "ingredientCategory": "菌菇类"},
            {"seqNo": 3, "ingredientName": "", "ingredientCategory": "蔬菜"},
            {"seqNo": 4, "ingredientCategory": "蔬菜"},
        ],
    )
    assert rows == [
        {
            "dish_name": "清蒸香菇鸡腿肉",
            "ingredient_name": "鸡腿肉",
            "ingredient_category": "肉类",
        },
        {
            "dish_name": "清蒸香菇鸡腿肉",
            "ingredient_name": "香菇",
            "ingredient_category": "菌菇类",
        },
    ]


def test_extract_dish_ingredients_handles_invalid_payload() -> None:
    assert _extract_dish_ingredients(dish_name="A", ingredient_json="invalid-json") == []
    assert _extract_dish_ingredients(dish_name="A", ingredient_json="") == []
    assert _extract_dish_ingredients(dish_name="A", ingredient_json=None) == []
