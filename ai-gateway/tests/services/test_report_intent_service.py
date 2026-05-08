from __future__ import annotations

import pytest

from app.services.report_intent_service import ReportIntentResolution, ReportIntentService


class _FakeCursor:
    """模拟 aiomysql.DictCursor 的最小行为。"""

    def __init__(self, rows_by_sql: dict[str, list[dict[str, object]]]) -> None:
        self._rows_by_sql = rows_by_sql
        self._current_sql: str | None = None

    async def __aenter__(self) -> _FakeCursor:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    async def execute(self, sql: str) -> None:
        self._current_sql = sql.strip()

    async def fetchall(self) -> list[dict[str, object]]:
        return self._rows_by_sql.get(self._current_sql or "", [])


class _FakeConnection:
    def __init__(self, rows_by_sql: dict[str, list[dict[str, object]]]) -> None:
        self._rows_by_sql = rows_by_sql

    async def __aenter__(self) -> _FakeConnection:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    def cursor(self, _cursor_cls):  # noqa: ANN001
        return _FakeCursor(self._rows_by_sql)


class _FakePoolAcquire:
    def __init__(self, rows_by_sql: dict[str, list[dict[str, object]]]) -> None:
        self._rows_by_sql = rows_by_sql

    async def __aenter__(self) -> _FakeConnection:
        return _FakeConnection(self._rows_by_sql)

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


class _FakePool:
    def __init__(self, rows_by_sql: dict[str, list[dict[str, object]]]) -> None:
        self._rows_by_sql = rows_by_sql

    def acquire(self) -> _FakePoolAcquire:
        return _FakePoolAcquire(self._rows_by_sql)


@pytest.mark.asyncio
async def test_report_intent_service_resolves_metric_focus_first() -> None:
    """metric-focus 命中必须压过通用分组命中。"""

    rows_by_sql = {
        """
SELECT intent_code, priority
FROM report_intent_definition
WHERE status = 'active' AND enabled = 1
ORDER BY priority ASC, intent_code ASC
""".strip(): [
            {"intent_code": "metric-focus", "priority": 10},
            {"intent_code": "vitals", "priority": 60},
            {"intent_code": "overview", "priority": 90},
        ],
        """
SELECT intent_code, keyword, match_mode, sort_order
FROM report_intent_keyword
WHERE status = 'active' AND enabled = 1
ORDER BY intent_code ASC, sort_order ASC, id ASC
""".strip(): [
            {"intent_code": "vitals", "keyword": "体征", "match_mode": "contains", "sort_order": 10},
        ],
        """
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
""".strip(): [
            {
                "target_intent_code": "metric-focus",
                "keyword": "糖化血红蛋白",
                "metric_code": "040517",
                "standard_metric_name": "糖化血红蛋白",
                "abbreviation": "HbAlc",
                "aliases": "糖化血红蛋白(HbAlc)",
                "metric_category": "肝功能",
                "common_unit": None,
                "result_type": "mixed",
                "sort_order": 10,
            }
        ],
    }

    service = ReportIntentService(pool=_FakePool(rows_by_sql))  # type: ignore[arg-type]
    result = await service.resolve(query="糖化血红蛋白")
    assert result == ReportIntentResolution(
        target_id="metric-focus",
        focused_metric="糖化血红蛋白",
        target_year=None,
    )


@pytest.mark.asyncio
async def test_report_intent_service_resolves_vitals_with_keywords() -> None:
    """普通关键词命中返回对应 targetId。"""

    rows_by_sql = {
        """
SELECT intent_code, priority
FROM report_intent_definition
WHERE status = 'active' AND enabled = 1
ORDER BY priority ASC, intent_code ASC
""".strip(): [
            {"intent_code": "metric-focus", "priority": 10},
            {"intent_code": "vitals", "priority": 60},
            {"intent_code": "overview", "priority": 90},
        ],
        """
SELECT intent_code, keyword, match_mode, sort_order
FROM report_intent_keyword
WHERE status = 'active' AND enabled = 1
ORDER BY intent_code ASC, sort_order ASC, id ASC
""".strip(): [
            {"intent_code": "vitals", "keyword": "体征", "match_mode": "contains", "sort_order": 10},
            {"intent_code": "overview", "keyword": "概况", "match_mode": "contains", "sort_order": 10},
        ],
        """
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
""".strip(): [],
    }
    service = ReportIntentService(pool=_FakePool(rows_by_sql))  # type: ignore[arg-type]
    result = await service.resolve(query="查一般体征")
    assert result == ReportIntentResolution(
        target_id="vitals",
        focused_metric=None,
        target_year=None,
    )


@pytest.mark.asyncio
async def test_report_intent_service_fallbacks_to_overview_on_no_hit() -> None:
    """无命中时固定兜底 overview。"""

    rows_by_sql = {
        """
SELECT intent_code, priority
FROM report_intent_definition
WHERE status = 'active' AND enabled = 1
ORDER BY priority ASC, intent_code ASC
""".strip(): [
            {"intent_code": "overview", "priority": 90},
        ],
        """
SELECT intent_code, keyword, match_mode, sort_order
FROM report_intent_keyword
WHERE status = 'active' AND enabled = 1
ORDER BY intent_code ASC, sort_order ASC, id ASC
""".strip(): [],
        """
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
""".strip(): [],
    }
    service = ReportIntentService(pool=_FakePool(rows_by_sql))  # type: ignore[arg-type]
    result = await service.resolve(query="帮我看看")
    assert result == ReportIntentResolution(
        target_id="overview",
        focused_metric=None,
        target_year=None,
    )
