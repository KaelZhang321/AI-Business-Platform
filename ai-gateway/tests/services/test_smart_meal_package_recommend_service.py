from __future__ import annotations

from datetime import datetime, timedelta

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

    async def stub_query_candidates_by_meal_type(**kwargs):  # noqa: ANN003
        return []

    monkeypatch.setattr(service, "_safe_fetch_diagnoses", stub_safe_fetch_diagnoses)
    monkeypatch.setattr(service, "_safe_fetch_intolerance_terms", stub_safe_fetch_intolerance_terms)
    monkeypatch.setattr(service, "_query_candidates_by_meal_type", stub_query_candidates_by_meal_type)

    result = await service.recommend_packages(
        id_card_no="110101199001011234",
        meal_type="LUNCH",
        age=52,
        sex="男",
        health_tags=["慢病管理"],
        diet_preferences=["清淡"],
        dietary_restrictions=["花生过敏"],
        abnormal_indicators=[{"type": "blood_glucose", "value": 11.2, "unit": "mmol/L"}],
        trace_id="trace-service-1",
    )

    assert result == []


def test_detect_high_risk_types_uses_thresholds() -> None:
    high_risk_types = _detect_high_risk_types(
        [
            {"type": "blood_glucose", "value": 11.2},
            {"type": "blood_lipid", "value": 5.9},
            {"type": "kidney_function", "value": 201},
        ]
    )
    assert high_risk_types == {"blood_glucose", "kidney_function"}


def test_rerank_respects_tie_breaking_and_top3_limit() -> None:
    service = SmartMealPackageRecommendService(mysql_pools=StubMysqlPools())

    candidates = [
        _build_scored(package_code="PKG_B", package_type="RECOVERY", score=85.0),
        _build_scored(package_code="PKG_A", package_type="RECOVERY", score=85.0),
        _build_scored(package_code="PKG_C", package_type="STANDARD", score=84.0),
        _build_scored(package_code="PKG_D", package_type="STANDARD", score=83.0),
    ]

    reranked = service._rerank_candidates(scored_candidates=candidates, behavior_signals=[])

    assert len(reranked) == 3
    # PKG_A / PKG_B 同分时按 package_code 升序稳定输出。
    assert reranked[0].package.package_code == "PKG_A"


def _build_scored(*, package_code: str, package_type: str, score: float):
    """构造重排测试用评分对象。

    功能：
        统一测试数据构造方式，避免每个测试重复拼装内部 dataclass，降低维护成本。
    """

    from app.services.smart_meal_package_recommend_service import _PackageCandidate, _ScoredPackage

    candidate = _PackageCandidate(
        package_code=package_code,
        package_name=package_code,
        package_type=package_type,
        meal_type="LUNCH",
        create_time=datetime.now() - timedelta(days=30),
        dish_names={"菜品A"},
        ingredient_names={"食材A"},
    )
    return _ScoredPackage(package=candidate, match_score=score)
