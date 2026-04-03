from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import bi as bi_routes


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(bi_routes.router, prefix="/api/v1")
    app.dependency_overrides[bi_routes.get_bi_db] = lambda: object()
    return app


def test_kpi_overview_route_returns_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        bi_routes,
        "get_kpi_overview",
        lambda db: {
            "registered_customers": {"label": "报名人数", "value": 128, "unit": "人", "prefix": ""},
            "arrived_customers": {"label": "到场人数", "value": 96, "unit": "人", "prefix": ""},
            "deal_amount": {"label": "成交金额", "value": 320.5, "unit": "万元", "prefix": ""},
            "consumed_budget": {"label": "消耗预算", "value": 80, "unit": "万元", "prefix": ""},
            "received_amount": {"label": "回款金额", "value": 210, "unit": "万元", "prefix": ""},
            "roi": {"label": "ROI", "value": 1.75, "unit": "", "prefix": ""},
        },
    )
    client = TestClient(create_test_app())

    response = client.get("/api/v1/bi/kpi/overview")

    assert response.status_code == 200
    assert response.json()["registered_customers"]["value"] == 128.0


def test_registration_chart_route_returns_chart_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        bi_routes,
        "get_region_level_chart",
        lambda db: [
            {
                "region": "华东",
                "real_identity": "千万",
                "register_count": 12,
                "arrive_count": 10,
            }
        ],
    )
    client = TestClient(create_test_app())

    response = client.get("/api/v1/bi/registration/chart")

    assert response.status_code == 200
    assert response.json() == [
        {
            "region": "华东",
            "real_identity": "千万",
            "register_count": 12,
            "arrive_count": 10,
        }
    ]


def test_registration_detail_route_passes_filters(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_get_registration_detail(db, region: str | None, level: str | None):
        observed["db"] = db
        observed["region"] = region
        observed["level"] = level
        return [
            {
                "customer_name": "张三",
                "sign_in_status": "已签到",
                "customer_category": "A类",
                "real_identity": "千万",
                "attendee_role": "院长",
                "store_name": "上海店",
                "region": "华东",
            }
        ]

    monkeypatch.setattr(bi_routes, "get_registration_detail", fake_get_registration_detail)
    client = TestClient(create_test_app())

    response = client.get("/api/v1/bi/registration/detail?region=华东&level=千万")

    assert response.status_code == 200
    assert response.json()[0]["customer_name"] == "张三"
    assert observed["region"] == "华东"
    assert observed["level"] == "千万"


# ─────────────────────────────────────────────────────────────────────────────
# AI 问数 & 图表路由测试
# ─────────────────────────────────────────────────────────────────────────────

_FAKE_QUERY_RESULT = {
    "sql": "SELECT 1",
    "answer": "共 1 条数据。",
    "columns": ["total"],
    "rows": [{"total": 1}],
    "chart": None,
    "domain": "meeting_bi",
}


def test_bi_ai_query_returns_response(monkeypatch) -> None:
    """POST /bi/ai/query 应返回 200 并包含 sql/answer 字段。"""
    from app.models.schemas import QueryDomain, Text2SQLResponse

    fake_result = Text2SQLResponse(
        sql="SELECT 1",
        explanation="ok",
        domain=QueryDomain.MEETING_BI,
        answer="共 1 条数据。",
        results=[{"total": 1}],
        chart_spec={
            "chart_type": "bar",
            "categories": ["报名客户"],
            "series": [{"name": "total", "data": [1]}],
            "chart_id": "chart_123",
        },
    )

    class FakeExecutor:
        async def query(self, question, *, conversation_id=None, context=None):
            return fake_result

    import app.api.routes.bi as bi_module
    monkeypatch.setattr(bi_module, "MeetingBIQueryExecutor", FakeExecutor, raising=False)

    client = TestClient(create_test_app())
    response = client.post("/api/v1/bi/ai/query", json={"question": "报名了多少客户？"})

    assert response.status_code == 200
    body = response.json()
    assert body["sql"] == "SELECT 1"
    assert body["answer"] == "共 1 条数据。"
    assert body["rows"] == [{"total": 1}]
    assert body["chart"]["chart_id"] == "chart_123"


def test_bi_ai_query_stream_returns_sse(monkeypatch) -> None:
    """POST /bi/ai/query/stream 应返回 text/event-stream 响应。"""
    import json

    class FakeExecutor:
        async def stream(self, question, *, conversation_id=None):
            yield {"event": "answer", "data": json.dumps({"answer": "ok"}, ensure_ascii=False)}

    import app.api.routes.bi as bi_module
    monkeypatch.setattr(bi_module, "MeetingBIQueryExecutor", FakeExecutor, raising=False)

    client = TestClient(create_test_app())
    response = client.post(
        "/api/v1/bi/ai/query/stream",
        json={"question": "签到率是多少？"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_bi_get_chart_returns_data(monkeypatch) -> None:
    """GET /bi/chart/{chart_id} 存在时返回 200 + data。"""
    fake_chart = {"chart_type": "bar", "categories": ["A", "B"], "series": []}

    async def fake_get_chart(chart_id: str):
        return fake_chart

    import app.api.routes.bi as bi_module
    monkeypatch.setattr(bi_module, "get_chart", fake_get_chart)
    client = TestClient(create_test_app())
    response = client.get("/api/v1/bi/chart/abc123def456")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["chart_type"] == "bar"


def test_bi_get_chart_returns_404(monkeypatch) -> None:
    """GET /bi/chart/{chart_id} 不存在时返回 404。"""

    async def fake_get_chart(chart_id: str):
        return None

    import app.api.routes.bi as bi_module
    monkeypatch.setattr(bi_module, "get_chart", fake_get_chart)
    client = TestClient(create_test_app())
    response = client.get("/api/v1/bi/chart/nonexistent")

    assert response.status_code == 404
