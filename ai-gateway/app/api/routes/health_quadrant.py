"""体检/治疗四象限路由。"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request

from app.models.schemas import (
    HealthQuadrantConfirmRequest,
    HealthQuadrantConfirmEnvelopeResponse,
    HealthQuadrantConfirmResponse,
    HealthQuadrantBucket,
    HealthQuadrantQueryEnvelopeResponse,
    HealthQuadrantRequest,
    HealthQuadrantResponse,
)
from app.services.health_quadrant_service import HealthQuadrantService

router = APIRouter(prefix="/health-quadrant", tags=["健康四象限"])
health_quadrant_service = HealthQuadrantService()


@router.post("", response_model=HealthQuadrantQueryEnvelopeResponse, summary="查询健康四象限（已确认优先）")
async def build_health_quadrant(request: HealthQuadrantRequest, raw_request: Request) -> HealthQuadrantQueryEnvelopeResponse:
    """按 StudyID 和象限类型查询四象限。"""
    trace_id = (raw_request.headers.get("X-Trace-Id") or raw_request.headers.get("X-Request-Id") or "").strip() or uuid4().hex
    # 查询接口只接受列表形态主诉；这里统一去重并排序，避免签名输入抖动。
    chief_complaint_items = sorted(set(item.strip() for item in request.chief_complaint_items if item and item.strip()))
    result = await health_quadrant_service.query_quadrants(
        study_id=request.study_id,
        quadrant_type=request.quadrant_type,
        single_exam_items=[item.model_dump(by_alias=True) for item in request.single_exam_items],
        chief_complaint_items=chief_complaint_items,
        trace_id=trace_id,
    )
    return HealthQuadrantQueryEnvelopeResponse(
        code=0,
        message="ok",
        data=HealthQuadrantResponse(
            quadrants=[
                HealthQuadrantBucket(
                    q_code=bucket.get("q_code") or bucket.get("code") or "",
                    q_name=bucket.get("q_name") or bucket.get("name") or "",
                    abnormal_indicators=bucket["abnormalIndicators"],
                    recommendation_plans=bucket["recommendationPlans"],
                )
                for bucket in result["quadrants"]
            ],
        ),
    )


@router.post("/confirm", response_model=HealthQuadrantConfirmEnvelopeResponse, summary="确认并持久化四象限")
async def confirm_health_quadrant(
    request: HealthQuadrantConfirmRequest,
    raw_request: Request,
) -> HealthQuadrantConfirmEnvelopeResponse:
    """保存前端确认后的四象限结果。"""

    trace_id = (raw_request.headers.get("X-Trace-Id") or raw_request.headers.get("X-Request-Id") or "").strip() or uuid4().hex
    confirmed_by = (raw_request.headers.get("X-User-Id") or "").strip() or None
    chief_complaint_items = _merge_complaint_items(request.chief_complaint_items, request.chief_complaint_text)
    await health_quadrant_service.confirm_quadrants(
        study_id=request.study_id,
        quadrant_type=request.quadrant_type,
        single_exam_items=[item.model_dump(by_alias=True) for item in request.single_exam_items],
        chief_complaint_items=chief_complaint_items,
        quadrants=[bucket.model_dump(by_alias=False) for bucket in request.quadrants],
        confirmed_by=confirmed_by,
        trace_id=trace_id,
    )
    return HealthQuadrantConfirmEnvelopeResponse(
        code=0,
        message="ok",
        data=HealthQuadrantConfirmResponse(success=True),
    )


def _merge_complaint_items(items: list[str], single_text: str | None) -> list[str]:
    """合并主诉列表与兼容单条主诉并去重。"""

    merged = list(items)
    if single_text:
        merged.append(single_text)
    seen: set[str] = set()
    result: list[str] = []
    for item in merged:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
