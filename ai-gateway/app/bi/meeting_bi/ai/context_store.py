from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from app.core.config import settings

MAX_ROUNDS = 5


@dataclass
class QARound:
    """会议 BI 单轮问答快照。"""

    question: str
    rewritten: str
    sql: str = ""
    answer: str = ""


@dataclass
class ConversationContext:
    """会议 BI 会话上下文容器。"""

    rounds: list[QARound] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)


_store: dict[str, ConversationContext] = {}
_lock = threading.Lock()


def _cleanup_expired() -> None:
    """清理超时会话，避免内存上下文无限增长。"""
    ttl = settings.meeting_bi_context_ttl_seconds
    now = time.time()
    expired = [k for k, v in _store.items() if now - v.last_active > ttl]
    for key in expired:
        del _store[key]


def get_last_question(conversation_id: str) -> str | None:
    """读取最近一轮改写后的问题，用于代词消解和追问改写。"""
    with _lock:
        _cleanup_expired()
        ctx = _store.get(conversation_id)
        if ctx and ctx.rounds:
            ctx.last_active = time.time()
            return ctx.rounds[-1].rewritten
        return None


def save_round(conversation_id: str, qa_round: QARound) -> None:
    """保存一轮会话，并把上下文限制在固定窗口内。"""
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
    """读取最近 N 轮会话，用于回答总结和上下文补全。"""
    with _lock:
        ctx = _store.get(conversation_id)
        if ctx and ctx.rounds:
            ctx.last_active = time.time()
            return ctx.rounds[-n:]
        return []
