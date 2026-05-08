from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .common import IntentType


class ChatRequest(BaseModel):
    """聊天入口请求模型。"""

    message: str = Field(..., description="用户输入消息")
    conversation_id: str | None = Field(None, description="会话ID，空则新建")
    user_id: str = Field(..., description="用户ID")
    context: dict[str, Any] | None = Field(None, description="上下文信息")
    stream: bool = Field(True, description="是否开启SSE流式返回")


class ChatResponse(BaseModel):
    """聊天入口响应模型。"""

    conversation_id: str
    intent: IntentType
    content: str
    ui_spec: dict[str, Any] | None = Field(None, description="动态UI规格")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="引用来源")
