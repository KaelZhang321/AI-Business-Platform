from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import smart_meal as smart_meal_route


class StubSmartMealRiskService:
    async def identify_risks(
        self,
        *,
        id_card_no: str,
        sex: str,
        age: int,
        meal_type: list[str],
        reservation_date: str,
        package_code: str,
        trace_id: str | None,
    ) -> list[dict[str, str]]:
        assert id_card_no == "110101199001011234"
        assert sex == "男"
        assert age == 36
        assert meal_type == ["BREAKFAST", "LUNCH"]
        assert reservation_date == "2030-01-07"
        assert package_code == "TC202604180001"
        assert trace_id == "trace-001"
        return [
            {
                "ingredient": "西兰花",
                "intolerance_level": "2级",
                "source_dish": "蒜蓉西兰花",
            }
        ]


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(smart_meal_route.router, prefix="/api/v1")
    return app


def test_smart_meal_route_returns_envelope(monkeypatch) -> None:
    monkeypatch.setattr(smart_meal_route, "_service", StubSmartMealRiskService())
    client = TestClient(create_test_app())

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "sex": "男",
            "age": 36,
            "meal_type": ["BREAKFAST", "LUNCH"],
            "reservation_date": "2030-01-07",
            "package_code": "TC202604180001",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    assert payload["data"] == [
        {
            "ingredient": "西兰花",
            "intolerance_level": "2级",
            "source_dish": "蒜蓉西兰花",
        }
    ]
