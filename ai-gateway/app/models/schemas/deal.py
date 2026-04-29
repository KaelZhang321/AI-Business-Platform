from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DealRequest(BaseModel):
    """Deal测试入口请求模型。"""

    message: str = Field(..., description="用户输入消息")
    deal_id: str | None = Field(None, description="Deal ID，空则新建或测试")
    user_id: str = Field(..., description="用户ID")
    context: dict[str, Any] | None = Field(None, description="上下文信息")
    stream: bool = Field(True, description="是否开启SSE流式返回")


class DealResponse(BaseModel):
    """Deal测试入口响应模型。"""

    deal_id: str | None = Field(None, description="Deal ID")
    content: str = Field(..., description="返回内容")
    result: dict[str, Any] | None = Field(None, description="Deal处理结果")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="引用来源")