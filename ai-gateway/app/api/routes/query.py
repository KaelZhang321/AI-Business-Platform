"""通用 Text2SQL 路由。

该路由保留平台问数的稳定 HTTP 契约，让上游不需要理解具体执行器的分流细节。
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_text2sql_service
from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas.text2sql import (
    Text2SQLRequest,
    Text2SQLResponse,
    TrainRequest,
    TrainResponse,
)
from app.services.text2sql_service import Text2SQLService

router = APIRouter()


@router.post("/query/text2sql", response_model=Text2SQLResponse)
async def text2sql(
    request: Text2SQLRequest,
    settings: Settings = Depends(get_settings),
    service: Text2SQLService = Depends(get_text2sql_service),
):
    """执行自然语言问数。

    功能：
        仍然作为平台统一问数入口存在，内部由 `Text2SQLService` 决定是走通用链路
        还是会议 BI 垂直链路。
    """
    return await service.query(
        question=request.question,
        database=request.database or settings.text2sql_default_database,
        domain=request.domain,
        conversation_id=request.conversation_id,
    )


@router.post("/query/train", response_model=TrainResponse)
async def train(
    request: TrainRequest,
    service: Text2SQLService = Depends(get_text2sql_service),
):
    """导入 Text2SQL 问答对训练数据。"""
    training_data = [item.model_dump() for item in request.items]
    result = await service.train(training_data)
    return TrainResponse(status=result["status"], count=result["count"])


@router.post("/query/train-schema", response_model=TrainResponse)
async def train_from_schema(service: Text2SQLService = Depends(get_text2sql_service)):
    """从初始化 SQL 中抽取 DDL 训练问数模型。"""
    result = await service.train_from_schema()
    return TrainResponse(status=result["status"], count=result["count"])
