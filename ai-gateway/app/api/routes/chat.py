from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_workflow import ChatWorkflow

router = APIRouter()
workflow = ChatWorkflow()


async def _stream_chat(request: ChatRequest, settings: Settings) -> AsyncGenerator[str, None]:
    """SSE流式输出对话响应"""
    async for chunk in workflow.stream(request):
        yield chunk
    # LangGraph 的 on_graph_end 事件会输出 done，这里保持兼容备份
    yield ChatWorkflow._sse("done", {"status": "completed"})


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, settings: Settings = Depends(get_settings)):
    """对话主入口 - SSE流式输出"""
    if request.stream:
        return EventSourceResponse(_stream_chat(request, settings))
    try:
        response = await workflow.run(request)
    except Exception as exc:  # pragma: no cover - runtime safety
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return response
