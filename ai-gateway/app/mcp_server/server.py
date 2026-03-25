"""FastMCP Server — 对外暴露 AI 网关能力，供外部 Agent / MCP Client 调用。"""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from app.mcp_server.tools import register_tools

logger = logging.getLogger(__name__)

mcp_server = FastMCP(
    name="AI业务中台",
    instructions="企业级AI网关 MCP Server，提供 RAG 检索、Text2SQL、任务查询、知识搜索等工具。",
)

register_tools(mcp_server)
