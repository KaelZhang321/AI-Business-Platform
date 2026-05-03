from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_deal_workflow
from app.models.schemas.deal import DealRequest, DealResponse
from app.services.deal_workflow import DealWorkflow

router = APIRouter()


async def _stream_deal(
    request: DealRequest,
    workflow: DealWorkflow,
) -> AsyncGenerator[str, None]:
    async for chunk in workflow.stream(request):
        yield chunk


@router.post("/deal", response_model=DealResponse)
async def deal(
    request: DealRequest,
    workflow: DealWorkflow = Depends(get_deal_workflow),
):
    if request.stream:
        return EventSourceResponse(_stream_deal(request, workflow))

    try:
        return await workflow.run(request)
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=repr(exc)) from exc