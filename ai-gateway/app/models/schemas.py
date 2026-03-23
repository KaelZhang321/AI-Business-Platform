from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    CHAT = "chat"
    KNOWLEDGE = "knowledge"
    QUERY = "query"
    TASK = "task"


class SSEEvent(BaseModel):
    """SSE 事件封装"""
    event_type: str = Field(..., description="事件类型: intent/content/ui_spec/sources/done")
    data: Any = Field(..., description="事件数据")


class IntentResult(BaseModel):
    """意图分类结果"""
    intent: IntentType = Field(..., description="识别的意图类型")
    confidence: float = Field(..., ge=0, le=1, description="置信度")


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入消息")
    conversation_id: str | None = Field(None, description="会话ID，空则新建")
    user_id: str = Field(..., description="用户ID")
    context: dict[str, Any] | None = Field(None, description="上下文信息")
    stream: bool = Field(True, description="是否开启SSE流式返回")


class ChatResponse(BaseModel):
    conversation_id: str
    intent: IntentType
    content: str
    ui_spec: dict[str, Any] | None = Field(None, description="动态UI规格")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="引用来源")


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., description="检索查询")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数")
    doc_types: list[str] | None = Field(None, description="文档类型过滤")


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeResult]
    total: int


class KnowledgeResult(BaseModel):
    doc_id: str
    title: str
    content: str
    score: float
    doc_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Text2SQLRequest(BaseModel):
    question: str = Field(..., description="自然语言查询问题")
    database: str = Field("default", description="目标数据库")


class Text2SQLResponse(BaseModel):
    sql: str = Field(..., description="生成的SQL")
    explanation: str = Field(..., description="SQL解释")
    results: list[dict[str, Any]] = Field(default_factory=list, description="查询结果")
    chart_spec: dict[str, Any] | None = Field(None, description="可视化图表规格")


class TrainItem(BaseModel):
    question: str = Field(..., description="自然语言问题")
    sql: str = Field(..., description="对应的SQL语句")


class TrainRequest(BaseModel):
    items: list[TrainItem] = Field(..., description="训练数据列表")


class TrainResponse(BaseModel):
    status: str = "ok"
    count: int = Field(..., description="训练条目数")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    services: dict[str, str] = Field(default_factory=dict)
