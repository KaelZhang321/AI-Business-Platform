from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.models.schemas.api_query import (
    ApiQueryBusinessIntent,
    ApiQueryUIRuntime,
)


@dataclass(slots=True)
class UISnapshotRecord:
    """UI 快照记录。

    功能：
        固化高危写场景下“用户当时看到了什么”的最小留痕载体。
    """

    snapshot_id: str
    trace_id: str
    business_intent_codes: list[str]
    payload: dict[str, Any]


class UISnapshotService:
    """网关侧 UI 快照抽象。

    当前阶段仅提供内存实现，用于稳定 `Snapshot_ID` 契约和高危写检测逻辑。
    后续可以替换为 OSS / MongoDB 等持久化存储，而不需要改 route 层。
    """

    def __init__(self) -> None:
        self._store: dict[str, UISnapshotRecord] = {}
        self._high_risk_intent_codes = {
            "deleteCustomer",
        }

    def should_capture(self, business_intents: list[ApiQueryBusinessIntent]) -> bool:
        """判断当前业务意图是否需要写前快照。

        功能：
            第二阶段对外已经统一为 canonical business intents，不能再依赖历史别名做审计判断。
            这里优先使用显式 `risk_level`，只在缺省时才回退到高风险业务意图编码。
        """
        return any(
            intent.category == "write" and (intent.risk_level == "high" or intent.code in self._high_risk_intent_codes)
            for intent in business_intents
        )

    def create_snapshot(
        self,
        *,
        trace_id: str,
        business_intents: list[ApiQueryBusinessIntent],
        ui_spec: dict[str, Any] | None,
        ui_runtime: ApiQueryUIRuntime | None,
        metadata: dict[str, Any] | None = None,
    ) -> UISnapshotRecord:
        """创建并缓存一份 UI 快照。

        功能：
            在 Phase 02 先把 `snapshot_id` 契约跑通，后续替换 OSS / MongoDB 时不影响 route 层。
        """
        snapshot_id = f"snap_{uuid4().hex}"
        record = UISnapshotRecord(
            snapshot_id=snapshot_id,
            trace_id=trace_id,
            business_intent_codes=[intent.code for intent in business_intents],
            payload={
                "ui_spec": ui_spec or {},
                "ui_runtime": ui_runtime.model_dump(mode="json", exclude_none=True) if ui_runtime else {},
                "metadata": metadata or {},
            },
        )
        self._store[snapshot_id] = record
        return record

    def get_snapshot(self, snapshot_id: str) -> UISnapshotRecord | None:
        """按快照 ID 读取缓存记录。"""
        return self._store.get(snapshot_id)
