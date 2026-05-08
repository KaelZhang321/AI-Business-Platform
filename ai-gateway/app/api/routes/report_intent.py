"""报告意图识别路由。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.api.dependencies import get_report_intent_service
from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas.report_intent import (
    ReportIntentDialogData,
    ReportIntentDialogEnvelopeResponse,
    ReportIntentDialogRequest,
)
from app.services.report_intent_service import ReportIntentService, ReportIntentServiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report-intent", tags=["Report Intent"])


@router.post("/dialog", response_model=ReportIntentDialogEnvelopeResponse, summary="识别报告跳转意图")
async def report_intent_dialog(
    request_body: ReportIntentDialogRequest,
    service: ReportIntentService = Depends(get_report_intent_service),
) -> ReportIntentDialogEnvelopeResponse:
    """识别用户查询词对应的报告跳转目标。

    功能：
        使用数据库词典执行纯规则匹配，返回单一主意图。当前版本不做年份提取，
        `targetYear` 固定为 `null`。

    Args:
        request_body: 仅包含查询词的请求对象。
        service: 报告意图服务，由应用共享资源注入（共享业务库连接池）。

    Returns:
        `code/message/data` 统一响应，`data` 包含 `targetId/focusedMetric/targetYear`。

    Raises:
        BusinessError: 词典加载失败或服务内部异常时抛出统一业务错误。
    """

    try:
        resolved = await service.resolve(query=request_body.query)
        return ReportIntentDialogEnvelopeResponse(
            code=0,
            message="ok",
            data=ReportIntentDialogData(
                target_id=resolved.target_id,
                focused_metric=resolved.focused_metric,
                target_year=resolved.target_year,
            ),
        )
    except ReportIntentServiceError as exc:
        logger.warning("report intent resolve failed error=%s", exc)
        raise BusinessError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"report_intent_failed: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("report intent route unexpected")
        raise BusinessError(ErrorCode.INTERNAL_ERROR, "报告意图识别失败") from exc
