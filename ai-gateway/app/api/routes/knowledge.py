from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas import KnowledgeSearchRequest, KnowledgeSearchResponse

router = APIRouter()


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    settings: Settings = Depends(get_settings),
):
    """知识库检索 - 向量+关键词混合搜索"""
    # TODO: 集成RAG检索服务
    return KnowledgeSearchResponse(results=[], total=0)
