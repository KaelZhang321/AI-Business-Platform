"""
异步 MySQL 连接池 — 基于 aiomysql，解析 meeting_bi_database_url 配置。

使用方式::

    pool = await get_meeting_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql)
            rows = await cur.fetchall()
"""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import parse_qs, unquote, urlparse

import aiomysql

from app.core.config import reveal_secret, settings

logger = logging.getLogger(__name__)

_meeting_pool: aiomysql.Pool | None = None
_pool_lock = asyncio.Lock()


def _parse_db_url(url: str) -> dict:
    """解析 SQLAlchemy / pymysql 风格的 MySQL URL 为 aiomysql 连接参数。"""
    # 去除驱动前缀: mysql+pymysql:// → mysql:// etc.
    cleaned = re.sub(r"^mysql\+\w+://", "mysql://", url)
    parsed = urlparse(cleaned)
    params = parse_qs(parsed.query)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": unquote(parsed.password) if parsed.password else "",
        "db": (parsed.path or "/").lstrip("/") or "meeting_bi",
        "charset": params.get("charset", ["utf8mb4"])[0],
        "autocommit": True,
    }


async def get_meeting_pool() -> aiomysql.Pool:
    """获取 meeting_bi 数据库连接池（懒加载，进程内单例）。"""
    global _meeting_pool
    if _meeting_pool is not None:
        return _meeting_pool

    async with _pool_lock:
        if _meeting_pool is not None:
            return _meeting_pool
        conn_params = _parse_db_url(reveal_secret(settings.meeting_bi_database_url))
        logger.info(
            "Creating aiomysql pool for meeting_bi: host=%s db=%s",
            conn_params["host"],
            conn_params["db"],
        )
        _meeting_pool = await aiomysql.create_pool(
            minsize=1,
            maxsize=5,
            **conn_params,
        )
    return _meeting_pool


async def close_meeting_pool() -> None:
    """关闭连接池（供 lifespan shutdown 调用）。"""
    global _meeting_pool
    if _meeting_pool is not None:
        _meeting_pool.close()
        await _meeting_pool.wait_closed()
        _meeting_pool = None
        logger.info("Meeting BI aiomysql pool closed")
