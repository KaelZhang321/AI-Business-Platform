from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter()


async def _stream_chat(request: ChatRequest, settings: Settings) -> AsyncGenerator[str, None]:
    """SSE流式输出对话响应"""
    # TODO: 集成LangGraph工作流
    yield f'{{"event": "intent", "data": "{request.message}"}}'
    yield f'{{"event": "content", "data": "AI网关服务已就绪，正在开发中..."}}'
    yield '{"event": "done", "data": ""}'


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, settings: Settings = Depends(get_settings)):
    """对话主入口 - SSE流式输出"""
    return EventSourceResponse(_stream_chat(request, settings))
