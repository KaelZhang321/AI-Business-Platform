from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas import Text2SQLRequest, Text2SQLResponse
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
