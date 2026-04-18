"""健康四象限持久化仓储。

功能：
    统一管理“按上下文键命中 + 确认结果幂等写入”的持久化逻辑。
    这里把单项体检条目支持为多条列表，避免真实业务里“一次带多个条目”时缓存维度丢失。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

import aiomysql

from app.core.mysql import build_business_mysql_conn_params

_TABLE_NAME = "health_quadrant_result"
logger = logging.getLogger(__name__)


class HealthQuadrantRepositoryError(RuntimeError):
    """健康四象限仓储异常。"""


class HealthQuadrantRepository:
    """健康四象限持久化仓储。

    功能：
        提供“读取已确认结果 + 写入确认结果”两项能力。命中维度遵循业务约束：
        `study_id + 单项列表 + 主诉文本 + quadrant_type`。
    """

    def __init__(self) -> None:
        self._pool: aiomysql.Pool | None = None
        self._table_ready = False

    async def get_preferred_payload(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_text: str | None,
        source_jlrq: Any = None,
        source_zjrq: Any = None,
        draft_not_older_than: datetime,
        trace_id: str | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """按完整上下文读取可用缓存结果（CONFIRMED 优先，其次未过期 DRAFT）。

        Args:
            study_id: 体检主单号。
            quadrant_type: 四象限类型（`exam` / `treatment`）。
            single_exam_items: 规范化后的单项体检列表，每项包含
                `itemId/itemText/abnormalIndicator`。
            chief_complaint_text: 主诉文本。
            source_jlrq: ODS `ods_tj_jlb.JLRQ`，用于追踪源数据录入时间变化。
            source_zjrq: ODS `ods_tj_jlb.ZJRQ`，用于追踪终检结果更新时间变化。
            draft_not_older_than: 草稿生效窗口下限；早于该时间的 DRAFT 视为过期。
            trace_id: 请求链路追踪 ID。

        Returns:
            命中返回 `(payload, status)`；未命中返回 `(None, None)`。

        Raises:
            HealthQuadrantRepositoryError: 读取数据库失败时抛出。

        Edge Cases:
            1. `payload_json` 可能已是 dict，也可能是字符串，需兼容两种驱动返回形态。
            2. 反序列化失败时返回空命中，防止脏数据把主链路打挂。
        """

        # 1) 基于标准化上下文构造签名：把“同请求+同源版本”稳定映射到同一命中键。
        # await self._ensure_table()
        items_json = _dump_canonical_items_json(single_exam_items)
        context_signature = _build_context_signature(
            study_id=study_id,
            quadrant_type=quadrant_type,
            single_exam_items_json=items_json,
            chief_complaint_text=chief_complaint_text,
            source_jlrq=source_jlrq,
            source_zjrq=source_zjrq,
        )

        # 2) 命中优先级固定为 CONFIRMED > DRAFT，避免草稿覆盖已确认结果。
        sql = f"""
SELECT payload_json, status
FROM {_TABLE_NAME}
WHERE study_id=%s
  AND quadrant_type=%s
  AND context_signature=%s
  AND (
      status='CONFIRMED'
      OR (status='DRAFT' AND updated_at >= %s)
  )
ORDER BY CASE WHEN status='CONFIRMED' THEN 0 ELSE 1 END, updated_at DESC
LIMIT 1
""".strip()
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        sql,
                        (
                            study_id,
                            quadrant_type,
                            context_signature,
                            draft_not_older_than,
                        ),
                    )
                    row = await cursor.fetchone()
        except Exception as exc:
            logger.exception(
                "health quadrant repository read failed trace_id=%s study_id=%s quadrant_type=%s",
                trace_id,
                study_id,
                quadrant_type,
            )
            raise HealthQuadrantRepositoryError(f"读取四象限缓存结果失败: {exc}") from exc

        # 3) 兼容不同驱动返回类型：dict 直返、字符串尝试 JSON 反序列化。
        if not row:
            return None, None
        payload = row.get("payload_json")
        status = str(row.get("status") or "").strip() or None
        if isinstance(payload, dict):
            return payload, status
        if payload is None:
            return None, None
        try:
            return json.loads(str(payload)), status
        except Exception:
            return None, None

    async def upsert_confirmed_payload(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_text: str | None,
        source_jlrq: Any = None,
        source_zjrq: Any = None,
        payload: dict[str, Any],
        confirmed_by: str | None,
        trace_id: str | None = None,
    ) -> None:
        """写入或更新已确认结果。

        Args:
            study_id: 体检主单号。
            quadrant_type: 四象限类型（`exam` / `treatment`）。
            single_exam_items: 规范化后的单项体检列表。
            chief_complaint_text: 主诉文本。
            source_jlrq: ODS `ods_tj_jlb.JLRQ`，用于签名追踪源数据变化。
            source_zjrq: ODS `ods_tj_jlb.ZJRQ`，用于签名追踪源数据变化。
            payload: 四象限结果数据。
            confirmed_by: 确认操作人（通常来自 `X-User-Id`）。
            trace_id: 请求链路追踪 ID。

        Returns:
            无返回值；成功即表示确认态已持久化。

        Raises:
            HealthQuadrantRepositoryError: 写入数据库失败时抛出。

        Edge Cases:
            并发确认与接口重试命中同一唯一键时，采用幂等更新策略，不覆盖已有 payload。
        """

        # 1) 先构造签名：确保确认写入与查询命中使用同一上下文口径。
        # await self._ensure_table()
        items_json = _dump_canonical_items_json(single_exam_items)
        context_signature = _build_context_signature(
            study_id=study_id,
            quadrant_type=quadrant_type,
            single_exam_items_json=items_json,
            chief_complaint_text=chief_complaint_text,
            source_jlrq=source_jlrq,
            source_zjrq=source_zjrq,
        )

        # 2) 并发安全：冲突时仅刷新确认人和时间，不回写 payload，防止后写覆盖先写。
        sql = f"""
INSERT INTO {_TABLE_NAME}(
    study_id,
    quadrant_type,
    single_exam_items_json,
    chief_complaint_items_json,
    context_signature,
    status,
    payload_json,
    confirmed_by
)
VALUES(%s, %s, %s, %s, %s, 'CONFIRMED', %s, %s)
ON DUPLICATE KEY UPDATE
status = 'CONFIRMED',
confirmed_by = VALUES(confirmed_by),
updated_at = CURRENT_TIMESTAMP
""".strip()

        conn = None
        try:
            pool = await self._get_pool()
            async with pool.acquire() as acquired_conn:
                conn = acquired_conn
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        sql,
                        (
                            study_id,
                            quadrant_type,
                            items_json,
                            chief_complaint_text,
                            context_signature,
                            json.dumps(payload, ensure_ascii=False),
                            _normalize_nullable_text(confirmed_by),
                        ),
                    )
                await conn.commit()
        except Exception as exc:
            if conn is not None:
                try:
                    # 写事务失败后显式回滚，避免连接复用时残留脏事务状态。
                    await conn.rollback()
                except Exception as rollback_exc:
                    logger.warning(
                        "health quadrant repository rollback failed in confirmed upsert study_id=%s quadrant_type=%s error=%s",
                        study_id,
                        quadrant_type,
                        rollback_exc,
                        exc_info=True,
                    )
            logger.exception(
                "health quadrant repository write failed trace_id=%s study_id=%s quadrant_type=%s",
                trace_id,
                study_id,
                quadrant_type,
            )
            raise HealthQuadrantRepositoryError(f"写入四象限持久化结果失败: {exc}") from exc

    async def upsert_draft_payload(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_text: str | None,
        source_jlrq: Any = None,
        source_zjrq: Any = None,
        payload: dict[str, Any],
        trace_id: str | None = None,
    ) -> None:
        """写入或更新草稿结果。

        功能：
            查询链路实时计算后先落 DRAFT，用于后续重复请求直接命中，避免重复调用 LLM。
            若同上下文已是 CONFIRMED，则保持确认态不回退。

        Args:
            study_id: 体检主单号。
            quadrant_type: 四象限类型（`exam` / `treatment`）。
            single_exam_items: 规范化后的单项体检列表。
            chief_complaint_text: 主诉文本。
            source_jlrq: ODS `ods_tj_jlb.JLRQ`，用于签名追踪源数据变化。
            source_zjrq: ODS `ods_tj_jlb.ZJRQ`，用于签名追踪源数据变化。
            payload: 四象限草稿结果。
            trace_id: 请求链路追踪 ID。

        Returns:
            无返回值；成功即表示草稿已落库或已幂等更新。

        Raises:
            HealthQuadrantRepositoryError: 写库失败时抛出。

        Edge Cases:
            当目标记录已是 CONFIRMED 时，草稿写入不会回退状态或覆盖确认结果。
        """

        # 1) 与查询/确认链路共用同一签名算法，确保草稿与确认在同一上下文维度可追踪。
        # await self._ensure_table()
        items_json = _dump_canonical_items_json(single_exam_items)
        context_signature = _build_context_signature(
            study_id=study_id,
            quadrant_type=quadrant_type,
            single_exam_items_json=items_json,
            chief_complaint_text=chief_complaint_text,
            source_jlrq=source_jlrq,
            source_zjrq=source_zjrq,
        )

        # 2) 保护确认态：同签名已确认时只允许“读复用”，不允许草稿回写覆盖。
        sql = f"""
INSERT INTO {_TABLE_NAME}(
    study_id,
    quadrant_type,
    single_exam_items_json,
    chief_complaint_text,
    context_signature,
    status,
    payload_json,
    confirmed_by
)
VALUES(%s, %s, %s, %s, %s, 'DRAFT', %s, NULL)
ON DUPLICATE KEY UPDATE
single_exam_items_json = VALUES(single_exam_items_json),
chief_complaint_text = VALUES(chief_complaint_text),
payload_json = IF(status='CONFIRMED', payload_json, VALUES(payload_json)),
status = IF(status='CONFIRMED', status, VALUES(status)),
updated_at = IF(status='CONFIRMED', updated_at, CURRENT_TIMESTAMP)
""".strip()

        conn = None
        try:
            pool = await self._get_pool()
            async with pool.acquire() as acquired_conn:
                conn = acquired_conn
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        sql,
                        (
                            study_id,
                            quadrant_type,
                            items_json,
                            chief_complaint_text,
                            context_signature,
                            json.dumps(payload, ensure_ascii=False),
                        ),
                    )
                await conn.commit()
        except Exception as exc:
            if conn is not None:
                try:
                    # 草稿写入失败同样需要回滚，防止后续同连接执行异常。
                    await conn.rollback()
                except Exception as rollback_exc:
                    logger.warning(
                        "health quadrant repository rollback failed in draft upsert study_id=%s quadrant_type=%s error=%s",
                        study_id,
                        quadrant_type,
                        rollback_exc,
                        exc_info=True,
                    )
            logger.exception(
                "health quadrant repository upsert draft failed trace_id=%s study_id=%s quadrant_type=%s",
                trace_id,
                study_id,
                quadrant_type,
            )
            raise HealthQuadrantRepositoryError(f"写入四象限草稿失败: {exc}") from exc

    async def close(self) -> None:
        """关闭连接池。"""

        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._table_ready = False

    async def _ensure_table(self) -> None:
        """确保持久化表存在。

        功能：
            能力快速迭代时，先让接口具备自恢复建表能力，减少联调环境“忘记执行 DDL”
            带来的阻塞。正式环境仍建议用迁移脚本统一管理。

        Returns:
            无返回值；存在即跳过，不存在则创建。

        Raises:
            Exception: DDL 执行失败时由调用链上抛。

        Edge Cases:
            在多实例并发启动场景下，`IF NOT EXISTS` 语义可避免重复建表冲突。
        """

        if self._table_ready:
            return

        ddl = f"""
            CREATE TABLE IF NOT EXISTS {_TABLE_NAME} (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                study_id VARCHAR(64) NOT NULL,
                quadrant_type VARCHAR(16) NOT NULL,
                single_exam_items_json JSON NULL,
                chief_complaint_items_json JSON NULL,
                context_signature CHAR(64) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
                payload_json JSON NOT NULL,
                confirmed_by VARCHAR(64) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_context_signature (context_signature),
                KEY idx_study_id (study_id, quadrant_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """.strip()

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(ddl)
            await conn.commit()
        self._table_ready = True

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=3,
                **build_business_mysql_conn_params(),
            )
        return self._pool


def _normalize_nullable_text(value: str | None) -> str | None:
    """把可选文本规整为稳定值。"""

    if value is None:
        return None
    text = value.strip()
    return text or None


def _dump_canonical_items_json(single_exam_items: list[dict[str, str]]) -> str:
    """序列化规范化后的单项列表。

    功能：
        落库前把条目转成稳定顺序 JSON，保证同一业务输入在不同客户端提交时，
        上下文签名仍然一致。
    """

    canonical_items = []
    for item in single_exam_items:
        item_id = _normalize_nullable_text(item.get("itemId"))
        item_text = _normalize_nullable_text(item.get("itemText"))
        abnormal_indicator = _normalize_nullable_text(item.get("abnormalIndicator"))
        canonical_items.append(
            {
                "itemId": item_id or "",
                "itemText": item_text or "",
                "abnormalIndicator": abnormal_indicator or "",
            }
        )
    return _stable_json_dumps(canonical_items)


def _build_context_signature(
    *,
    study_id: str,
    quadrant_type: str,
    single_exam_items_json: str,
    chief_complaint_text: str | None,
    source_jlrq: Any = None,
    source_zjrq: Any = None,
) -> str:
    """构造上下文签名。

    功能：
        多条单项体检无法直接拼接为唯一键，使用签名可以把长文本上下文稳定收敛成固定长度键，
        同时保持查询性能和索引可控性。
    """

    normalized_jlrq = _normalize_source_signature_part(source_jlrq)
    normalized_zjrq = _normalize_source_signature_part(source_zjrq)
    raw = (
        f"{study_id}|{quadrant_type}|{single_exam_items_json}|{chief_complaint_text}|"
        f"{normalized_jlrq}|{normalized_zjrq}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _stable_json_dumps(value: Any) -> str:
    """把 JSON 数据规范化后稳定序列化。

    功能：
        `context_signature` 要求“语义等价输入得到同一签名”。因此这里在哈希前强制执行：
        1. 所有 Array 按字典序排序；
        2. 所有 Object 按 key 排序；
        3. 用固定分隔符输出字符串，消除空格差异。
    """

    normalized = _normalize_for_signature(value)
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _normalize_for_signature(value: Any) -> Any:
    """递归规范化 JSON 结构用于签名。"""

    if isinstance(value, dict):
        normalized_object = {str(key): _normalize_for_signature(sub_value) for key, sub_value in value.items()}
        # 对象 key 排序由 sort_keys=True 兜底，这里显式重建可提升可读性并固定中间态。
        return {key: normalized_object[key] for key in sorted(normalized_object)}
    if isinstance(value, list):
        normalized_items = [_normalize_for_signature(item) for item in value]
        # 列表中的元素可能是 object/list/scalar，统一用稳定 JSON 字符串作为排序键。
        return sorted(normalized_items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_source_signature_part(value: Any) -> str:
    """规范化源系统时间戳，保证签名构造稳定。

    功能：
        `JLRQ/ZJRQ` 来自 MySQL 时，驱动层可能返回 `datetime` 或字符串。
        这里统一成可预测文本，避免同一时间值因类型差异导致签名抖动。
    """

    if value is None:
        return ""
    if isinstance(value, datetime):
        # 以秒级文本参与签名，兼顾稳定性与业务追踪粒度。
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip()
