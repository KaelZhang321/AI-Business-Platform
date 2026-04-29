"""阶段耗时观测工具 — 用于 AI 对话全链路性能分析。

Usage:
    timer = StageTimer()
    with timer.stage("intent_classify"):
        result = await classifier.classify(msg)
    with timer.stage("rag_search"):
        docs = await rag.search(msg)
    logger.info("stages=%s", timer.to_dict())
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


class StageTimer:
    """轻量级阶段计时器，记录命名阶段的耗时。

    线程安全性：单个 StageTimer 实例应在单个请求内使用，不跨请求共享。
    """

    def __init__(self) -> None:
        self._stages: dict[str, float] = {}
        self._start_time = time.perf_counter()
        self._counters: dict[str, int] = {}

    @contextmanager
    def stage(self, name: str):
        """记录命名阶段的耗时（毫秒）。

        Args:
            name: 阶段名称，如 "intent_classify", "rag_embedding"

        Usage:
            with timer.stage("intent_classify"):
                await classify(...)
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._stages[name] = round(elapsed_ms, 2)

    def count(self, name: str, increment: int = 1) -> None:
        """递增计数器（如 LLM 调用次数）。"""
        self._counters[name] = self._counters.get(name, 0) + increment

    def elapsed_ms(self, name: str) -> float | None:
        """获取指定阶段的耗时（毫秒），未记录则返回 None。"""
        return self._stages.get(name)

    def total_ms(self) -> float:
        """获取从创建 Timer 到当前的总耗时（毫秒）。"""
        return round((time.perf_counter() - self._start_time) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        """输出结构化耗时数据，适合日志记录。"""
        result: dict[str, Any] = {"total_ms": self.total_ms()}
        result.update({f"{k}_ms": v for k, v in self._stages.items()})
        result.update(self._counters)
        return result

    def log_summary(self, prefix: str = "chat_workflow") -> None:
        """输出耗时摘要到日志。"""
        data = self.to_dict()
        parts = [f"{k}={v}" for k, v in data.items()]
        logger.info("[%s] %s", prefix, " ".join(parts))
