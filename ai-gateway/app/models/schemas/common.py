from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """聊天主工作流的一级意图枚举。"""

    CHAT = "chat"
    KNOWLEDGE = "knowledge"
    QUERY = "query"
    TASK = "task"


class SubIntentType(str, Enum):
    """二级意图分类"""

    # 知识问答
    KNOWLEDGE_POLICY = "knowledge_policy"
    KNOWLEDGE_PRODUCT = "knowledge_product"
    KNOWLEDGE_MEDICAL = "knowledge_medical"
    # 数据查询
    DATA_CUSTOMER = "data_customer"
    DATA_SALES = "data_sales"
    DATA_OPERATION = "data_operation"
    DATA_MEETING_BI = "data_meeting_bi"
    # 任务操作
    TASK_QUERY = "task_query"
    TASK_CREATE = "task_create"
    TASK_APPROVE = "task_approve"
    # 通用
    GENERAL = "general"


class SSEEvent(BaseModel):
    """SSE 事件封装"""

    event_type: str = Field(..., description="事件类型: intent/content/ui_spec/sources/done")
    data: Any = Field(..., description="事件数据")


class IntentResult(BaseModel):
    """意图分类结果。"""

    intent: IntentType = Field(..., description="识别的意图类型")
    sub_intent: SubIntentType = Field(SubIntentType.GENERAL, description="二级意图")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
