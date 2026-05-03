from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field


class SmartMealMealType(str, Enum):
    """智能订餐餐次枚举。"""

    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"


class SmartMealRiskIdentifyRequest(BaseModel):
    """智能订餐风险识别请求。"""

    model_config = ConfigDict(populate_by_name=False, extra="forbid")

    id_card_no: str = Field(..., alias="idCardNo", min_length=1, description="客户密文身份证号")
    campus_id: str = Field(..., alias="campusId", min_length=1, description="预约院区ID")
    meal_snapshot: list[SmartMealSnapshotDish] = Field(
        ...,
        alias="mealSnapshot",
        min_length=1,
        description="菜品快照列表",
    )


class SmartMealSnapshotDish(BaseModel):
    """智能订餐菜品快照。"""

    model_config = ConfigDict(populate_by_name=False, extra="forbid")

    dish_code: str | None = Field(None, alias="dishCode", description="菜品编码（缺失时服务层会跳过该元素）")
    dish_name: str | None = Field(None, alias="dishName", description="菜品名称")


class SmartMealRiskDish(BaseModel):
    """风险来源菜品。"""

    model_config = ConfigDict(populate_by_name=True)

    dish_code: str = Field(..., alias="dishCode", description="菜品编码")
    dish_name: str = Field("", alias="dishName", description="菜品名称")


class SmartMealRiskItem(BaseModel):
    """智能订餐风险明细。"""

    model_config = ConfigDict(populate_by_name=True)

    ingredient: str = Field(..., description="食材名称")
    intolerance_level: str = Field(..., alias="intoleranceLevel", description="不耐受级别")
    dishes: list[SmartMealRiskDish] = Field(default_factory=list, description="风险来源菜品列表")


class SmartMealRiskIdentifyEnvelopeResponse(BaseModel):
    """智能订餐风险识别响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: list[SmartMealRiskItem] = Field(default_factory=list, description="冲突食材列表")


class SmartMealPackageRecommendRequest(BaseModel):
    """智能订餐套餐推荐请求。

    功能：
        定义套餐推荐入口契约。只强制身份证号与餐次必填，其余画像特征按“缺失即缺失”
        的业务约定传递，不在网关层做兜底补齐，避免把用户显式输入覆盖为历史脏画像。

    Args:
        id_card_no: 客户身份证号（密文），用于外部接口与行为数据关联。
        campus_id: 预约院区 ID，仅允许在该院区菜单范围内推荐套餐。
        meal_type: 餐次列表，限定为 BREAKFAST/LUNCH/DINNER。
        reservation_date: 订餐日期，决定命中的周菜单与星期菜单配置。
        age: 年龄，可选。
        sex: 性别，可选。
        health_tags: 健康标签，可选。
        diet_preferences: 用餐偏好，可选。
        dietary_restrictions: 忌口自然语言列表，可选。
        abnormal_indicators: 异常指标字典，可选。键为异常类别，值为该类别下的异常描述列表。
            示例：
            {
              "血糖异常": ["糖化HbA1c升高", "空腹血糖8.3"],
              "体重": ["超重"],
              "血脂异常": ["甘油三酯升高", "HDL-C升高"]
            }
    """
    model_config = ConfigDict(populate_by_name=True)

    id_card_no: str = Field(..., alias="idCardNo", min_length=1, description="客户密文身份证号")
    campus_id: str = Field(..., alias="campusId", min_length=1, description="预约院区ID")
    meal_type: list[SmartMealMealType] = Field(..., alias="mealType", min_length=1, description="餐次列表")
    reservation_date: str = Field(..., alias="reservationDate", min_length=1, description="订餐日期，格式 YYYY-MM-DD")
    age: int | None = Field(None, ge=0, le=130, description="年龄")
    sex: str | None = Field(None, description="性别")
    health_tags: list[str] = Field(alias="healthTags", default_factory=list, description="健康标签")
    diet_preferences: list[str] = Field(alias="dietPreferences", default_factory=list, description="用餐偏好")
    dietary_restrictions: list[str] = Field(alias="dietaryRestrictions", default_factory=list, description="忌口自然语言")
    abnormal_indicators: Dict[str, List[str]] = Field(alias="abnormalIndicators", default_factory=dict, description="异常指标字典")


class SmartMealPackageRecommendItem(BaseModel):
    """智能订餐套餐推荐项。"""
    model_config = ConfigDict(populate_by_name=True)

    package_code: str = Field(..., alias="packageCode", description="套餐编码")
    package_name: str = Field(..., alias="packageName", description="套餐名称")
    match_score: float = Field(..., alias="matchScore", description="匹配度绝对评分，保留两位小数")
    reason: str = Field(..., description="推荐理由")


class SmartMealPackageRecommendEnvelopeResponse(BaseModel):
    """智能订餐套餐推荐响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: list[SmartMealPackageRecommendItem] = Field(default_factory=list, description="推荐结果")
