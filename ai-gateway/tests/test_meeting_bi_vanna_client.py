from __future__ import annotations

from app.bi.meeting_bi.ai.vanna_client import _parse_mysql_url


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
