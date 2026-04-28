from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.dependencies import get_transcript_extract_service
from app.api.routes import transcript_extract as transcript_extract_route
from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas import TranscriptExtractData


class StubTranscriptExtractService:
    async def extract(self, *, task_code: str, transcript: str) -> TranscriptExtractData:
        assert task_code == "task1"
        assert transcript == "客户说最近睡眠差"
        return TranscriptExtractData(
            task_code=task_code,
            service_code="transcript.extract.task1",
            result={"summary": "ok", "nextAction": "follow-up"},
        )

    async def close(self) -> None:
        return None


class StubFailingTranscriptExtractService:
    async def extract(self, *, task_code: str, transcript: str) -> TranscriptExtractData:
        del task_code, transcript
        raise BusinessError(ErrorCode.BAD_REQUEST, "unsupported taskCode: unknown")

    async def close(self) -> None:
        return None


def create_test_app() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(BusinessError)
    async def business_error_handler(request, exc: BusinessError):  # noqa: ANN001
        return JSONResponse(
            status_code=400,
            content={"code": exc.code, "message": exc.detail, "data": None},
        )

    app.include_router(transcript_extract_route.router, prefix="/api/v1")
    return app


def test_transcript_extract_route_returns_camel_case_response() -> None:
    app = create_test_app()
    app.dependency_overrides[get_transcript_extract_service] = lambda: StubTranscriptExtractService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/transcriptExtract",
        json={
            "taskCode": "task1",
            "transcript": "客户说最近睡眠差",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    assert payload["data"] == {
        "taskCode": "task1",
        "serviceCode": "transcript.extract.task1",
        "result": {"summary": "ok", "nextAction": "follow-up"},
    }
    app.dependency_overrides.clear()


def test_transcript_extract_route_accepts_snake_case_request() -> None:
    app = create_test_app()
    app.dependency_overrides[get_transcript_extract_service] = lambda: StubTranscriptExtractService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/transcriptExtract",
        json={
            "task_code": "task1",
            "transcript": "客户说最近睡眠差",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["taskCode"] == "task1"
    app.dependency_overrides.clear()


def test_transcript_extract_route_returns_error_envelope() -> None:
    app = create_test_app()
    app.dependency_overrides[get_transcript_extract_service] = lambda: StubFailingTranscriptExtractService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/transcriptExtract",
        json={
            "taskCode": "unknown",
            "transcript": "客户说最近睡眠差",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": ErrorCode.BAD_REQUEST.code,
        "message": "unsupported taskCode: unknown",
        "data": None,
    }
    app.dependency_overrides.clear()
