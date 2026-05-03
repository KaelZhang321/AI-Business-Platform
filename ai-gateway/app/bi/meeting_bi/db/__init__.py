"""Meeting BI database access."""

from app.bi.meeting_bi.db.session import SessionLocal, engine

__all__ = ["engine", "SessionLocal"]
