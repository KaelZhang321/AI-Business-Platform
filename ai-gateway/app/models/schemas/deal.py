from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthQuadrantInput(BaseModel):
    sex: str = Field(..., description="性别")
    age: int = Field(..., description="年龄")
    study_id: str = Field(..., description="体检 study_id")
    quadrant_type: str = Field("treatment", description="象限类型")
    chief_complaint_text: str = Field("", description="主诉")


class CustomerProfileInput(BaseModel):
    idCard: str = Field(..., description="加密身份证")


class CustomerPackageInput(BaseModel):
    idCard: str = Field(..., description="加密身份证")
    pageNo: int = 1
    pageSize: int = 10
    source: str = "ERP"


class DealRequest(BaseModel):
    message: str = Field(..., description="用户输入消息")
    user_id: str = Field(..., description="用户ID")
    deal_id: str | None = None
    context: dict[str, Any] | None = None
    stream: bool = False

    health_quadrant: HealthQuadrantInput | None = None
    customer_profile: CustomerProfileInput | None = None
    customer_package: CustomerPackageInput | None = None


class DealResponse(BaseModel):
    deal_id: str | None = None
    content: str
    result: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)