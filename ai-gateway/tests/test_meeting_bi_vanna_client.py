from __future__ import annotations

import sys
from types import ModuleType

from app.bi.meeting_bi.ai.vanna_client import (
    _build_business_mysql_vanna_params,
    _ensure_sqlite_compat,
    _parse_mysql_url,
)


def test_parse_mysql_url_decodes_credentials_and_scalar_charset() -> None:
    url = (
        "mysql+aiomysql://stat_dev_251029:8uI%25K%26%24oybe%40nCHB"
        "@rm-2ze1r48g54eg09z53.mysql.rds.aliyuncs.com:3306/test_stat_data?charset=utf8mb4"
    )

    parsed = _parse_mysql_url(url)

    assert parsed == {
        "host": "rm-2ze1r48g54eg09z53.mysql.rds.aliyuncs.com",
        "dbname": "test_stat_data",
        "user": "stat_dev_251029",
        "password": "8uI%K&$oybe@nCHB",
        "port": 3306,
        "charset": "utf8mb4",
    }


def test_build_business_mysql_vanna_params_reads_business_mysql_settings(monkeypatch) -> None:
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_host", "business-mysql")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_port", 3307)
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_user", "biz_user")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_password", "biz_pass")
    monkeypatch.setattr("app.core.mysql.settings.business_mysql_database", "biz_db")

    parsed = _build_business_mysql_vanna_params()

    assert parsed == {
        "host": "business-mysql",
        "dbname": "biz_db",
        "user": "biz_user",
        "password": "biz_pass",
        "port": 3307,
        "charset": "utf8mb4",
    }


def test_ensure_sqlite_compat_switches_to_pysqlite3_when_stdlib_is_too_old(monkeypatch) -> None:
    old_sqlite = ModuleType("sqlite3")
    old_sqlite.sqlite_version_info = (3, 34, 1)
    pysqlite3 = ModuleType("pysqlite3")

    monkeypatch.setitem(sys.modules, "sqlite3", old_sqlite)
    monkeypatch.setitem(sys.modules, "pysqlite3", pysqlite3)

    _ensure_sqlite_compat()

    assert sys.modules["sqlite3"] is pysqlite3
