from __future__ import annotations

import json

import pytest

from app.services.smart_meal_risk_service import SmartMealRiskService


class StubMysqlPools:
    def __init__(self) -> None:
        self.get_business_pool_calls = 0
        self.close_calls = 0

    async def get_business_pool(self):  # noqa: ANN201
        self.get_business_pool_calls += 1
        return object()

    async def close(self) -> None:
        self.close_calls += 1


@pytest.fixture(autouse=True)
def stub_query_meal_dishes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stub(self: SmartMealRiskService, *, campus_id: str, package_ingredients: list[dict[str, str]]):  # noqa: ANN001
        _ = campus_id
        rows: list[dict[str, str]] = []
        for item in package_ingredients:
            dish_code = item.get("dish_code") or ""
            dish_name = item.get("dish_name") or ""
            rows.append(
                {
                    "campus_id": "TJ-001",
                    "dish_code": dish_code,
                    "dish_name": dish_name,
                    "ingredient_json": json.dumps(
                        [
                            {
                                "ingredientName": dish_name,
                                "ingredientCatagory": dish_name,
                            }
                        ],
                        ensure_ascii=False,
                    ),
                }
            )
        return rows

    monkeypatch.setattr(SmartMealRiskService, "_query_meal_dishes", _stub)


@pytest.mark.asyncio
async def test_identify_risks_uses_rule_output_with_dishes(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["西兰花特异性IgG抗体（低）:2级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"},
            {"dish_code": "DISH-002", "dish_name": "清炒时蔬"},
        ],
        trace_id="trace-1",
    )
    assert result == [
        {
            "ingredient": "西兰花",
            "intolerance_level": "2级",
            "dishes": [
                {"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_passes_normalized_snapshot_to_query_meal_dishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["西兰花:2级"]

    captured: dict[str, object] = {}

    async def stub_query_meal_dishes(**kwargs):  # noqa: ANN003
        captured["campus_id"] = kwargs.get("campus_id")
        captured["package_ingredients"] = kwargs.get("package_ingredients")
        return [
            {
                "campus_id": "TJ-001",
                "dish_code": "DISH-001",
                "dish_name": "蒜蓉西兰花",
                "ingredient_json": [{"ingredientName": "西兰花", "ingredientCatagory": "蔬菜"}],
            }
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)
    monkeypatch.setattr(service, "_query_meal_dishes", stub_query_meal_dishes)

    await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": None, "dish_name": "应跳过"},
            {"dish_code": "  ", "dish_name": "应跳过"},
            {"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"},
        ],
        trace_id="trace-query-1",
    )

    assert captured["campus_id"] == "TJ-001"
    assert captured["package_ingredients"] == [
        {"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"},
    ]


@pytest.mark.asyncio
async def test_close_does_not_close_shared_mysql_pools() -> None:
    pools = StubMysqlPools()
    service = SmartMealRiskService(mysql_pools=pools)

    await service.close()

    assert pools.close_calls == 0


@pytest.mark.asyncio
async def test_warmup_uses_shared_business_pool() -> None:
    pools = StubMysqlPools()
    service = SmartMealRiskService(mysql_pools=pools)

    await service.warmup()

    assert pools.get_business_pool_calls == 1


@pytest.mark.asyncio
async def test_close_closes_owned_mysql_pools() -> None:
    service = SmartMealRiskService()
    owned_pools = StubMysqlPools()
    service._mysql_pools = owned_pools
    service._owned_mysql_pools = True

    await service.close()

    assert owned_pools.close_calls == 1


@pytest.mark.asyncio
async def test_identify_risks_rule_match_with_cleaned_intolerance_items(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return [
            "小麦特异性IgG抗体（高）:IgG抗体3级",
            "牛奶-sIgE抗体升高:1级",
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-A", "dish_name": "小麦面包"},
            {"dish_code": "DISH-B", "dish_name": "牛奶燕麦"},
            {"dish_code": "DISH-C", "dish_name": "时蔬沙拉"},
        ],
        trace_id="trace-2",
    )
    assert result == [
        {
            "ingredient": "小麦",
            "intolerance_level": "IgG抗体3级",
            "dishes": [{"dish_code": "DISH-A", "dish_name": "小麦面包"}],
        },
        {
            "ingredient": "牛奶",
            "intolerance_level": "1级",
            "dishes": [{"dish_code": "DISH-B", "dish_name": "牛奶燕麦"}],
        },
    ]


@pytest.mark.asyncio
async def test_identify_risks_skips_snapshot_item_without_dish_code(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["西兰花（2级）"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "", "dish_name": "蒜蓉西兰花"},
            {"dish_code": "DISH-002", "dish_name": "清炒时蔬"},
        ],
        trace_id="trace-3",
    )
    assert result == []


@pytest.mark.asyncio
async def test_identify_risks_parses_colon_and_removes_parentheses(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["芒果特异性IgG抗体（风险提示）:2级", "斑节虾-sIgE抗体升高（轻度）:1级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-M", "dish_name": "芒果沙拉"},
            {"dish_code": "DISH-S", "dish_name": "白灼斑节虾"},
        ],
        trace_id="trace-4",
    )
    assert sorted(result, key=lambda item: item["ingredient"]) == sorted(
        [
        {
            "ingredient": "芒果",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-M", "dish_name": "芒果沙拉"}],
        },
        {
            "ingredient": "斑节虾",
            "intolerance_level": "1级",
            "dishes": [{"dish_code": "DISH-S", "dish_name": "白灼斑节虾"}],
        },
        ],
        key=lambda item: item["ingredient"],
    )


@pytest.mark.asyncio
async def test_identify_risks_removes_mixed_parentheses_and_bracket_chars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["芒果（风险提示):2级", "斑节虾(轻度）:1级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-M", "dish_name": "芒果沙拉"},
            {"dish_code": "DISH-S", "dish_name": "白灼斑节虾"},
        ],
        trace_id="trace-4b",
    )
    assert sorted(result, key=lambda item: item["ingredient"]) == sorted(
        [
            {
                "ingredient": "芒果",
                "intolerance_level": "2级",
                "dishes": [{"dish_code": "DISH-M", "dish_name": "芒果沙拉"}],
            },
            {
                "ingredient": "斑节虾",
                "intolerance_level": "1级",
                "dishes": [{"dish_code": "DISH-S", "dish_name": "白灼斑节虾"}],
            },
        ],
        key=lambda item: item["ingredient"],
    )


@pytest.mark.asyncio
async def test_identify_risks_ignores_empty_ingredient_after_bracket_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["（仅提示）:2级", "(仅提示):1级", "（ ）:3级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-M", "dish_name": "芒果沙拉"},
            {"dish_code": "DISH-S", "dish_name": "白灼斑节虾"},
        ],
        trace_id="trace-5",
    )
    assert result == []


@pytest.mark.asyncio
async def test_identify_risks_sets_unknown_level_when_colon_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["牛奶-sIgE抗体升高（轻度）"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-6",
    )
    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "未知",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_splits_intolerance_text_on_first_colon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["鲈鱼:1级:补充说明"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-F", "dish_name": "清蒸鲈鱼"},
        ],
        trace_id="trace-7",
    )
    assert result == [
        {
            "ingredient": "鲈鱼",
            "intolerance_level": "1级:补充说明",
            "dishes": [{"dish_code": "DISH-F", "dish_name": "清蒸鲈鱼"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_keeps_processing_when_only_dish_name_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["西兰花特异性IgG抗体（高）:2级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-EMPTY-NAME", "dish_name": None},
            {"dish_code": "DISH-OK", "dish_name": "蒜蓉西兰花"},
            {"dish_code": None, "dish_name": "蒜蓉西兰花"},
        ],
        trace_id="trace-8",
    )
    assert result == [
        {
            "ingredient": "西兰花",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-OK", "dish_name": "蒜蓉西兰花"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_supports_full_width_colon_separator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["鸡蛋特异性IgG抗体（提示）：2级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-E", "dish_name": "番茄炒鸡蛋"},
        ],
        trace_id="trace-9",
    )
    assert result == [
        {
            "ingredient": "鸡蛋",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-E", "dish_name": "番茄炒鸡蛋"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_ignores_empty_ingredient_with_full_width_colon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["（仅提示）：2级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-E", "dish_name": "番茄炒鸡蛋"},
        ],
        trace_id="trace-10",
    )
    assert result == []


@pytest.mark.asyncio
async def test_identify_risks_ignores_empty_ingredient_with_half_width_colon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["(仅提示):2级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-E", "dish_name": "番茄炒鸡蛋"},
        ],
        trace_id="trace-11",
    )
    assert result == []


@pytest.mark.asyncio
async def test_identify_risks_returns_items_sorted_by_ingredient(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return [
            "鲈鱼:1级",
            "牛奶:2级",
            "芒果:3级",
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-F", "dish_name": "清蒸鲈鱼"},
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
            {"dish_code": "DISH-M", "dish_name": "芒果沙拉"},
        ],
        trace_id="trace-12",
    )

    assert [item["ingredient"] for item in result] == ["牛奶", "芒果", "鲈鱼"]


@pytest.mark.asyncio
async def test_identify_risks_deduplicates_and_sorts_dishes(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["西兰花:2级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-B", "dish_name": "西兰花炒虾仁"},
            {"dish_code": "DISH-A", "dish_name": "蒜蓉西兰花"},
            {"dish_code": "DISH-A", "dish_name": "蒜蓉西兰花"},
        ],
        trace_id="trace-13",
    )

    assert result == [
        {
            "ingredient": "西兰花",
            "intolerance_level": "2级",
            "dishes": [
                {"dish_code": "DISH-A", "dish_name": "蒜蓉西兰花"},
                {"dish_code": "DISH-B", "dish_name": "西兰花炒虾仁"},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_prefers_known_level_over_unknown_for_same_ingredient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return [
            "牛奶-sIgE抗体升高（轻度）",
            "牛奶:2级",
            "牛奶:1级",
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-14",
    )

    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_keeps_known_level_when_unknown_appears_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return [
            "牛奶:2级",
            "牛奶-sIgE抗体升高（轻度）",
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-15",
    )

    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_falls_back_to_unknown_when_level_after_colon_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["牛奶:"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-16",
    )

    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "未知",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_falls_back_to_unknown_when_level_after_full_width_colon_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["牛奶："]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-17",
    )

    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "未知",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_trims_whitespace_around_colon_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["  牛奶特异性IgG抗体（轻度）  :   2级   "]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-18",
    )

    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_trims_whitespace_around_full_width_colon_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["  牛奶特异性IgG抗体（轻度）  ：   2级   "]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-19",
    )

    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_cleans_combined_igg_and_sige_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["牛奶特异性IgG抗体-sIgE抗体升高（提示）:1级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-20",
    )

    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "1级",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_skips_empty_ingredient_item_but_keeps_other_valid_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return [
            "（仅提示）:2级",
            "牛奶:1级",
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-N", "dish_name": "牛奶燕麦"},
        ],
        trace_id="trace-21",
    )

    assert result == [
        {
            "ingredient": "牛奶",
            "intolerance_level": "1级",
            "dishes": [{"dish_code": "DISH-N", "dish_name": "牛奶燕麦"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_matches_ingredient_case_insensitively(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["MILK:1级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-EN", "dish_name": "milk tea"},
        ],
        trace_id="trace-22",
    )

    assert result == [
        {
            "ingredient": "MILK",
            "intolerance_level": "1级",
            "dishes": [{"dish_code": "DISH-EN", "dish_name": "milk tea"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_does_not_match_single_char_ingredient_by_containment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["鱼:1级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-F", "dish_name": "清蒸鲈鱼"},
        ],
        trace_id="trace-23",
    )

    assert result == []


@pytest.mark.asyncio
async def test_identify_risks_matches_single_char_ingredient_on_exact_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["鱼:1级"]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[
            {"dish_code": "DISH-F", "dish_name": "鱼"},
        ],
        trace_id="trace-24",
    )

    assert result == [
        {
            "ingredient": "鱼",
            "intolerance_level": "1级",
            "dishes": [{"dish_code": "DISH-F", "dish_name": "鱼"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_matches_on_ingredient_category(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["海鲜:2级"]

    async def stub_query_meal_dishes(**kwargs):  # noqa: ANN003
        return [
            {
                "campus_id": "TJ-001",
                "dish_code": "DISH-S",
                "dish_name": "白灼斑节虾",
                "ingredient_json": [
                    {"ingredientName": "斑节虾", "ingredientCatagory": "海鲜"},
                    {"ingredientName": "食盐", "ingredientCatagory": "调味料"},
                ],
            }
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)
    monkeypatch.setattr(service, "_query_meal_dishes", stub_query_meal_dishes)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[{"dish_code": "DISH-S", "dish_name": "白灼斑节虾"}],
        trace_id="trace-cat-1",
    )
    assert result == [
        {
            "ingredient": "海鲜",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-S", "dish_name": "白灼斑节虾"}],
        }
    ]


@pytest.mark.asyncio
async def test_identify_risks_prefers_known_level_in_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["海鲜:", "海鲜:2级"]

    async def stub_query_meal_dishes(**kwargs):  # noqa: ANN003
        return [
            {
                "campus_id": "TJ-001",
                "dish_code": "DISH-S",
                "dish_name": "白灼斑节虾",
                "ingredient_json": [{"ingredientName": "斑节虾", "ingredientCatagory": "海鲜"}],
            }
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)
    monkeypatch.setattr(service, "_query_meal_dishes", stub_query_meal_dishes)

    result = await service.identify_risks(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_snapshot=[{"dish_code": "DISH-S", "dish_name": "白灼斑节虾"}],
        trace_id="trace-cat-2",
    )
    assert result == [
        {
            "ingredient": "海鲜",
            "intolerance_level": "2级",
            "dishes": [{"dish_code": "DISH-S", "dish_name": "白灼斑节虾"}],
        }
    ]
