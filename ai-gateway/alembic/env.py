from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import URL
from sqlalchemy import create_engine, pool

from app.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 当前阶段只做手写 migration，不维护完整 ORM metadata。
target_metadata = None


def _build_business_sqlalchemy_url() -> URL:
    """构建 Alembic 使用的业务库 URL 对象。

    功能：
        应用主链路多数 MySQL 访问仍基于 `aiomysql`。Alembic 需要同步 SQLAlchemy URL，
        这里统一从同一组业务库配置构建连接信息，避免迁移链再维护一套独立 DSN。

    Edge Cases:
        业务库密码可能包含 `%`、`@`、`:` 等 URL 保留字符。若手工字符串拼接，会在 URL
        解析阶段被误解释并污染密码值，最终触发驱动层编码异常。使用 `URL.create` 让
        SQLAlchemy 负责安全转义，可避免这类隐性发布故障。
    """

    return URL.create(
        "mysql+pymysql",
        username=settings.business_mysql_user,
        password=settings.business_mysql_password,
        host=settings.business_mysql_host,
        port=settings.business_mysql_port,
        database=settings.business_mysql_database,
        query={"charset": "utf8mb4"},
    )


def run_migrations_offline() -> None:
    """以离线模式执行迁移。"""

    context.configure(
        # 离线模式仍要求 URL 字符串；这里通过 SQLAlchemy 渲染，保持与在线模式一致的转义语义。
        url=_build_business_sqlalchemy_url().render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以在线模式执行迁移。"""

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _build_business_sqlalchemy_url().render_as_string(hide_password=False)
    connectable = create_engine(
        configuration["sqlalchemy.url"],
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
