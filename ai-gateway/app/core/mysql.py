from __future__ import annotations

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
