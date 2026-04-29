from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_chat_workflow
from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas.chat import (
    ChatRequest,
    ChatResponse,
)
from app.services.chat_workflow import ChatWorkflow

router = APIRouter()


async def _stream_chat(request: ChatRequest, workflow: ChatWorkflow) -> AsyncGenerator[str, None]:
    """SSE流式输出对话响应。

    STREAM_END 由 ChatWorkflow.stream() 内部的 on_graph_end 事件唯一发出，
    route 层不再补发，避免重复终止事件。异常时由 workflow 发出 STREAM_ERROR。
    """
    async for chunk in workflow.stream(request):
        yield chunk


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
    workflow: ChatWorkflow = Depends(get_chat_workflow),
):
    """对话主入口 - SSE流式输出"""
    if request.stream:
        return EventSourceResponse(_stream_chat(request, workflow))
    try:
        response = await workflow.run(request)
    except Exception as exc:  # pragma: no cover - runtime safety
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return response
