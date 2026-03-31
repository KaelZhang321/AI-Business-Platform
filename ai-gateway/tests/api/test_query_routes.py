from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import query as query_routes
from app.models.schemas import QueryDomain, Text2SQLResponse


class StubText2SQLService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def query(
        self,
        *,
        question: str,
        database: str = "default",
        domain: QueryDomain | str | None = None,
        conversation_id: str | None = None,
    ) -> Text2SQLResponse:
        self.calls.append(
            {
                "question": question,
                "database": database,
                "domain": domain,
                "conversation_id": conversation_id,
            }
        )
        return Text2SQLResponse(
            sql="SELECT 1 LIMIT 1",
            explanation="meeting bi query executed",
            domain=QueryDomain.MEETING_BI,
            answer="会议报名 128 人",
            results=[{"registered_customers": 128}],
        )


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(query_routes.router, prefix="/api/v1")
    return app


def test_text2sql_route_passes_explicit_domain(monkeypatch) -> None:
    stub = StubText2SQLService()
    monkeypatch.setattr(query_routes, "text2sql_service", stub)
    client = TestClient(create_test_app())

    response = client.post(
        "/api/v1/query/text2sql",
        json={
            "question": "分析会议报名人数",
            "database": "warehouse",
            "domain": "meeting_bi",
            "conversation_id": "conv-route",
        },
    )

    assert response.status_code == 200
    assert response.json()["domain"] == "meeting_bi"
    assert stub.calls == [
        {
            "question": "分析会议报名人数",
            "database": "warehouse",
            "domain": QueryDomain.MEETING_BI,
            "conversation_id": "conv-route",
        }
    ]
