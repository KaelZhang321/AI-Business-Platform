from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from app.core.config import settings

MAX_ROUNDS = 5


@dataclass
class QARound:
    question: str
    rewritten: str
    sql: str = ""
    answer: str = ""


@dataclass
class ConversationContext:
    rounds: list[QARound] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)


_store: dict[str, ConversationContext] = {}
_lock = threading.Lock()


def _cleanup_expired() -> None:
    ttl = settings.meeting_bi_context_ttl_seconds
    now = time.time()
    expired = [k for k, v in _store.items() if now - v.last_active > ttl]
    for key in expired:
        del _store[key]


def get_last_question(conversation_id: str) -> str | None:
    with _lock:
        _cleanup_expired()
        ctx = _store.get(conversation_id)
        if ctx and ctx.rounds:
            ctx.last_active = time.time()
            return ctx.rounds[-1].rewritten
        return None


def save_round(conversation_id: str, qa_round: QARound) -> None:
    with _lock:
        _cleanup_expired()
        if conversation_id not in _store:
            _store[conversation_id] = ConversationContext()
        ctx = _store[conversation_id]
        ctx.rounds.append(qa_round)
        if len(ctx.rounds) > MAX_ROUNDS:
            ctx.rounds = ctx.rounds[-MAX_ROUNDS:]
        ctx.last_active = time.time()


def get_recent_rounds(conversation_id: str, n: int = 3) -> list[QARound]:
    with _lock:
        ctx = _store.get(conversation_id)
        if ctx and ctx.rounds:
            ctx.last_active = time.time()
            return ctx.rounds[-n:]
        return []
