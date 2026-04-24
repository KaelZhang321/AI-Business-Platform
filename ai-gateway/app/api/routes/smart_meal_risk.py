"""智能订餐风险识别路由。"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Request

from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas import (
    SmartMealRiskIdentifyEnvelopeResponse,
    SmartMealRiskIdentifyRequest,
    SmartMealRiskItem,
)
from app.services.smart_meal_risk_service import SmartMealRiskService, SmartMealRiskServiceError

router = APIRouter(prefix="/smart-meal", tags=["智能订餐"])
_service = SmartMealRiskService()
logger = logging.getLogger(__name__)


def get_smart_meal_risk_service() -> SmartMealRiskService:
    """返回智能订餐服务单例。"""

    return _service


def _raise_route_error(exc: SmartMealRiskServiceError) -> None:
    message = str(exc)
    if "package_not_found" in message:
        raise BusinessError(ErrorCode.BAD_REQUEST, message) from exc
    if "external_timeout" in message:
        raise BusinessError(ErrorCode.EXTERNAL_SERVICE_TIMEOUT, message) from exc
    if "external_failed" in message:
        raise BusinessError(ErrorCode.EXTERNAL_SERVICE_ERROR, message) from exc
    raise BusinessError(ErrorCode.INTERNAL_ERROR, message) from exc


@router.post("/risk-identify", response_model=SmartMealRiskIdentifyEnvelopeResponse, summary="智能订餐风险识别")
async def identify_smart_meal_risk(
    request_body: SmartMealRiskIdentifyRequest,
    request: Request,
) -> SmartMealRiskIdentifyEnvelopeResponse:
    trace_id = (request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id") or "").strip() or uuid4().hex
    try:
        risk_items = await _service.identify_risks(
            id_card_no=request_body.id_card_no,
            sex=request_body.sex,
            age=request_body.age,
            package_code=request_body.package_code,
            trace_id=trace_id,
        )
        return SmartMealRiskIdentifyEnvelopeResponse(
            code=0,
            message="ok",
            data=[SmartMealRiskItem(**item) for item in risk_items],
        )
    except SmartMealRiskServiceError as exc:
        logger.warning("smart meal risk route failed trace_id=%s error=%s", trace_id, exc)
        _raise_route_error(exc)
    except Exception as exc:
        logger.exception("smart meal risk route unexpected trace_id=%s", trace_id)
        raise BusinessError(ErrorCode.INTERNAL_ERROR, "智能订餐风险识别失败") from exc
