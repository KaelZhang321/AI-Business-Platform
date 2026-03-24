"""MCP 工具集 — 注册到 FastMCP Server 供外部 Agent / Client 调用。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 模块级共享客户端，避免每次调用创建新实例
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=15)
    return _http_client


def _get_rag_service():
    """从 FastAPI app.state 获取共享 RAGService，回退为缓存单例。"""
    try:
        from app.main import app
        if hasattr(app.state, "rag_service"):
            return app.state.rag_service
    except Exception:
        pass
    # 回退：缓存到函数属性，避免每次调用创建新实例
    if not hasattr(_get_rag_service, "_fallback"):
        from app.services.rag_service import RAGService
        _get_rag_service._fallback = RAGService()
    return _get_rag_service._fallback


def _get_text2sql_service():
    """懒加载 Text2SQLService 单例。"""
    if not hasattr(_get_text2sql_service, "_instance"):
        from app.services.text2sql_service import Text2SQLService
        _get_text2sql_service._instance = Text2SQLService()
    return _get_text2sql_service._instance


def register_tools(mcp):
    """将所有工具注册到 mcp 实例上。"""

    @mcp.tool()
    async def rag_search(query: str, top_k: int = 5, doc_types: list[str] | None = None) -> list[dict[str, Any]]:
        """RAG 混合检索 — 向量 + 关键词 + 图谱融合，返回最相关的知识片段。"""
        service = _get_rag_service()
        results = await service.search(query, top_k=top_k, doc_types=doc_types)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def text2sql(question: str, database: str = "default") -> dict[str, Any]:
        """自然语言转 SQL — 将业务问题转为 SQL 查询并执行，返回结果和可视化 Spec。"""
        service = _get_text2sql_service()
        result = await service.query(question, database=database)
        return result.model_dump()

    @mcp.tool()
    async def task_query(user_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        """待办任务查询 — 从业务编排层聚合多系统待办任务。"""
        params: dict[str, str] = {}
        if user_id:
            params["userId"] = user_id
        if status:
            params["status"] = status

        client = _get_http_client()
        resp = await client.get(f"{settings.business_server_url}/api/v1/tasks/aggregate", params=params)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body)
        if isinstance(data, dict) and "records" in data:
            return data["records"]
        if isinstance(data, list):
            return data
        return []

    @mcp.tool()
    async def knowledge_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """知识库搜索 — 简化版 RAG 搜索，仅返回标题和摘要。"""
        service = _get_rag_service()
        results = await service.search(query, top_k=top_k)
        return [{"title": r.title, "content": r.content[:200], "score": r.score} for r in results]
