"""会议 BI 同步 SQLAlchemy 会话工厂。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.core.mysql import build_business_mysql_conn_params

# 会议 BI 的固定看板查询仍有同步 SQLAlchemy 调用，独立 engine 能避免与通用问数池互相干扰。
_conn = build_business_mysql_conn_params(include_connect_timeout=False)
_meeting_bi_db_url = URL.create(
    drivername="mysql+pymysql",
    username=str(_conn["user"]),
    password=str(_conn["password"]),
    host=str(_conn["host"]),
    port=int(_conn["port"]),
    database=str(_conn["db"]),
    query={"charset": str(_conn["charset"])},
)
engine = create_engine(
    _meeting_bi_db_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
