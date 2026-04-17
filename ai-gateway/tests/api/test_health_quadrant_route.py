from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import health_quadrant as health_quadrant_route


class StubHealthQuadrantService:
    async def query_quadrants(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_items: list[str],
        trace_id: str | None,
    ) -> dict:
        assert study_id == "1675218389653693282"
        assert quadrant_type == "exam"
        assert chief_complaint_items == ["夜间易醒", "睡眠障碍"]
        assert trace_id == "trace-001"
        assert len(single_exam_items) == 2
        assert single_exam_items[0]["itemId"] == "A1"
        assert single_exam_items[0]["itemText"] == "维生素D缺乏"
        assert single_exam_items[0]["abnormalIndicator"] == "维生素D偏低"
        return {
            "quadrants": [
                {
                    "q_code": "exam_q1_basic_screening",
                    "q_name": "第一象限（基础筛查）",
                    "abnormalIndicators": ["血脂异常"],
                    "recommendationPlans": ["基础异常复查包"],
                },
                {
                    "q_code": "exam_q2_imaging",
                    "q_name": "第二象限（影像评估）",
                    "abnormalIndicators": ["肺部CT：结节"],
                    "recommendationPlans": ["影像专科复核"],
                },
                {
                    "q_code": "exam_q3_deep_screening",
                    "q_name": "第三象限（专项深度筛查）",
                    "abnormalIndicators": ["建议进一步复查甲状腺"],
                    "recommendationPlans": ["终检意见专项深筛包"],
                },
                {
                    "q_code": "exam_q4_premium",
                    "q_name": "第四象限（丽滋特色项目）",
                    "abnormalIndicators": ["PET-MR 评估建议"],
                    "recommendationPlans": ["PET-MR 高端筛查评估"],
                },
            ],
            "fromCache": False,
        }

    async def confirm_quadrants(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_items: list[str],
        quadrants: list[dict],
        confirmed_by: str | None,
        trace_id: str | None,
    ) -> None:
        assert study_id == "1675218389653693282"
        assert quadrant_type == "exam"
        assert confirmed_by == "hello"
        assert trace_id == "trace-001"
        assert len(single_exam_items) == 2
        assert sorted(chief_complaint_items) == ["夜间易醒", "睡眠障碍"]
        assert len(quadrants) == 4


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_quadrant_route.router, prefix="/api/v1")
    return app


def test_health_quadrant_query_route_returns_unified_quadrants(monkeypatch) -> None:
    monkeypatch.setattr(health_quadrant_route, "health_quadrant_service", StubHealthQuadrantService())
    client = TestClient(create_test_app())

    response = client.post(
        "/api/v1/health-quadrant",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "sex": "男",
            "study_id": "1675218389653693282",
            "quadrant_type": "exam",
            "single_exam_items": [
                {"itemId": "A1", "itemText": "维生素D缺乏", "abnormalIndicator": "维生素D偏低"},
                {"itemId": "A2", "itemText": "甲状腺结节", "abnormalIndicator": "结节"},
            ],
            "chief_complaint_items": ["睡眠障碍", "夜间易醒"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "study_id" not in payload
    assert "source_data" not in payload
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    assert len(payload["data"]["quadrants"]) == 4
    assert payload["data"]["quadrants"][0]["abnormal_indicators"] == ["血脂异常"]
    assert payload["data"]["quadrants"][0]["recommendation_plans"] == ["基础异常复查包"]


def test_health_quadrant_confirm_route_persists_payload(monkeypatch) -> None:
    monkeypatch.setattr(health_quadrant_route, "health_quadrant_service", StubHealthQuadrantService())
    client = TestClient(create_test_app())

    response = client.post(
        "/api/v1/health-quadrant/confirm",
        headers={"X-User-Id": "hello", "X-Trace-Id": "trace-001"},
        json={
            "study_id": "1675218389653693282",
            "quadrant_type": "exam",
            "single_exam_items": [
                {"itemId": "A1", "itemText": "维生素D缺乏", "abnormalIndicator": "维生素D偏低"},
                {"itemId": "A2", "itemText": "甲状腺结节", "abnormalIndicator": "结节"},
            ],
            "chief_complaint_items": ["睡眠障碍", "夜间易醒"],
            "quadrants": [
                {
                    "q_code": "exam_q1_basic_screening",
                    "q_name": "第一象限（基础筛查）",
                    "abnormal_indicators": ["血脂异常"],
                    "recommendation_plans": ["基础异常复查包"],
                },
                {
                    "q_code": "exam_q2_imaging",
                    "q_name": "第二象限（影像评估）",
                    "abnormal_indicators": [],
                    "recommendation_plans": ["影像专科复核"],
                },
                {
                    "q_code": "exam_q3_deep_screening",
                    "q_name": "第三象限（专项深度筛查）",
                    "abnormal_indicators": [],
                    "recommendation_plans": ["终检意见专项深筛包"],
                },
                {
                    "q_code": "exam_q4_premium",
                    "q_name": "第四象限（丽滋特色项目）",
                    "abnormal_indicators": [],
                    "recommendation_plans": ["PET-MR 高端筛查评估"],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"code": 0, "message": "ok", "data": {"success": True}}
