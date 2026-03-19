from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas import Text2SQLRequest, Text2SQLResponse

router = APIRouter()


@router.post("/query/text2sql", response_model=Text2SQLResponse)
async def text2sql(
    request: Text2SQLRequest,
    settings: Settings = Depends(get_settings),
):
    """自然语言转SQL查询"""
    # TODO: 集成Text2SQL服务（Vanna.ai）
    return Text2SQLResponse(
        sql="SELECT 1",
        explanation="Text2SQL服务开发中",
        results=[],
    )
