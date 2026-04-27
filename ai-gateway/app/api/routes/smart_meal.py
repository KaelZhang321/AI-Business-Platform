"""智能订餐路由（风险识别 + 套餐推荐）。"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Request

from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas import (
    SmartMealPackageRecommendEnvelopeResponse,
    SmartMealPackageRecommendItem,
    SmartMealPackageRecommendRequest,
    SmartMealRiskIdentifyEnvelopeResponse,
    SmartMealRiskIdentifyRequest,
    SmartMealRiskItem,
)
from app.services.smart_meal_package_recommend_service import (
    SmartMealPackageRecommendService,
    SmartMealPackageRecommendServiceError,
)
from app.services.smart_meal_risk_service import SmartMealRiskService, SmartMealRiskServiceError

router = APIRouter(prefix="/smart-meal", tags=["智能订餐"])
_service = SmartMealRiskService()
_package_recommend_service = SmartMealPackageRecommendService()
logger = logging.getLogger(__name__)


def get_smart_meal_risk_service() -> SmartMealRiskService:
    """返回智能订餐服务单例。"""

    return _service


def get_smart_meal_package_recommend_service() -> SmartMealPackageRecommendService:
    """返回智能订餐套餐推荐服务单例。

    功能：
        智能订餐业务统一挂在同一路由下；把推荐服务实例显式暴露给 `main.py`，
        便于在应用生命周期中完成预热与释放，避免资源管理散落到路由函数内部。
    """

    return _package_recommend_service


def _raise_route_error(exc: SmartMealRiskServiceError) -> None:
    """风险识别路由错误映射。"""

    message = str(exc)
    if "package_not_found" in message:
        raise BusinessError(ErrorCode.BAD_REQUEST, message) from exc
    if "external_timeout" in message:
        raise BusinessError(ErrorCode.EXTERNAL_SERVICE_TIMEOUT, message) from exc
    if "external_failed" in message:
        raise BusinessError(ErrorCode.EXTERNAL_SERVICE_ERROR, message) from exc
    raise BusinessError(ErrorCode.INTERNAL_ERROR, message) from exc


def _raise_package_recommend_route_error(exc: SmartMealPackageRecommendServiceError) -> None:
    """套餐推荐路由错误映射。

    功能：
        推荐链路在服务层会尽量降级吞错；能抛到路由层的通常是参数或数据库硬故障。
        这里统一映射错误码，保证前端拿到稳定语义而不是裸异常文本。
    """

    message = str(exc)
    if "bad_request" in message:
        raise BusinessError(ErrorCode.BAD_REQUEST, message) from exc
    if "external_timeout" in message:
        raise BusinessError(ErrorCode.EXTERNAL_SERVICE_TIMEOUT, message) from exc
    if "external_failed" in message:
        raise BusinessError(ErrorCode.EXTERNAL_SERVICE_ERROR, message) from exc
    if "db_failed" in message:
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
            meal_type=[item.value for item in request_body.meal_type],
            reservation_date=request_body.reservation_date,
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


@router.post("/package-recommend", response_model=SmartMealPackageRecommendEnvelopeResponse, summary="智能订餐套餐推荐")
async def recommend_smart_meal_package(
    request_body: SmartMealPackageRecommendRequest,
    request: Request,
) -> SmartMealPackageRecommendEnvelopeResponse:
    """推荐智能订餐套餐。

    功能：
        统一承接智能订餐套餐推荐请求，调用服务层完成硬过滤、排序和重排。
        当无候选时按业务约定返回成功空列表，不把“空结果”升级为异常。
    """

    trace_id = (request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id") or "").strip() or uuid4().hex
    try:
        recommendations = await _package_recommend_service.recommend_packages(
            id_card_no=request_body.id_card_no,
            meal_type=[item.value for item in request_body.meal_type],
            reservation_date=request_body.reservation_date,
            age=request_body.age,
            sex=request_body.sex,
            health_tags=request_body.health_tags,
            diet_preferences=request_body.diet_preferences,
            dietary_restrictions=request_body.dietary_restrictions,
            abnormal_indicators=request_body.abnormal_indicators,
            trace_id=trace_id,
        )
        if not recommendations:
            return SmartMealPackageRecommendEnvelopeResponse(
                code=0,
                message="当前条件下暂无可推荐套餐",
                data=[],
            )
        return SmartMealPackageRecommendEnvelopeResponse(
            code=0,
            message="ok",
            data=[SmartMealPackageRecommendItem(**item) for item in recommendations],
        )
    except SmartMealPackageRecommendServiceError as exc:
        logger.warning("smart meal package recommend route failed trace_id=%s error=%s", trace_id, exc)
        _raise_package_recommend_route_error(exc)
    except Exception as exc:
        logger.exception("smart meal package recommend route unexpected trace_id=%s", trace_id)
        raise BusinessError(ErrorCode.INTERNAL_ERROR, "智能订餐套餐推荐失败") from exc
