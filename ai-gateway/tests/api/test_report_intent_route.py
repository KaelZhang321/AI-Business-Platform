from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_report_intent_service
from app.api.routes import report_intent as report_intent_route
from app.services.report_intent_service import ReportIntentResolution


class StubReportIntentService:
    """报告意图路由测试桩。"""

    async def resolve(self, *, query: str) -> ReportIntentResolution:
        if query == "查一般体征":
            return ReportIntentResolution(target_id="vitals", focused_metric=None, target_year=None)
        if query == "糖化血红蛋白":
            return ReportIntentResolution(
                target_id="metric-focus",
                focused_metric="糖化血红蛋白",
                target_year=None,
            )
        return ReportIntentResolution(target_id="overview", focused_metric=None, target_year=None)


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(report_intent_route.router, prefix="/api/v1")
    app.dependency_overrides[get_report_intent_service] = lambda: StubReportIntentService()
    return app


def test_report_intent_route_returns_vitals() -> None:
    client = TestClient(create_test_app())
    response = client.post("/api/v1/report-intent/dialog", json={"query": "查一般体征"})
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {
            "targetId": "vitals",
            "focusedMetric": None,
            "targetYear": None,
        },
    }


def test_report_intent_route_returns_metric_focus() -> None:
    client = TestClient(create_test_app())
    response = client.post("/api/v1/report-intent/dialog", json={"query": "糖化血红蛋白"})
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {
            "targetId": "metric-focus",
            "focusedMetric": "糖化血红蛋白",
            "targetYear": None,
        },
    }


def test_report_intent_route_validation_error_for_empty_query() -> None:
    client = TestClient(create_test_app())
    response = client.post("/api/v1/report-intent/dialog", json={"query": ""})
    assert response.status_code == 422
