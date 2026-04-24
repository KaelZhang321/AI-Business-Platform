"""会议 BI 同步 SQLAlchemy 会话工厂。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# 会议 BI 的固定看板查询仍有同步 SQLAlchemy 调用，独立 engine 能避免与通用问数池互相干扰。
engine = create_engine(
    settings.meeting_bi_database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
