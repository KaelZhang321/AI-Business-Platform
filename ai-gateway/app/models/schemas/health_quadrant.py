from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthQuadrantSingleExamItem(BaseModel):
    """单项体检条目。"""

    model_config = ConfigDict(populate_by_name=True)

    item_id: str | None = Field(None, alias="itemId", description="单项体检条目ID")
    item_text: str | None = Field(None, alias="itemText", description="单项体检项目名称")
    abnormal_indicator: str | None = Field(None, alias="abnormalIndicator", description="单项体检异常指标")


class HealthQuadrantRequest(BaseModel):
    """四象限分析请求。"""

    sex: str = Field(..., description="性别：男/女")
    age: int | None = Field(None, description="年龄")
    study_id: str = Field(..., min_length=1, description="体检主单号 StudyID")
    quadrant_type: Literal["exam", "treatment"] = Field(..., description="四象限类型：体检或治疗")
    single_exam_items: list[HealthQuadrantSingleExamItem] = Field(
        default_factory=list,
        description="单项体检条目列表（可选，可多条）",
    )
    chief_complaint_text: str | None = Field(None, description="主诉文本（可选）")


class HealthQuadrantBucket(BaseModel):
    """单个象限结果。"""

    q_code: str = Field(..., description="象限编码")
    q_name: str = Field(..., description="象限名称")
    abnormal_indicators: list[str] = Field(default_factory=list, description="该象限命中的异常指标条目")
    recommendation_plans: list[str] = Field(default_factory=list, description="该象限推荐方案")


class HealthQuadrantResponse(BaseModel):
    """体检/治疗双四象限结果。"""

    quadrants: list[HealthQuadrantBucket] = Field(..., min_length=4, max_length=4, description="四象限结果")


class HealthQuadrantConfirmRequest(BaseModel):
    """四象限确认入库请求。"""

    study_id: str = Field(..., min_length=1, description="体检主单号 StudyID")
    quadrant_type: Literal["exam", "treatment"] = Field(..., description="四象限类型：体检或治疗")
    single_exam_items: list[HealthQuadrantSingleExamItem] = Field(
        default_factory=list,
        description="单项体检条目列表（可选，可多条）",
    )
    chief_complaint_text: str | None = Field(None, description="主诉文本列表（可选，可多条）")
    quadrants: list[HealthQuadrantBucket] = Field(..., min_length=4, max_length=4, description="确认后的四象限结果")


class HealthQuadrantConfirmResponse(BaseModel):
    """四象限确认入库响应。"""

    success: bool = Field(True, description="是否保存成功")


class HealthQuadrantQueryEnvelopeResponse(BaseModel):
    """健康四象限查询统一响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: HealthQuadrantResponse = Field(..., description="健康四象限数据")


class HealthQuadrantConfirmEnvelopeResponse(BaseModel):
    """健康四象限确认统一响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: HealthQuadrantConfirmResponse = Field(..., description="确认结果")
