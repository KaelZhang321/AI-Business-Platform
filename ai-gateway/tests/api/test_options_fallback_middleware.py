from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import options_fallback_middleware


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(options_fallback_middleware)

    @app.post("/api/v1/health-quadrant")
    async def health_quadrant() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_options_fallback_returns_200_for_non_preflight_options() -> None:
    client = TestClient(_create_test_app())

    response = client.options("/api/v1/health-quadrant")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-methods"] == "GET,POST,PUT,PATCH,DELETE,OPTIONS"


def test_options_fallback_keeps_standard_preflight_to_cors_middleware() -> None:
    client = TestClient(_create_test_app())

    response = client.options(
        "/api/v1/health-quadrant",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 200
    assert response.text == "OK"
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST" in response.headers["access-control-allow-methods"]

