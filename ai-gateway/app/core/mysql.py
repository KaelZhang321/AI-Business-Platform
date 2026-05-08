from __future__ import annotations

import aiomysql

from app.core.config import settings


def build_business_mysql_conn_params(*, include_connect_timeout: bool = True) -> dict[str, str | int | float]:
    """从 `BUSINESS_MYSQL_*` 生成统一的业务 MySQL 连接参数。"""
    conn_params: dict[str, str | int | float] = {
        "host": settings.business_mysql_host,
        "port": settings.business_mysql_port,
        "user": settings.business_mysql_user,
        "password": settings.business_mysql_password,
        "db": settings.business_mysql_database,
        "charset": "utf8mb4",
    }
    if include_connect_timeout:
        conn_params["connect_timeout"] = settings.api_catalog_mysql_connect_timeout_seconds
    return conn_params


async def create_business_mysql_pool(
    *,
    minsize: int = 1,
    maxsize: int = 3,
    include_connect_timeout: bool = True,
) -> aiomysql.Pool:
    """创建统一的业务 MySQL 连接池。

    功能：
        仓库里已经统一了“业务库连接参数”的组装逻辑，但多个 repository 仍各自手写
        `aiomysql.create_pool(...)`。这里把“建业务库连接池”也上提成公共方法，避免
        后续再出现池参数、超时策略和字符集口径漂移。

    Args:
        minsize: 连接池最小连接数。
        maxsize: 连接池最大连接数。
        include_connect_timeout: 是否把业务库统一超时写入连接参数。

    Returns:
        已创建好的 `aiomysql.Pool`。

    Edge Cases:
        该方法只负责“业务库”建池，不覆盖 ODS / DW 等其它数据源，避免把不同库的超时
        和连接策略强行揉成一套。
    """

    return await aiomysql.create_pool(
        minsize=minsize,
        maxsize=maxsize,
        **build_business_mysql_conn_params(include_connect_timeout=include_connect_timeout),
    )


def _build_mysql_conn_params(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    connect_timeout_seconds: float,
    include_connect_timeout: bool = True,
) -> dict[str, str | int | float]:
    """构建统一 MySQL 连接参数。

    功能：
        把不同业务域（业务库 / ODS / DW）的连接参数组装逻辑统一收敛，避免各 service
        出现重复字段和不一致超时策略。
    """

    conn_params: dict[str, str | int | float] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "db": database,
        "charset": "utf8mb4",
    }
    if include_connect_timeout:
        conn_params["connect_timeout"] = connect_timeout_seconds
    return conn_params


def build_health_quadrant_ods_mysql_conn_params(*, include_connect_timeout: bool = True) -> dict[str, str | int | float]:
    """构建健康四象限 ODS 数据源 MySQL 连接参数。"""

    return _build_mysql_conn_params(
        host=settings.health_quadrant_ods_mysql_host,
        port=settings.health_quadrant_ods_mysql_port,
        user=settings.health_quadrant_ods_mysql_user,
        password=settings.health_quadrant_ods_mysql_password,
        database=settings.health_quadrant_ods_mysql_database,
        connect_timeout_seconds=settings.health_quadrant_mysql_connect_timeout_seconds,
        include_connect_timeout=include_connect_timeout,
    )
