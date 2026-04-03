from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.bi.meeting_bi.db.session import SessionLocal


def get_bi_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
