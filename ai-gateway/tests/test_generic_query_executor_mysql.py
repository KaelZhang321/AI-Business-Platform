from __future__ import annotations

from app.services.generic_query_executor import _parse_mysql_url


def test_parse_mysql_url_reads_business_mysql_settings(monkeypatch) -> None:
    monkeypatch.setattr("app.services.generic_query_executor.settings.business_mysql_host", "ai-platform-mysql")
    monkeypatch.setattr("app.services.generic_query_executor.settings.business_mysql_port", 3306)
    monkeypatch.setattr("app.services.generic_query_executor.settings.business_mysql_user", "ai_platform")
    monkeypatch.setattr("app.services.generic_query_executor.settings.business_mysql_password", "ai_platform_dev")
    monkeypatch.setattr("app.services.generic_query_executor.settings.business_mysql_database", "ai_platform_business")

    assert _parse_mysql_url() == {
        "host": "ai-platform-mysql",
        "port": 3306,
        "user": "ai_platform",
        "password": "ai_platform_dev",
        "db": "ai_platform_business",
        "charset": "utf8mb4",
    }
