from __future__ import annotations

import pytest

from app.core.mysql import build_business_mysql_conn_params, create_business_mysql_pool


def test_build_business_mysql_conn_params_reads_business_mysql_settings(monkeypatch) -> None:
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_host", "ai-platform-mysql")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_port", 3306)
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_user", "ai_platform")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_password", "ai_platform_dev")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_database", "ai_platform_business")
    monkeypatch.setattr("app.core.mysql.settings.api_catalog_mysql_connect_timeout_seconds", 7.5)

    assert build_business_mysql_conn_params() == {
        "host": "ai-platform-mysql",
        "port": 3306,
        "user": "ai_platform",
        "password": "ai_platform_dev",
        "db": "ai_platform_business",
        "charset": "utf8mb4",
        "connect_timeout": 7.5,
    }
    assert build_business_mysql_conn_params(include_connect_timeout=False) == {
        "host": "ai-platform-mysql",
        "port": 3306,
        "user": "ai_platform",
        "password": "ai_platform_dev",
        "db": "ai_platform_business",
        "charset": "utf8mb4",
    }


@pytest.mark.asyncio
async def test_create_business_mysql_pool_uses_shared_business_conn_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_create_pool(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return "fake-pool"

    monkeypatch.setattr("app.core.mysql.aiomysql.create_pool", fake_create_pool)
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_host", "ai-platform-mysql")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_port", 3306)
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_user", "ai_platform")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_password", "ai_platform_dev")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_database", "ai_platform_business")
    monkeypatch.setattr("app.core.mysql.settings.api_catalog_mysql_connect_timeout_seconds", 7.5)

    pool = await create_business_mysql_pool(minsize=2, maxsize=4)

    assert pool == "fake-pool"
    assert captured == {
        "minsize": 2,
        "maxsize": 4,
        "host": "ai-platform-mysql",
        "port": 3306,
        "user": "ai_platform",
        "password": "ai_platform_dev",
        "db": "ai_platform_business",
        "charset": "utf8mb4",
        "connect_timeout": 7,
    }
