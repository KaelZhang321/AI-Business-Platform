from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    """知识检索请求模型。"""

    query: str = Field(..., description="检索查询")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数")
    doc_types: list[str] | None = Field(None, description="文档类型过滤")


class KnowledgeSearchResponse(BaseModel):
    """知识检索响应模型。"""

    results: list[KnowledgeResult]
    total: int


class KnowledgeResult(BaseModel):
    """知识检索命中结果。"""

    doc_id: str
    title: str
    content: str
    score: float
    doc_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
