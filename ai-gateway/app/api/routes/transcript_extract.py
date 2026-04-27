"""Transcript 信息提取路由。"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas import (
    TranscriptExtractEnvelopeResponse,
    TranscriptExtractRequest,
)
from app.services.transcript_extract_service import TranscriptExtractService

router = APIRouter(prefix="/transcriptExtract", tags=["Transcript Extract"])
transcript_extract_service = TranscriptExtractService()
logger = logging.getLogger(__name__)


def get_transcript_extract_service() -> TranscriptExtractService:
    """获取 transcript 抽取服务实例。

    功能：
        与项目中其他路由保持一致，显式暴露单例获取入口，便于应用生命周期统一关闭资源，
        也方便测试通过 monkeypatch 替换底层服务。
    """

    return transcript_extract_service


@router.post(
    "",
    response_model=TranscriptExtractEnvelopeResponse,
    response_model_by_alias=True,
    summary="Transcript 信息提取",
)
async def transcript_extract(request: TranscriptExtractRequest) -> TranscriptExtractEnvelopeResponse:
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
        result = await transcript_extract_service.extract(
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
