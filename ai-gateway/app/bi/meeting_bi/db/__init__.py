"""Meeting BI database access."""

from app.bi.meeting_bi.db.dependencies import get_bi_db
from app.bi.meeting_bi.db.session import SessionLocal, engine

__all__ = ["SessionLocal", "engine", "get_bi_db"]
