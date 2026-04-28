from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import aiomysql

logger = logging.getLogger(__name__)

_INTENT_OVERVIEW = "overview"
_INTENT_METRIC_FOCUS = "metric-focus"

_SELECT_ACTIVE_INTENT_DEFINITIONS_SQL = """
SELECT intent_code, priority
FROM report_intent_definition
WHERE status = 'active' AND enabled = 1
ORDER BY priority ASC, intent_code ASC
""".strip()

_SELECT_ACTIVE_INTENT_KEYWORDS_SQL = """
SELECT intent_code, keyword, match_mode, sort_order
FROM report_intent_keyword
WHERE status = 'active' AND enabled = 1
ORDER BY intent_code ASC, sort_order ASC, id ASC
""".strip()

_SELECT_ACTIVE_METRIC_FOCUS_SQL = """
SELECT
    target_intent_code,
    keyword,
    metric_code,
    standard_metric_name,
    abbreviation,
    aliases,
    metric_category,
    common_unit,
    result_type,
    sort_order
FROM report_intent_metric_focus_keyword
WHERE status = 'active' AND enabled = 1
ORDER BY sort_order ASC, id ASC
""".strip()


class ReportIntentServiceError(RuntimeError):
    """报告意图服务异常。"""


@dataclass(frozen=True)
class _IntentKeywordRule:
    """通用关键词规则。"""

    intent_code: str
    keyword: str
    match_mode: str
    sort_order: int


@dataclass(frozen=True)
class _MetricFocusRule:
    """metric-focus 专用规则。"""

    target_intent_code: str
    keyword: str
    metric_code: str
    standard_metric_name: str
    abbreviation: str | None
    aliases: str | None
    metric_category: str | None
    common_unit: str | None
    result_type: str | None
    sort_order: int


@dataclass(frozen=True)
class _ReportIntentDictionarySnapshot:
    """报告意图词典快照。

    功能：
        将数据库词典按“进程内只读快照”缓存，避免每次请求都击穿 MySQL。业务侧频繁扩词
        的诉求通过重启/灰度刷新解决，本期优先保障查询链路稳定与低延迟。
    """

    intent_priority: dict[str, int]
    keyword_rules: tuple[_IntentKeywordRule, ...]
    metric_focus_rules: tuple[_MetricFocusRule, ...]


@dataclass(frozen=True)
class ReportIntentResolution:
    """报告意图解析结果。"""

    target_id: str
    focused_metric: str | None
    target_year: int | None


class ReportIntentService:
    """报告意图规则服务（数据库词典版）。

    功能：
        读取 MySQL 词典并执行纯规则匹配，输出单一跳转目标。此服务刻意不引入 LLM，
        目标是在 AI 咨询跳转场景提供可解释、可回放、可回归测试的稳定判定。

    Args:
        pool: 业务库共享连接池，由 AppResources 注入。服务本身不创建连接池。

    Returns:
        `resolve(...)` 返回 `ReportIntentResolution`，并保证 `target_year` 当前恒为 `None`。

    Raises:
        ReportIntentServiceError: 词典加载失败或连接池缺失时抛出。

    Edge Cases:
        - 词典为空或加载失败时，返回 `overview` 兜底，避免前端跳转链硬失败。
        - 多命中时按 `report_intent_definition.priority` 做单主命中仲裁。
    """

    def __init__(self, *, pool: aiomysql.Pool | None = None) -> None:
        self._pool = pool
        self._snapshot: _ReportIntentDictionarySnapshot | None = None
        self._snapshot_lock = asyncio.Lock()

    async def warmup(self) -> None:
        """预热词典快照。

        功能：
            启动期主动预热，避免首个请求承担词典查询开销和潜在冷启动抖动。
        """

        await self._ensure_snapshot_loaded(force_refresh=True)

    async def resolve(self, *, query: str) -> ReportIntentResolution:
        """根据查询词解析报告跳转意图。

        Args:
            query: 用户自然语言查询词。

        Returns:
            单一解析结果，字段说明：
            - `target_id`：目标意图编码
            - `focused_metric`：仅 `metric-focus` 命中时返回标准指标名称
            - `target_year`：本期固定 `None`

        Raises:
            ReportIntentServiceError: 连接池缺失或词典加载发生不可恢复错误。
        """

        normalized_query = _normalize_query_text(query)
        if not normalized_query:
            return ReportIntentResolution(target_id=_INTENT_OVERVIEW, focused_metric=None, target_year=None)

        snapshot = await self._ensure_snapshot_loaded(force_refresh=False)

        # 1. 先命中 metric-focus。原因：业务上单指标跳转需要压过所有普通分组。
        metric_hit = self._match_metric_focus(snapshot.metric_focus_rules, normalized_query)
        if metric_hit is not None:
            return ReportIntentResolution(
                target_id=metric_hit.target_intent_code,
                focused_metric=metric_hit.standard_metric_name,
                target_year=None,
            )

        # 2. 再走通用意图关键词命中，收集候选后按优先级仲裁成单值。
        candidates = self._collect_intent_candidates(snapshot.keyword_rules, normalized_query)
        if not candidates:
            return ReportIntentResolution(target_id=_INTENT_OVERVIEW, focused_metric=None, target_year=None)

        selected_target = self._select_primary_target(snapshot.intent_priority, candidates)
        return ReportIntentResolution(target_id=selected_target, focused_metric=None, target_year=None)

    async def close(self) -> None:
        """服务不持有连接池所有权，close 保持 no-op。"""

    async def _ensure_snapshot_loaded(self, *, force_refresh: bool) -> _ReportIntentDictionarySnapshot:
        """确保词典快照已加载。"""

        if self._snapshot is not None and not force_refresh:
            return self._snapshot

        async with self._snapshot_lock:
            if self._snapshot is not None and not force_refresh:
                return self._snapshot
            self._snapshot = await self._load_snapshot_from_mysql()
            return self._snapshot

    async def _load_snapshot_from_mysql(self) -> _ReportIntentDictionarySnapshot:
        """从 MySQL 加载词典快照。

        功能：
            该方法把三张词典表一次性收敛为不可变快照，后续解析阶段只做内存判定，避免
            在请求热路径反复触库。
        """

        try:
            intent_rows = await self._fetch_mysql_rows(_SELECT_ACTIVE_INTENT_DEFINITIONS_SQL)
            keyword_rows = await self._fetch_mysql_rows(_SELECT_ACTIVE_INTENT_KEYWORDS_SQL)
            metric_rows = await self._fetch_mysql_rows(_SELECT_ACTIVE_METRIC_FOCUS_SQL)
        except Exception as exc:  # noqa: BLE001
            raise ReportIntentServiceError(f"report_intent_dictionary_load_failed: {exc}") from exc

        intent_priority: dict[str, int] = {}
        for row in intent_rows:
            intent_code = str(row.get("intent_code") or "").strip()
            if not intent_code:
                continue
            intent_priority[intent_code] = int(row.get("priority") or 9999)

        # 若治理词典缺失 overview，本地强制补位，保证空命中时必有稳定兜底。
        intent_priority.setdefault(_INTENT_OVERVIEW, 9999)

        keyword_rules: list[_IntentKeywordRule] = []
        for row in keyword_rows:
            intent_code = str(row.get("intent_code") or "").strip()
            keyword = _normalize_rule_keyword(str(row.get("keyword") or ""))
            if not intent_code or not keyword:
                continue
            keyword_rules.append(
                _IntentKeywordRule(
                    intent_code=intent_code,
                    keyword=keyword,
                    match_mode=str(row.get("match_mode") or "contains").strip().lower(),
                    sort_order=int(row.get("sort_order") or 100),
                )
            )

        metric_focus_rules: list[_MetricFocusRule] = []
        for row in metric_rows:
            target_intent_code = str(row.get("target_intent_code") or "").strip() or _INTENT_METRIC_FOCUS
            keyword = _normalize_rule_keyword(str(row.get("keyword") or ""))
            metric_code = str(row.get("metric_code") or "").strip()
            standard_metric_name = str(row.get("standard_metric_name") or "").strip()
            if not keyword or not metric_code or not standard_metric_name:
                continue
            metric_focus_rules.append(
                _MetricFocusRule(
                    target_intent_code=target_intent_code,
                    keyword=keyword,
                    metric_code=metric_code,
                    standard_metric_name=standard_metric_name,
                    abbreviation=_normalize_optional_text(row.get("abbreviation")),
                    aliases=_normalize_optional_text(row.get("aliases")),
                    metric_category=_normalize_optional_text(row.get("metric_category")),
                    common_unit=_normalize_optional_text(row.get("common_unit")),
                    result_type=_normalize_optional_text(row.get("result_type")),
                    sort_order=int(row.get("sort_order") or 100),
                )
            )

        return _ReportIntentDictionarySnapshot(
            intent_priority=intent_priority,
            keyword_rules=tuple(keyword_rules),
            metric_focus_rules=tuple(metric_focus_rules),
        )

    async def _fetch_mysql_rows(self, sql: str) -> list[dict[str, object]]:
        """执行 SQL 并返回字典行。"""

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def _get_pool(self) -> aiomysql.Pool:
        """读取注入的共享业务库连接池。"""

        if self._pool is None:
            raise ReportIntentServiceError("business_mysql_pool_missing: ReportIntentService requires shared pool")
        return self._pool

    @staticmethod
    def _match_metric_focus(
        rules: tuple[_MetricFocusRule, ...],
        normalized_query: str,
    ) -> _MetricFocusRule | None:
        """匹配 metric-focus 规则。"""

        for rule in rules:
            if rule.keyword and rule.keyword in normalized_query:
                return rule
        return None

    @staticmethod
    def _collect_intent_candidates(
        rules: tuple[_IntentKeywordRule, ...],
        normalized_query: str,
    ) -> set[str]:
        """收集命中的意图候选集合。"""

        candidates: set[str] = set()
        for rule in rules:
            if not rule.keyword:
                continue
            if rule.match_mode == "exact":
                if normalized_query == rule.keyword:
                    candidates.add(rule.intent_code)
                continue
            if rule.keyword in normalized_query:
                candidates.add(rule.intent_code)
        return candidates

    @staticmethod
    def _select_primary_target(intent_priority: dict[str, int], candidates: set[str]) -> str:
        """按优先级选择单一主命中。"""

        return min(
            candidates,
            key=lambda intent_code: (intent_priority.get(intent_code, 9999), intent_code),
        )


def _normalize_query_text(raw_query: str) -> str:
    """归一化查询文本。

    功能：
        词典命中依赖 contains 判定。这里先做统一归一化，减少全角空格、换行、大小写
        差异带来的漏召回。
    """

    collapsed = re.sub(r"\s+", "", (raw_query or "").strip())
    return collapsed.lower()


def _normalize_rule_keyword(raw_keyword: str) -> str:
    """归一化词典关键词。"""

    return _normalize_query_text(raw_keyword.replace("★", ""))


def _normalize_optional_text(value: object) -> str | None:
    """将可选文本列归一化为 `str | None`。"""

    text = str(value).strip() if value is not None else ""
    return text or None
