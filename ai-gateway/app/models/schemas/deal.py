from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthQuadrantInput(BaseModel):
    sex: str = Field(..., description="鎬у埆")
    age: int = Field(..., description="骞撮緞")
    study_id: str = Field(..., description="浣撴 study_id")
    quadrant_type: str = Field("treatment", description="璞￠檺绫诲瀷")
    chief_complaint_text: str = Field("", description="涓昏瘔")


class CustomerProfileInput(BaseModel):
    idCard: str = Field(..., description="鍔犲瘑韬唤璇?")


class CustomerPackageInput(BaseModel):
    idCard: str = Field(..., description="鍔犲瘑韬唤璇?")
    pageNo: int = 1
    pageSize: int = 10
    source: str = "ERP"


class CustomerPlanInput(BaseModel):
    idCard: str = Field(..., description="鍔犲瘑韬唤璇?")
    planYear: str = Field(..., description="璁″垝骞翠唤")
    planMonth: int = Field(..., description="璁″垝鏈堜唤")


class DealRequest(BaseModel):
    message: str = Field("璇风粨鍚堢敤鎴蜂俊鎭紝鎺ㄨ崘top3椤圭洰锛岃緭鍑篔SON", description="鐢ㄦ埛杈撳叆娑堟伅")
    user_id: str = Field("u1", description="鐢ㄦ埛ID")
    deal_id: str | None = None
    context: dict[str, Any] | None = None
    user_preferences: dict[str, Any] | None = None
    stream: bool = False

    health_quadrant: HealthQuadrantInput | None = None
    customer_profile: CustomerProfileInput | None = None
    customer_package: CustomerPackageInput | None = None
    customer_plan: CustomerPlanInput | None = None


class DealResponse(BaseModel):
    deal_id: str | None = None
    content: str
    result: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
