from __future__ import annotations

import aiomysql

from app.bi.meeting_bi.db.async_session import get_meeting_pool



async def get_bi_db_pool() -> aiomysql.Pool:
    """为固定 BI 路由提供共享 aiomysql 连接池。

    功能：
        固定看板接口在 Wave3 后统一走异步 aiomysql 查询，连接池生命周期交给
        `async_session.py` + FastAPI lifespan 管理，路由层只消费共享池。
    """
    return await get_meeting_pool()
