from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.models.schemas.knowledge import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    settings: Settings = Depends(get_settings),
):
    """知识库检索 - 向量+关键词混合搜索"""
    results = await rag_service.search(
        query=request.query,
        top_k=request.top_k,
        doc_types=request.doc_types,
    )
    return KnowledgeSearchResponse(results=results, total=len(results))
