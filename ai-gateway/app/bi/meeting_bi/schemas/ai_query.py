from __future__ import annotations

from pydantic import BaseModel, Field

from app.bi.meeting_bi.schemas.common import BIChartConfig, BIQueryResult
from app.models.schemas.text2sql import QueryDomain


class MeetingBIQueryRequest(BaseModel):
    question: str
    conversation_id: str | None = None


class MeetingBIQueryResponse(BIQueryResult):
    sql: str = Field(..., description="生成的 SQL")
    answer: str = Field(..., description="自然语言回答")
    chart: BIChartConfig | None = Field(None, description="推荐图表")
    domain: QueryDomain = QueryDomain.MEETING_BI
