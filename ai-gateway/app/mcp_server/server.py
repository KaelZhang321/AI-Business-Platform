"""FastMCP Server — 对外暴露 AI 网关能力，供外部 Agent / MCP Client 调用。"""

from __future__ import annotations

import logging

from fastmcp import FastMCP
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import reveal_secret, settings

from app.mcp_server.tools import register_tools

logger = logging.getLogger(__name__)

mcp_server = FastMCP(
    name="AI业务中台",
    instructions="企业级AI网关 MCP Server，提供 RAG 检索、Text2SQL、任务查询、知识搜索等工具。",
)

register_tools(mcp_server)


class MCPApiKeyMiddleware(BaseHTTPMiddleware):
    """Protect mounted MCP endpoints with a simple API key check."""

    async def dispatch(self, request, call_next):  # noqa: ANN001
        expected_api_key = reveal_secret(settings.mcp_api_key)
        if not expected_api_key:
            logger.warning("MCP API key is not configured; rejecting MCP request by default")
            return JSONResponse(status_code=503, content={"error": "mcp_api_key_not_configured"})

        provided_api_key = request.headers.get("X-API-Key", "")
        if provided_api_key != expected_api_key:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})

        return await call_next(request)


def create_mcp_http_app():
    """Create the mounted MCP ASGI app with auth middleware attached."""

    app = mcp_server.http_app()
    app.add_middleware(MCPApiKeyMiddleware)
    return app
