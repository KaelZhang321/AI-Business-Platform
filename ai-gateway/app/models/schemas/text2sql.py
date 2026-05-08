from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QueryDomain(str, Enum):
    """Text2SQL 当前支持的查询域枚举。"""

    GENERIC = "generic"
    MEETING_BI = "meeting_bi"


class Text2SQLRequest(BaseModel):
    """统一问数请求模型。"""

    question: str = Field(..., description="自然语言查询问题")
    database: str = Field("default", description="目标数据库")
    domain: QueryDomain | None = Field(None, description="查询域，空则由服务自动判定")
    conversation_id: str | None = Field(None, description="会话ID，用于多轮问数场景")


class Text2SQLResponse(BaseModel):
    """统一问数响应模型。"""

    sql: str = Field(..., description="生成的SQL")
    explanation: str = Field(..., description="SQL解释")
    domain: QueryDomain = Field(QueryDomain.GENERIC, description="实际命中的查询域")
    answer: str | None = Field(None, description="自然语言结论回答")
    results: list[dict[str, Any]] = Field(default_factory=list, description="查询结果")
    chart_spec: dict[str, Any] | None = Field(None, description="可视化图表规格")


class TrainItem(BaseModel):
    """Text2SQL 单条训练样本。"""

    question: str = Field(..., description="自然语言问题")
    sql: str = Field(..., description="对应的SQL语句")


class TrainRequest(BaseModel):
    """Text2SQL 训练请求。"""

    items: list[TrainItem] = Field(..., description="训练数据列表")


class TrainResponse(BaseModel):
    """Text2SQL 训练响应。"""

    status: str = "ok"
    count: int = Field(..., description="训练条目数")
