from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mcp_server import server as mcp_server_module


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.mount("/mcp", mcp_server_module.create_mcp_http_app())
    return app


def test_mcp_returns_503_when_api_key_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(mcp_server_module.settings, "mcp_api_key", "")

    client = TestClient(_create_test_app())
    response = client.post("/mcp")

    assert response.status_code == 503
    assert response.json() == {"error": "mcp_api_key_not_configured"}


def test_mcp_returns_401_when_api_key_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(mcp_server_module.settings, "mcp_api_key", "expected-key")

    client = TestClient(_create_test_app())
    response = client.post("/mcp", headers={"X-API-Key": "wrong-key"})

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
