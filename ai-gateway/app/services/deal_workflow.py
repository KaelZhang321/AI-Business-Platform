from collections.abc import AsyncGenerator

from app.models.schemas.deal import DealRequest, DealResponse


class DealWorkflow:
    async def run(self, request: DealRequest) -> DealResponse:
        return DealResponse(
            deal_id=request.deal_id,
            content=f"deal test ok: {request.message}",
            result={
                "user_id": request.user_id,
                "context": request.context or {},
            },
            sources=[],
        )

    async def stream(self, request: DealRequest) -> AsyncGenerator[str, None]:
        yield f"data: deal test ok: {request.message}\n\n"
        yield "data: [DONE]\n\n"