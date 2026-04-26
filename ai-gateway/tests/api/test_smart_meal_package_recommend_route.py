from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import smart_meal as smart_meal_route


class StubSmartMealPackageRecommendService:
    """套餐推荐路由测试桩。

    功能：
        用于验证路由层参数透传与 envelope 结构，避免测试耦合到数据库或外部接口。
    """

    async def recommend_packages(
        self,
        *,
        id_card_no: str,
        age: int | None,
        sex: str | None,
        health_tags: list[str],
        diet_preferences: list[str],
        dietary_restrictions: list[str],
        abnormal_indicators: dict[str, list[str]],
        trace_id: str | None,
    ) -> list[dict[str, str | float]]:
        assert id_card_no == "110101199001011234"
        assert age == 52
        assert sex == "男"
        assert health_tags == ["慢病管理"]
        assert diet_preferences == ["清淡"]
        assert dietary_restrictions == ["花生过敏"]
        assert abnormal_indicators == {
            "血糖异常": ["糖化HbA1c升高", "空腹血糖8.3"],
            "体重": ["超重"],
            "血脂异常": ["甘油三酯升高", "HDL-C升高"],
        }
        assert trace_id == "trace-002"
        return [
            {
                "package_code": "PKG_LUNCH_1024",
                "package_name": "心血管专研餐-康复型",
                "match_score": 92.37,
                "reason": "适合慢病管理与清淡偏好。",
            },
            {
                "package_code": "PKG_LUNCH_0881",
                "package_name": "控糖优蛋白午餐A",
                "match_score": 88.14,
                "reason": "更贴近控糖与高蛋白方向。",
            },
        ]


class StubSmartMealPackageRecommendEmptyService:
    async def recommend_packages(self, **kwargs):  # noqa: ANN003
        return []


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(smart_meal_route.router, prefix="/api/v1")
    return app


def test_smart_meal_package_recommend_route_returns_envelope(monkeypatch) -> None:
    monkeypatch.setattr(smart_meal_route, "_package_recommend_service", StubSmartMealPackageRecommendService())
    client = TestClient(create_test_app())

    response = client.post(
        "/api/v1/smart-meal/package-recommend",
        headers={"X-Trace-Id": "trace-002"},
        json={
            "id_card_no": "110101199001011234",
            "age": 52,
            "sex": "男",
            "health_tags": ["慢病管理"],
            "diet_preferences": ["清淡"],
            "dietary_restrictions": ["花生过敏"],
            "abnormal_indicators": {
                "血糖异常": ["糖化HbA1c升高", "空腹血糖8.3"],
                "体重": ["超重"],
                "血脂异常": ["甘油三酯升高", "HDL-C升高"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    assert payload["data"] == [
        {
            "package_code": "PKG_LUNCH_1024",
            "package_name": "心血管专研餐-康复型",
            "match_score": 92.37,
            "reason": "适合慢病管理与清淡偏好。",
        },
        {
            "package_code": "PKG_LUNCH_0881",
            "package_name": "控糖优蛋白午餐A",
            "match_score": 88.14,
            "reason": "更贴近控糖与高蛋白方向。",
        },
    ]


def test_smart_meal_package_recommend_route_returns_empty_contract(monkeypatch) -> None:
    monkeypatch.setattr(smart_meal_route, "_package_recommend_service", StubSmartMealPackageRecommendEmptyService())
    client = TestClient(create_test_app())

    response = client.post(
        "/api/v1/smart-meal/package-recommend",
        json={
            "id_card_no": "110101199001011234",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "当前条件下暂无可推荐套餐",
        "data": [],
    }
