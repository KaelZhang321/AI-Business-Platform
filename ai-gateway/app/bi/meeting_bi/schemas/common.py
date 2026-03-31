from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BIChartConfig(BaseModel):
    """Shared chart payload used by meeting BI fixed reports and BI query answers."""

    chart_type: str = Field(..., description="图表类型")
    categories: list[str] = Field(default_factory=list, description="分类维度")
    series: list[dict[str, Any]] = Field(default_factory=list, description="图表序列")
    chart_id: str | None = Field(None, description="已缓存图表ID")


class BIQueryResult(BaseModel):
    """Common tabular result payload for BI query execution."""

    columns: list[str] = Field(default_factory=list, description="结果列名")
    rows: list[dict[str, Any]] = Field(default_factory=list, description="结果行")
