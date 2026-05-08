from __future__ import annotations

import pytest

from app.services.smart_meal_package_recommend_service import (
    SmartMealPackageRecommendService,
    _detect_high_risk_types,
)


class StubMysqlPools:
    """推荐服务测试连接池桩。"""

    def __init__(self) -> None:
        self.get_ods_pool_calls = 0
        self.close_calls = 0

    async def get_ods_pool(self):  # noqa: ANN201
        self.get_ods_pool_calls += 1
        return object()

    async def close(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_warmup_uses_shared_ods_pool() -> None:
    pools = StubMysqlPools()
    service = SmartMealPackageRecommendService(mysql_pools=pools)

    await service.warmup()

    assert pools.get_ods_pool_calls == 1


@pytest.mark.asyncio
async def test_close_does_not_close_shared_mysql_pools() -> None:
    pools = StubMysqlPools()
    service = SmartMealPackageRecommendService(mysql_pools=pools)

    await service.close()

    assert pools.close_calls == 0


@pytest.mark.asyncio
async def test_close_closes_owned_mysql_pools() -> None:
    service = SmartMealPackageRecommendService()
    owned_pools = StubMysqlPools()
    service._mysql_pools = owned_pools
    service._owned_mysql_pools = True

    await service.close()

    assert owned_pools.close_calls == 1


@pytest.mark.asyncio
async def test_recommend_packages_returns_empty_when_no_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealPackageRecommendService(mysql_pools=StubMysqlPools())

    async def stub_safe_fetch_diagnoses(**kwargs):  # noqa: ANN003
        return [], "ok"

    async def stub_safe_fetch_intolerance_terms(**kwargs):  # noqa: ANN003
        return set(), "ok"

    async def stub_query_candidates(**kwargs):  # noqa: ANN003
        assert kwargs["campus_id"] == "TJ-001"
        assert kwargs["reservation_date"].strftime("%Y-%m-%d") == "2030-01-07"
        assert kwargs["meal_types"] == {"BREAKFAST", "LUNCH"}
        return []

    monkeypatch.setattr(service, "_safe_fetch_diagnoses", stub_safe_fetch_diagnoses)
    monkeypatch.setattr(service, "_safe_fetch_intolerance_terms", stub_safe_fetch_intolerance_terms)
    monkeypatch.setattr(service, "_query_candidates", stub_query_candidates)

    result = await service.recommend_packages(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_type=["BREAKFAST", "LUNCH"],
        reservation_date="2030-01-07",
        age=52,
        sex="男",
        health_tags=["慢病管理"],
        diet_preferences=["清淡"],
        dietary_restrictions=["花生过敏"],
        abnormal_indicators={"血糖异常": ["空腹血糖8.3"]},
        trace_id="trace-service-1",
    )

    assert result == []


def test_detect_high_risk_types_uses_category_mapping() -> None:
    high_risk_types = _detect_high_risk_types(
        {
            "血糖异常": ["空腹血糖8.3"],
            "血脂异常": ["甘油三酯升高"],
            "肾功": ["肌酐升高"],
            "体重": ["超重"],
        }
    )
    assert high_risk_types == {"blood_glucose", "blood_lipid", "kidney_function"}


@pytest.mark.asyncio
async def test_fetch_diagnoses_accepts_mixed_row_types(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealPackageRecommendService(mysql_pools=StubMysqlPools())

    class _StubResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "rows": [
                    {"label_value": "高血压", "record_date": "2026-04-01"},
                    "糖尿病",
                    {"diagnosis": "高血脂", "diagnosis_time": "2026-03-20"},
                ]
            }

    class _StubClient:
        async def get(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return _StubResponse()

    monkeypatch.setattr(service, "_get_http_client", lambda: _StubClient())

    signals = await service._fetch_diagnoses(id_card_no="enc-id-card", trace_id="trace-001")

    assert len(signals) == 3
    names = {signal.name for signal in signals}
    assert names == {"高血压", "糖尿病", "高血脂"}


def test_score_candidates_uses_trimmed_weights_without_behavior_features() -> None:
    service = SmartMealPackageRecommendService(mysql_pools=StubMysqlPools())
    from app.services.smart_meal_package_recommend_service import _DiagnosisSignal, _PackageCandidate

    candidates = [
        _PackageCandidate(
            package_code="PKG_B",
            package_name="控糖轻脂餐",
            package_type="RECOVERY",
            applicable_people="慢病管理人群",
            core_target="控糖",
            nutrition_feature="轻脂",
            dish_names={"低糖餐"},
            ingredient_names={"燕麦"},
        ),
        _PackageCandidate(
            package_code="PKG_A",
            package_name="控糖轻脂餐",
            package_type="RECOVERY",
            applicable_people="慢病管理人群",
            core_target="控糖",
            nutrition_feature="轻脂",
            dish_names={"低糖餐"},
            ingredient_names={"燕麦"},
        ),
    ]
    diagnoses = [_DiagnosisSignal(name="控糖轻脂餐", days_since=0)]

    scored = service._score_candidates(
        candidates=candidates,
        health_tags=["控糖"],
        diet_preferences=["轻脂"],
        abnormal_indicators={},
        diagnoses=diagnoses,
        age=66,
        sex="男",
    )

    assert len(scored) == 2
    assert scored[0]["package_code"] == "PKG_A"
    assert scored[0]["match_score"] == 100.0
    assert isinstance(scored[0]["reason"], str)


@pytest.mark.asyncio
async def test_recommend_packages_prefers_llm_rank_result(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealPackageRecommendService(mysql_pools=StubMysqlPools())

    async def stub_safe_fetch_diagnoses(**kwargs):  # noqa: ANN003
        return [], "ok"

    async def stub_safe_fetch_intolerance_terms(**kwargs):  # noqa: ANN003
        return set(), "ok"

    async def stub_query_candidates(**kwargs):  # noqa: ANN003
        from app.services.smart_meal_package_recommend_service import _PackageCandidate

        return [
            _PackageCandidate(
                package_code="PKG_A",
                package_name="套餐A",
                package_type="RECOVERY",
                applicable_people="慢病管理人群",
                core_target="控糖",
                nutrition_feature="清淡",
                dish_names={"菜品A"},
                ingredient_names={"食材A"},
            ),
            _PackageCandidate(
                package_code="PKG_B",
                package_name="套餐B",
                package_type="RECOVERY",
                applicable_people="慢病管理人群",
                core_target="控脂",
                nutrition_feature="低脂",
                dish_names={"菜品B"},
                ingredient_names={"食材B"},
            ),
        ]

    async def stub_rank_candidates_with_llm(**kwargs):  # noqa: ANN003
        return (
            [
                {
                    "package_code": "PKG_B",
                    "package_name": "套餐B",
                    "match_score": 91.2,
                    "reason": "更贴合当前诊断与营养目标。",
                }
            ],
            "ok",
            "",
        )

    monkeypatch.setattr(service, "_safe_fetch_diagnoses", stub_safe_fetch_diagnoses)
    monkeypatch.setattr(service, "_safe_fetch_intolerance_terms", stub_safe_fetch_intolerance_terms)
    monkeypatch.setattr(service, "_query_candidates", stub_query_candidates)
    monkeypatch.setattr(service, "_rank_candidates_with_llm", stub_rank_candidates_with_llm)

    result = await service.recommend_packages(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_type=["BREAKFAST", "LUNCH"],
        reservation_date="2030-01-07",
        age=52,
        sex="男",
        health_tags=["慢病管理"],
        diet_preferences=["清淡"],
        dietary_restrictions=[],
        abnormal_indicators={},
        trace_id="trace-service-llm",
    )

    assert result == [
        {
            "package_code": "PKG_B",
            "package_name": "套餐B",
            "match_score": 91.2,
            "reason": "更贴合当前诊断与营养目标。",
        }
    ]


@pytest.mark.asyncio
async def test_recommend_packages_falls_back_to_rule_rank_when_llm_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SmartMealPackageRecommendService(mysql_pools=StubMysqlPools())

    async def stub_safe_fetch_diagnoses(**kwargs):  # noqa: ANN003
        return [], "ok"

    async def stub_safe_fetch_intolerance_terms(**kwargs):  # noqa: ANN003
        return set(), "ok"

    async def stub_query_candidates(**kwargs):  # noqa: ANN003
        from app.services.smart_meal_package_recommend_service import _PackageCandidate

        return [
            _PackageCandidate(
                package_code="PKG_A",
                package_name="控糖轻脂餐",
                package_type="RECOVERY",
                applicable_people="慢病管理人群",
                core_target="控糖",
                nutrition_feature="清淡",
                dish_names={"低糖餐"},
                ingredient_names={"燕麦"},
            )
        ]

    async def stub_rank_candidates_with_llm(**kwargs):  # noqa: ANN003
        return None, "invalid_json", "llm_invalid_json"

    monkeypatch.setattr(service, "_safe_fetch_diagnoses", stub_safe_fetch_diagnoses)
    monkeypatch.setattr(service, "_safe_fetch_intolerance_terms", stub_safe_fetch_intolerance_terms)
    monkeypatch.setattr(service, "_query_candidates", stub_query_candidates)
    monkeypatch.setattr(service, "_rank_candidates_with_llm", stub_rank_candidates_with_llm)

    result = await service.recommend_packages(
        id_card_no="110101199001011234",
        campus_id="TJ-001",
        meal_type=["BREAKFAST", "LUNCH"],
        reservation_date="2030-01-07",
        age=52,
        sex="男",
        health_tags=["控糖"],
        diet_preferences=["清淡"],
        dietary_restrictions=[],
        abnormal_indicators={},
        trace_id="trace-service-fallback",
    )

    assert len(result) == 1
    assert result[0]["package_code"] == "PKG_A"
    assert result[0]["match_score"] == 52.0
    assert isinstance(result[0]["reason"], str)
