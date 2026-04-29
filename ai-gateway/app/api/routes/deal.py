from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_deal_workflow
from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas.deal import DealRequest, DealResponse
from app.services.deal_workflow import DealWorkflow

router = APIRouter()


async def _stream_deal(
    request: DealRequest,
    workflow: DealWorkflow,
) -> AsyncGenerator[str, None]:
    """SSE流式输出deal测试响应。"""
    async for chunk in workflow.stream(request):
        yield chunk


@router.post("/deal", response_model=DealResponse)
async def deal(
    request: DealRequest,
    settings: Settings = Depends(get_settings),
    workflow: DealWorkflow = Depends(get_deal_workflow),
):
    """Deal测试入口 - 支持SSE流式输出"""
    if request.stream:
        return EventSourceResponse(_stream_deal(request, workflow))

    try:
        response = await workflow.run(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return response