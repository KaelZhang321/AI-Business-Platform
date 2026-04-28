from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.bi.meeting_bi.db.session import SessionLocal


def get_bi_db() -> Generator[Session, None, None]:
    """为固定 BI 路由提供独立数据库会话。

    功能：
        固定看板接口仍走同步 SQLAlchemy 查询，这里统一封装生命周期，避免路由层忘记关闭连接。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
