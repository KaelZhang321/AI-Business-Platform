"""MCP 工具集 — 注册到 FastMCP Server 供外部 Agent / Client 调用。"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def register_tools(mcp):
    """将所有工具注册到 mcp 实例上。"""

    @mcp.tool()
    async def rag_search(query: str, top_k: int = 5, doc_types: list[str] | None = None) -> list[dict[str, Any]]:
        """RAG 混合检索 — 向量 + 关键词 + 图谱融合，返回最相关的知识片段。"""
        from app.services.rag_service import RAGService

        service = RAGService()
        results = await service.search(query, top_k=top_k, doc_types=doc_types)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def text2sql(question: str, database: str = "default") -> dict[str, Any]:
        """自然语言转 SQL — 将业务问题转为 SQL 查询并执行，返回结果和可视化 Spec。"""
        from app.services.text2sql_service import Text2SQLService

        service = Text2SQLService()
        result = await service.query(question, database=database)
        return result.model_dump()

    @mcp.tool()
    async def task_query(user_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        """待办任务查询 — 从业务编排层聚合多系统待办任务。"""
        import httpx

        params: dict[str, str] = {}
        if user_id:
            params["userId"] = user_id
        if status:
            params["status"] = status

        async with httpx.AsyncClient(timeout=15) as client:
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
        from app.services.rag_service import RAGService

        service = RAGService()
        results = await service.search(query, top_k=top_k)
        return [{"title": r.title, "content": r.content[:200], "score": r.score} for r in results]
