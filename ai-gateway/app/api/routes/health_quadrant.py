"""体检/治疗四象限路由。"""

from __future__ import annotations

import logging
import time
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
logger = logging.getLogger(__name__)


def get_health_quadrant_service() -> HealthQuadrantService:
    """获取健康四象限服务实例。

    功能：
        对外暴露统一访问入口，方便应用生命周期在 `main.py` 中执行资源预热与关闭，
        避免业务路由与资源管理耦合。
    """

    return health_quadrant_service


@router.post("", response_model=HealthQuadrantQueryEnvelopeResponse, summary="查询健康四象限（已确认优先）")
async def build_health_quadrant(request: HealthQuadrantRequest, raw_request: Request) -> HealthQuadrantQueryEnvelopeResponse:
    """按 StudyID 和象限类型查询四象限。"""
    trace_id = (raw_request.headers.get("X-Trace-Id") or raw_request.headers.get("X-Request-Id") or "").strip() or uuid4().hex
    route_started_at = time.perf_counter()
    # 查询接口只接受列表形态主诉；这里统一去重并排序，避免签名输入抖动。
    logger.info(
        "health quadrant route query received trace_id=%s study_id=%s quadrant_type=%s single_exam_count=%s complaint_len=%s",
        trace_id,
        request.study_id,
        request.quadrant_type,
        len(request.single_exam_items),
        len(request.chief_complaint_text or ""),
    )
    try:
        result = await health_quadrant_service.query_quadrants(
            sex=request.sex,
            age=request.age,
            study_id=request.study_id,
            quadrant_type=request.quadrant_type,
            single_exam_items=[item.model_dump(by_alias=True) for item in request.single_exam_items],
            chief_complaint_text=request.chief_complaint_text,
            trace_id=trace_id,
        )
        logger.info(
            "health quadrant route query completed trace_id=%s study_id=%s quadrant_type=%s from_cache=%s quadrant_count=%s",
            trace_id,
            request.study_id,
            request.quadrant_type,
            bool(result.get("fromCache")),
            len(result.get("quadrants", [])),
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
    finally:
        duration_ms = int((time.perf_counter() - route_started_at) * 1000)
        logger.info(
            "health quadrant stage duration stage=route.query.total duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
            duration_ms,
            trace_id,
            request.study_id,
            request.quadrant_type,
        )


@router.post("/confirm", response_model=HealthQuadrantConfirmEnvelopeResponse, summary="确认并持久化四象限")
async def confirm_health_quadrant(
    request: HealthQuadrantConfirmRequest,
    raw_request: Request,
) -> HealthQuadrantConfirmEnvelopeResponse:
    """保存前端确认后的四象限结果。"""

    trace_id = (raw_request.headers.get("X-Trace-Id") or raw_request.headers.get("X-Request-Id") or "").strip() or uuid4().hex
    route_started_at = time.perf_counter()
    confirmed_by = (raw_request.headers.get("X-User-Id") or "").strip() or None
    chief_complaint_items = sorted(set(item.strip() for item in request.chief_complaint_items if item and item.strip()))
    logger.info(
        "health quadrant route confirm received trace_id=%s study_id=%s quadrant_type=%s single_exam_count=%s complaint_count=%s quadrant_count=%s confirmed_by=%s",
        trace_id,
        request.study_id,
        request.quadrant_type,
        len(request.single_exam_items),
        len(chief_complaint_items),
        len(request.quadrants),
        confirmed_by,
    )
    try:
        await health_quadrant_service.confirm_quadrants(
            study_id=request.study_id,
            quadrant_type=request.quadrant_type,
            single_exam_items=[item.model_dump(by_alias=True) for item in request.single_exam_items],
            chief_complaint_text="，".join(chief_complaint_items) if chief_complaint_items else None,
            quadrants=[bucket.model_dump(by_alias=False) for bucket in request.quadrants],
            confirmed_by=confirmed_by,
            trace_id=trace_id,
        )
        logger.info(
            "health quadrant route confirm completed trace_id=%s study_id=%s quadrant_type=%s confirmed_by=%s",
            trace_id,
            request.study_id,
            request.quadrant_type,
            confirmed_by,
        )
        return HealthQuadrantConfirmEnvelopeResponse(
            code=0,
            message="ok",
            data=HealthQuadrantConfirmResponse(success=True),
        )
    finally:
        duration_ms = int((time.perf_counter() - route_started_at) * 1000)
        logger.info(
            "health quadrant stage duration stage=route.confirm.total duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
            duration_ms,
            trace_id,
            request.study_id,
            request.quadrant_type,
        )
