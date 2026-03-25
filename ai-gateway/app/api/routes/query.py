from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas import (
    Text2SQLRequest,
    Text2SQLResponse,
    TrainRequest,
    TrainResponse,
)
from app.services.text2sql_service import Text2SQLService

router = APIRouter()
text2sql_service = Text2SQLService()


@router.post("/query/text2sql", response_model=Text2SQLResponse)
async def text2sql(
    request: Text2SQLRequest,
    settings: Settings = Depends(get_settings),
):
    """自然语言转SQL查询"""
    return await text2sql_service.query(
        question=request.question,
        database=request.database or settings.text2sql_default_database,
    )


@router.post("/query/train", response_model=TrainResponse)
async def train(request: TrainRequest):
    """导入Text2SQL训练数据（问答对）"""
    training_data = [item.model_dump() for item in request.items]
    result = await text2sql_service.train(training_data)
    return TrainResponse(status=result["status"], count=result["count"])


@router.post("/query/train-schema", response_model=TrainResponse)
async def train_from_schema():
    """从 init-mysql.sql 自动导入表结构到 Vanna 训练"""
    result = await text2sql_service.train_from_schema()
    return TrainResponse(status=result["status"], count=result["count"])
