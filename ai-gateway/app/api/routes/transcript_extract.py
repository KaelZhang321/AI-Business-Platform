"""Transcript 信息提取路由。"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends

from app.api.dependencies import get_transcript_extract_service
from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas.transcript_extract import (
    TranscriptExtractEnvelopeResponse,
    TranscriptExtractRequest,
)
from app.services.transcript_extract_service import TranscriptExtractService

router = APIRouter(prefix="/transcriptExtract", tags=["Transcript Extract"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=TranscriptExtractEnvelopeResponse,
    response_model_by_alias=True,
    summary="Transcript 信息提取",
)
async def transcript_extract(
    request: TranscriptExtractRequest,
    service: TranscriptExtractService = Depends(get_transcript_extract_service),
) -> TranscriptExtractEnvelopeResponse:
    """执行 transcript 信息提取。

    功能：
        路由层只做 HTTP 契约承接和统一响应包装，不参与 Prompt 选择、模型路由和结果解析，
        避免后续业务规则再次回流到 route 层。
    """

    route_started_at = time.perf_counter()
    logger.info(
        "transcript extract route received task_code=%s transcript_length=%s",
        request.task_code,
        len(request.transcript),
    )
    try:
        result = await service.extract(
            task_code=request.task_code,
            transcript=request.transcript,
        )
        return TranscriptExtractEnvelopeResponse(code=0, message="ok", data=result)
    except BusinessError:
        raise
    except ValueError as exc:
        raise BusinessError(ErrorCode.BAD_REQUEST, str(exc)) from exc
    except Exception as exc:
        logger.exception("transcript extract route unexpected error task_code=%s", request.task_code)
        raise BusinessError(ErrorCode.INTERNAL_ERROR, f"transcript 信息提取失败: {exc}") from exc
    finally:
        duration_ms = int((time.perf_counter() - route_started_at) * 1000)
        logger.info(
            "transcript extract route completed task_code=%s duration_ms=%s",
            request.task_code,
            duration_ms,
        )
