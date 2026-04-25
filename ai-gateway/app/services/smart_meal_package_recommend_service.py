"""智能订餐套餐推荐服务。

功能：
    提供「硬过滤 + 全量排序 + 重排」的一体化推荐链路，
    在候选规模较小（单餐次约几十个）的约束下，优先保证可解释性和上线稳定性。
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any

import aiomysql
import httpx

from app.core.config import settings
from app.models.schemas import SmartMealMealType
from app.services.health_quadrant_mysql_pools import HealthQuadrantMySQLPools

logger = logging.getLogger(__name__)

_DIAGNOSIS_ENDPOINT = f"{settings.dw_route_url.rstrip('/')}/customer-diagnosis-items"
_INTOLERANCE_ENDPOINT = f"{settings.dw_route_url.rstrip('/')}/food-intolerance-items"

_MEAL_TYPE_ALIASES = {
    "BREAKFAST": SmartMealMealType.BREAKFAST.value,
    "早餐": SmartMealMealType.BREAKFAST.value,
    "LUNCH": SmartMealMealType.LUNCH.value,
    "LAUCH": SmartMealMealType.LUNCH.value,
    "午餐": SmartMealMealType.LUNCH.value,
    "DINNER": SmartMealMealType.DINNER.value,
    "晚餐": SmartMealMealType.DINNER.value,
}

_PACKAGE_CODE_KEYS = ("package_code", "packageCode", "code")
_MEAL_TYPE_KEYS = ("meal_type", "mealType", "meal_slot", "mealSlot", "meal")
_DIAGNOSIS_NAME_KEYS = ("diagnosis", "diagnosis_name", "diagnosisName", "disease", "symptom", "name")
_DIAGNOSIS_TIME_KEYS = (
    "diagnosis_time",
    "diagnosisTime",
    "confirmed_time",
    "confirmedTime",
    "create_time",
    "createTime",
    "update_time",
    "updateTime",
)


@dataclass(slots=True)
class _DiagnosisSignal:
    """诊断信号。

    功能：
        把外部诊断接口的异构字段压平成统一结构，便于按时间衰减计算诊断匹配分。
    """

    name: str
    days_since: int


@dataclass(slots=True)
class _BehaviorSignal:
    """用户行为信号。"""

    package_code: str
    meal_type: str
    reservation_date: datetime


@dataclass(slots=True)
class _PackageCandidate:
    """套餐候选。

    功能：
        聚合套餐主信息与菜品/食材信息，供硬过滤、排序和重排共用，
        避免每个阶段重复拼接与重复解析 JSON。
    """

    package_code: str
    package_name: str
    package_type: str
    meal_type: str
    create_time: datetime | None
    dish_names: set[str]
    ingredient_names: set[str]

    @property
    def search_text(self) -> str:
        """返回用于关键词匹配的统一检索文本。"""

        parts = [self.package_name, self.package_type]
        parts.extend(sorted(self.dish_names))
        parts.extend(sorted(self.ingredient_names))
        return " ".join(part for part in parts if part)

    @property
    def is_new_package(self) -> bool:
        """是否属于新套餐。"""

        if self.create_time is None:
            return False
        return self.create_time >= datetime.now() - timedelta(days=10)


@dataclass(slots=True)
class _ScoredPackage:
    """排序阶段输出。"""

    package: _PackageCandidate
    match_score: float


class SmartMealPackageRecommendServiceError(RuntimeError):
    """智能订餐套餐推荐服务异常。"""


class SmartMealPackageRecommendService:
    """智能订餐套餐推荐服务。

    功能：
        在网关侧实现套餐推荐核心决策链路，统一处理：
        1) 诊断/不耐受外部依赖；
        2) 硬过滤；
        3) 特征打分；
        4) 重排约束。

    Args:
        mysql_pools: 可选共享连接池，未传入时服务内部自建并负责关闭。

    Edge Cases:
        1. 外部接口超时/失败时，不中断主链路，只做降级与日志记录。
        2. 候选套餐被硬过滤清空时，返回空结果而非业务异常。
        3. 订单 JSON 数据脏化时，丢弃单条脏记录，避免污染整批计算。
    """

    def __init__(self, *, mysql_pools: HealthQuadrantMySQLPools | None = None) -> None:
        self._mysql_pools = mysql_pools or HealthQuadrantMySQLPools(minsize=1, maxsize=3)
        self._owned_mysql_pools = mysql_pools is None
        self._http_client: httpx.AsyncClient | None = None

    async def warmup(self) -> None:
        """预热连接池。

        功能：
            推荐接口会同时访问套餐和订单表，预热能把首请求建连成本前置，降低首包抖动。
        """

        await self._mysql_pools.get_ods_pool()

    async def close(self) -> None:
        """释放服务资源。"""

        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        if self._owned_mysql_pools:
            await self._mysql_pools.close()

    async def recommend_packages(
        self,
        *,
        id_card_no: str,
        meal_type: str,
        age: int | None,
        sex: str | None,
        health_tags: list[str],
        diet_preferences: list[str],
        dietary_restrictions: list[str],
        abnormal_indicators: list[dict[str, Any]],
        trace_id: str | None = None,
    ) -> list[dict[str, str | float]]:
        """推荐套餐。

        功能：
            执行完整推荐链路并返回 Top3 结果。该方法是服务对外唯一编排入口，
            目的是把“规则、降级、可观测”集中在一个事务化流程中，避免调用方自己拼链路。

        Args:
            id_card_no: 客户身份证号（原值）。
            meal_type: 餐次（BREAKFAST/LUNCH/DINNER）。
            age: 年龄（可选）。
            sex: 性别（可选）。
            health_tags: 健康标签列表。
            diet_preferences: 用餐偏好列表。
            dietary_restrictions: 忌口自然语言列表。
            abnormal_indicators: 异常指标列表（type/value/unit）。
            trace_id: 链路追踪 ID。

        Returns:
            Top3 套餐列表。每项包含 `package_code/package_name/match_score`。

        Raises:
            SmartMealPackageRecommendServiceError:
                - `bad_request`: 参数不合法
                - `db_failed`: 数据查询失败
                - `external_timeout`: 外部接口超时（最终会被内部降级吞掉）
                - `external_failed`: 外部接口失败（最终会被内部降级吞掉）
        """

        started_at = perf_counter()
        normalized_meal_type = _normalize_meal_type(meal_type)
        if not id_card_no.strip():
            raise SmartMealPackageRecommendServiceError("bad_request: id_card_no 不能为空")
        if not normalized_meal_type:
            raise SmartMealPackageRecommendServiceError(f"bad_request: meal_type 非法 meal_type={meal_type}")

        # 1. 先拉外部增强信息；诊断/不耐受任一失败都降级，不阻断推荐主链路。
        diagnoses, diagnosis_fetch_status = await self._safe_fetch_diagnoses(id_card_no=id_card_no, trace_id=trace_id)
        intolerance_terms, intolerance_fetch_status = await self._safe_fetch_intolerance_terms(
            id_card_no=id_card_no,
            dietary_restrictions=dietary_restrictions,
            trace_id=trace_id,
        )

        # 2. 拉取候选套餐全集（按餐次）并执行硬过滤。
        candidates = await self._query_candidates_by_meal_type(meal_type=normalized_meal_type)
        if not candidates:
            logger.info(
                "smart meal recommend no candidates trace_id=%s id_card_no=%s meal_type=%s",
                trace_id,
                id_card_no,
                normalized_meal_type,
            )
            return []

        filtered_candidates, filtered_by_intolerance, filtered_by_high_risk = self._apply_hard_filters(
            candidates=candidates,
            intolerance_terms=intolerance_terms,
            abnormal_indicators=abnormal_indicators,
        )
        if not filtered_candidates:
            logger.info(
                "smart meal recommend hard-filter empty trace_id=%s id_card_no=%s meal_type=%s candidate_total=%s",
                trace_id,
                id_card_no,
                normalized_meal_type,
                len(candidates),
            )
            return []

        # 3. 行为信号用于复购、疲劳和协同信号代理。
        behavior_signals = await self._query_customer_behavior_signals(
            id_card_no=id_card_no,
            meal_type=normalized_meal_type,
        )

        scored_candidates = self._score_candidates(
            candidates=filtered_candidates,
            health_tags=health_tags,
            diet_preferences=diet_preferences,
            abnormal_indicators=abnormal_indicators,
            diagnoses=diagnoses,
            behavior_signals=behavior_signals,
            age=age,
            sex=sex,
        )
        if not scored_candidates:
            return []

        reranked = self._rerank_candidates(scored_candidates=scored_candidates, behavior_signals=behavior_signals)

        duration_ms = int((perf_counter() - started_at) * 1000)
        logger.info(
            "smart meal recommend completed trace_id=%s id_card_no=%s meal_type=%s "
            "candidate_total_before_filter=%s candidate_total_after_filter=%s filtered_by_intolerance_count=%s "
            "filtered_by_high_risk_count=%s diagnosis_fetch_status=%s intolerance_fetch_status=%s "
            "new_package_in_top3=%s no_candidate=%s total_latency_ms=%s",
            trace_id,
            id_card_no,
            normalized_meal_type,
            len(candidates),
            len(filtered_candidates),
            filtered_by_intolerance,
            filtered_by_high_risk,
            diagnosis_fetch_status,
            intolerance_fetch_status,
            int(
                any(
                    item.package.is_new_package and item.match_score >= 70
                    for item in reranked
                )
            ),
            int(not reranked),
            duration_ms,
        )
        return [
            {
                "package_code": item.package.package_code,
                "package_name": item.package.package_name,
                "match_score": item.match_score,
            }
            for item in reranked
        ]

    async def _safe_fetch_diagnoses(self, *, id_card_no: str, trace_id: str | None) -> tuple[list[_DiagnosisSignal], str]:
        """安全拉取诊断信号。

        功能：
            诊断接口是增强信号，不是主流程硬依赖。这里把异常统一降级为“空诊断 + 状态码”，
            避免外部依赖抖动直接打断推荐服务。
        """

        try:
            return await self._fetch_diagnoses(id_card_no=id_card_no, trace_id=trace_id), "ok"
        except SmartMealPackageRecommendServiceError as exc:
            logger.warning(
                "smart meal recommend diagnosis degraded trace_id=%s id_card_no=%s reason=%s",
                trace_id,
                id_card_no,
                exc,
            )
            return [], "error"

    async def _safe_fetch_intolerance_terms(
        self,
        *,
        id_card_no: str,
        dietary_restrictions: list[str],
        trace_id: str | None,
    ) -> tuple[set[str], str]:
        """安全拉取不耐受与忌口词项。

        功能：
            忌口是硬过滤输入。即使外部接口失败，也应继续保留请求体中的忌口词，
            这样至少不会把用户显式声明的禁忌完全丢掉。
        """

        local_terms = _normalize_terms(dietary_restrictions)
        try:
            remote_terms = await self._fetch_intolerance_terms(id_card_no=id_card_no, trace_id=trace_id)
            return local_terms | remote_terms, "ok"
        except SmartMealPackageRecommendServiceError as exc:
            logger.warning(
                "smart meal recommend intolerance degraded trace_id=%s id_card_no=%s reason=%s",
                trace_id,
                id_card_no,
                exc,
            )
            return local_terms, "error"

    async def _fetch_diagnoses(self, *, id_card_no: str, trace_id: str | None) -> list[_DiagnosisSignal]:
        """调用诊断接口并转换为诊断信号。"""

        client = self._get_http_client()
        headers: dict[str, str] = {}
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        try:
            response = await client.get(_DIAGNOSIS_ENDPOINT, params={"idcard_no": id_card_no}, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise SmartMealPackageRecommendServiceError("external_timeout: 诊断接口超时") from exc
        except Exception as exc:  # noqa: BLE001
            raise SmartMealPackageRecommendServiceError("external_failed: 诊断接口调用失败") from exc

        rows = _extract_rows(payload)
        now = datetime.now()
        signals: list[_DiagnosisSignal] = []
        for row in rows:
            diagnosis_name = _pick_first_text(row, _DIAGNOSIS_NAME_KEYS)
            if not diagnosis_name:
                continue
            diagnosis_time = _pick_first_datetime(row, _DIAGNOSIS_TIME_KEYS)
            days_since = (now - diagnosis_time).days if diagnosis_time else 365
            signals.append(_DiagnosisSignal(name=diagnosis_name, days_since=max(days_since, 0)))
        return signals

    async def _fetch_intolerance_terms(self, *, id_card_no: str, trace_id: str | None) -> set[str]:
        """调用不耐受接口并提取可匹配词项。"""

        client = self._get_http_client()
        headers: dict[str, str] = {}
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        try:
            response = await client.get(_INTOLERANCE_ENDPOINT, params={"idcard_no": id_card_no}, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise SmartMealPackageRecommendServiceError("external_timeout: 不耐受接口超时") from exc
        except Exception as exc:  # noqa: BLE001
            raise SmartMealPackageRecommendServiceError("external_failed: 不耐受接口调用失败") from exc

        rows = _extract_rows(payload)
        terms: set[str] = set()
        for row in rows:
            if isinstance(row, str):
                terms.update(_extract_food_terms(row))
                continue
            if isinstance(row, dict):
                candidate_text = " ".join(str(value) for value in row.values() if isinstance(value, str))
                terms.update(_extract_food_terms(candidate_text))
        return _normalize_terms(list(terms))

    async def _query_candidates_by_meal_type(self, *, meal_type: str) -> list[_PackageCandidate]:
        """按餐次查询候选套餐。

        功能：
            优先按数据库餐次字段过滤；若线上分支存在旧表结构（缺 meal_type 列），
            自动降级为全量读取后在 Python 侧推断餐次，保证灰度期间接口可用。
        """

        pool = await self._mysql_pools.get_ods_pool()
        sql_with_meal_type = """
            SELECT
                p.package_code,
                p.package_name,
                p.package_type,
                p.meal_type,
                p.create_time,
                d.dish_name,
                d.ingredient_json
            FROM meal_package AS p
            LEFT JOIN meal_package_dish_binding AS db ON p.id = db.package_id
            LEFT JOIN meal_dish AS d ON db.dish_id = d.id
            WHERE p.status = 1
              AND UPPER(COALESCE(p.meal_type, '')) = %s
              AND (db.status = 1 OR db.status IS NULL)
              AND (d.status = 1 OR d.status IS NULL)
        """
        sql_fallback = """
            SELECT
                p.package_code,
                p.package_name,
                p.package_type,
                p.create_time,
                d.dish_name,
                d.ingredient_json
            FROM meal_package AS p
            LEFT JOIN meal_package_dish_binding AS db ON p.id = db.package_id
            LEFT JOIN meal_dish AS d ON db.dish_id = d.id
            WHERE p.status = 1
              AND (db.status = 1 OR db.status IS NULL)
              AND (d.status = 1 OR d.status IS NULL)
        """

        rows: list[dict[str, Any]] = []
        try:
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql_with_meal_type, (meal_type,))
                    rows = await cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            # 兼容历史表结构：旧分支可能没有 meal_type 列，此时降级为全量读取+文本推断。
            if "Unknown column" not in str(exc):
                raise SmartMealPackageRecommendServiceError("db_failed: 套餐候选查询失败") from exc
            logger.warning("smart meal recommend fallback query used reason=%s", exc)
            try:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        await cursor.execute(sql_fallback)
                        rows = await cursor.fetchall()
            except Exception as fallback_exc:  # noqa: BLE001
                raise SmartMealPackageRecommendServiceError("db_failed: 套餐候选查询失败") from fallback_exc

        candidate_map: dict[str, _PackageCandidate] = {}
        for row in rows:
            package_code = _normalize_text(row.get("package_code"))
            package_name = _normalize_text(row.get("package_name"))
            if not package_code or not package_name:
                continue
            row_meal_type = _normalize_meal_type(row.get("meal_type")) or _infer_meal_type(
                package_code=package_code,
                package_name=package_name,
            )
            if row_meal_type and row_meal_type != meal_type:
                continue

            candidate = candidate_map.get(package_code)
            if candidate is None:
                candidate = _PackageCandidate(
                    package_code=package_code,
                    package_name=package_name,
                    package_type=_normalize_text(row.get("package_type")) or "UNKNOWN",
                    meal_type=row_meal_type or meal_type,
                    create_time=_parse_datetime(row.get("create_time")),
                    dish_names=set(),
                    ingredient_names=set(),
                )
                candidate_map[package_code] = candidate

            dish_name = _normalize_text(row.get("dish_name"))
            if dish_name:
                candidate.dish_names.add(dish_name)
            for ingredient in _extract_ingredient_names(row.get("ingredient_json")):
                candidate.ingredient_names.add(ingredient)

        return list(candidate_map.values())

    async def _query_customer_behavior_signals(self, *, id_card_no: str, meal_type: str) -> list[_BehaviorSignal]:
        """查询客户近 90 天行为信号。

        功能：
            当前业务表在不同环境常见身份证列命名差异（`id_card_no` / `idcard_no`），
            这里按“多候选 SQL 依次尝试”的方式兜底，保证跨环境部署可运行。
        """

        pool = await self._mysql_pools.get_ods_pool()
        filter_templates = [
            "id_card_no = %s",
            "idcard_no = %s",
            "encrypted_id_card = %s",
        ]

        rows: list[dict[str, Any]] = []
        for filter_sql in filter_templates:
            sql = f"""
                SELECT reservation_date, confirmed_package
                FROM meal_order
                WHERE deleted = 0
                  AND reservation_date IS NOT NULL
                  AND reservation_date >= DATE_SUB(NOW(), INTERVAL 90 DAY)
                  AND {filter_sql}
                ORDER BY reservation_date DESC
                LIMIT 500
            """
            try:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        await cursor.execute(sql, (id_card_no,))
                        rows = await cursor.fetchall()
                break
            except Exception as exc:  # noqa: BLE001
                if "Unknown column" in str(exc):
                    continue
                raise SmartMealPackageRecommendServiceError("db_failed: 客户行为查询失败") from exc

        signals: list[_BehaviorSignal] = []
        for row in rows:
            reservation_date = _parse_datetime(row.get("reservation_date"))
            if reservation_date is None:
                continue
            for package_code, row_meal_type in _extract_package_codes_from_confirmed_package(row.get("confirmed_package")):
                if row_meal_type != meal_type:
                    continue
                signals.append(
                    _BehaviorSignal(
                        package_code=package_code,
                        meal_type=row_meal_type,
                        reservation_date=reservation_date,
                    )
                )
        signals.sort(key=lambda item: item.reservation_date, reverse=True)
        return signals

    def _apply_hard_filters(
        self,
        *,
        candidates: list[_PackageCandidate],
        intolerance_terms: set[str],
        abnormal_indicators: list[dict[str, Any]],
    ) -> tuple[list[_PackageCandidate], int, int]:
        """执行硬过滤。

        功能：
            先过滤食材不耐受，再过滤高风险硬禁配。硬过滤放在排序前，
            是为了保证后续所有打分策略都不会把“临床禁配项”重新抬上来。
        """

        filtered: list[_PackageCandidate] = []
        filtered_by_intolerance = 0
        filtered_by_high_risk = 0
        for candidate in candidates:
            if self._contains_intolerance(candidate=candidate, intolerance_terms=intolerance_terms):
                filtered_by_intolerance += 1
                continue
            if self._is_high_risk_blocked(candidate=candidate, abnormal_indicators=abnormal_indicators):
                filtered_by_high_risk += 1
                continue
            filtered.append(candidate)
        return filtered, filtered_by_intolerance, filtered_by_high_risk

    def _score_candidates(
        self,
        *,
        candidates: list[_PackageCandidate],
        health_tags: list[str],
        diet_preferences: list[str],
        abnormal_indicators: list[dict[str, Any]],
        diagnoses: list[_DiagnosisSignal],
        behavior_signals: list[_BehaviorSignal],
        age: int | None,
        sex: str | None,
    ) -> list[_ScoredPackage]:
        """计算候选套餐绝对评分。

        功能：
            评分阶段使用固定权重，确保上线初期具备可解释性与可回放性。
            当异常指标缺失时执行权重重分配，避免“空指标字段”把整体分数硬拉低。
        """

        repurchase_counter = Counter(signal.package_code for signal in behavior_signals)
        has_abnormal = any(_normalize_text(item.get("type")) for item in abnormal_indicators)

        scored: list[_ScoredPackage] = []
        for candidate in candidates:
            f_health = _keyword_overlap_score(health_tags, candidate.search_text)
            f_abnormal = self._score_abnormal_match(candidate=candidate, abnormal_indicators=abnormal_indicators)
            f_preference = _keyword_overlap_score(diet_preferences, candidate.search_text)
            f_diagnosis = self._score_diagnosis_match(candidate=candidate, diagnoses=diagnoses)
            f_repurchase = min(math.log1p(repurchase_counter.get(candidate.package_code, 0)) / math.log1p(10), 1.0)

            # 协同过滤在 V1 没有独立近线特征仓；这里用“历史行为 + 诊断命中”做代理信号，
            # 目的是先保证线上链路完整，再在后续版本替换为真实邻居/物品图特征。
            f_user_cf = _clip01(0.6 * f_diagnosis + 0.4 * f_repurchase)
            f_item_cf = _clip01(0.7 * f_repurchase + 0.3 * _dish_overlap_score(candidate=candidate, behaviors=behavior_signals))

            if has_abnormal:
                base = (
                    0.26 * f_health
                    + 0.22 * f_abnormal
                    + 0.14 * f_preference
                    + 0.14 * f_diagnosis
                    + 0.08 * f_repurchase
                    + 0.08 * f_user_cf
                    + 0.08 * f_item_cf
                )
            else:
                base = (
                    0.38 * f_health
                    + 0.14 * f_preference
                    + 0.24 * f_diagnosis
                    + 0.08 * f_repurchase
                    + 0.08 * f_user_cf
                    + 0.08 * f_item_cf
                )

            # 绝对评分输出用于前端展示，重排只改顺序不改 match_score，便于业务解释“基础匹配度”。
            match_score = round(100 * _clip01(base), 2)
            scored.append(_ScoredPackage(package=candidate, match_score=match_score))

        scored.sort(key=lambda item: (-item.match_score, item.package.package_code))
        return scored

    def _rerank_candidates(
        self,
        *,
        scored_candidates: list[_ScoredPackage],
        behavior_signals: list[_BehaviorSignal],
    ) -> list[_ScoredPackage]:
        """执行重排并返回 Top3。

        功能：
            重排聚焦三个业务目标：
            1) 同类型多样性；
            2) 历史疲劳抑制；
            3) 新套餐受控探索。
        """

        latest_days = _latest_days_by_package(behavior_signals)
        remaining = list(scored_candidates)
        selected: list[_ScoredPackage] = []
        exploration_used = False

        while remaining and len(selected) < 3:
            best_index = 0
            best_rerank_score = float("-inf")
            for idx, candidate in enumerate(remaining):
                same_type_count = sum(
                    1
                    for picked in selected
                    if picked.package.package_type == candidate.package.package_type and candidate.package.package_type
                )

                # Magic number 8/4 来自当前业务策略：首次同类型重复就要明显降权，
                # 第二次重复继续追加惩罚，避免 Top3 被单类型垄断。
                penalty_type_diversity = 8 + max(same_type_count - 1, 0) * 4 if same_type_count > 0 else 0

                fatigue_days = latest_days.get(candidate.package.package_code)
                penalty_fatigue = 0
                if fatigue_days is not None and fatigue_days <= 14:
                    penalty_fatigue = 6
                elif fatigue_days is not None and fatigue_days <= 30:
                    penalty_fatigue = 3

                bonus_explore = 0
                if (
                    not exploration_used
                    and candidate.package.is_new_package
                    and candidate.match_score >= 70
                ):
                    bonus_explore = 4

                rerank_score = candidate.match_score + bonus_explore - penalty_type_diversity - penalty_fatigue
                if rerank_score > best_rerank_score:
                    best_index = idx
                    best_rerank_score = rerank_score
                    continue
                if math.isclose(rerank_score, best_rerank_score, rel_tol=0.0, abs_tol=1e-9):
                    best = remaining[best_index]
                    if candidate.match_score > best.match_score:
                        best_index = idx
                    elif math.isclose(candidate.match_score, best.match_score, rel_tol=0.0, abs_tol=1e-9):
                        if candidate.package.package_code < best.package.package_code:
                            best_index = idx

            picked = remaining.pop(best_index)
            if picked.package.is_new_package and picked.match_score >= 70 and not exploration_used:
                exploration_used = True
            selected.append(picked)

        return selected

    def _contains_intolerance(self, *, candidate: _PackageCandidate, intolerance_terms: set[str]) -> bool:
        """判断套餐是否命中不耐受项。"""

        if not intolerance_terms:
            return False
        for ingredient in candidate.ingredient_names:
            normalized_ingredient = ingredient.lower()
            for term in intolerance_terms:
                normalized_term = term.lower()
                if normalized_term in normalized_ingredient or normalized_ingredient in normalized_term:
                    return True
        return False

    def _is_high_risk_blocked(self, *, candidate: _PackageCandidate, abnormal_indicators: list[dict[str, Any]]) -> bool:
        """判断套餐是否命中高风险硬禁配。

        功能：
            V1 没有完整营养成分表，先采用“异常指标阈值 + 套餐关键词”的保守规则，
            把明显高风险套餐在排序前剔除，防止推荐结果与医疗安全目标冲突。
        """

        high_risk_types = _detect_high_risk_types(abnormal_indicators)
        if not high_risk_types:
            return False

        package_text = f"{candidate.package_name} {candidate.package_type} {' '.join(candidate.dish_names)}".lower()
        risk_keywords = {
            "blood_glucose": ("糖", "甜", "甜品", "奶茶"),
            "blood_lipid": ("油炸", "肥", "高脂", "奶油"),
            "kidney_function": ("高钠", "腌", "重口"),
            "weight_condition": ("高热量", "高脂", "重油"),
        }
        for risk_type in high_risk_types:
            for keyword in risk_keywords.get(risk_type, ()):
                if keyword in package_text:
                    return True
        return False

    def _score_abnormal_match(self, *, candidate: _PackageCandidate, abnormal_indicators: list[dict[str, Any]]) -> float:
        """计算异常指标匹配分。"""

        types = {_normalize_text(item.get("type")) for item in abnormal_indicators if _normalize_text(item.get("type"))}
        if not types:
            return 0.0

        match_keywords = {
            "blood_glucose": ("控糖", "低糖", "粗粮"),
            "blood_lipid": ("轻脂", "低脂", "清淡"),
            "kidney_function": ("低钠", "清淡", "优蛋白"),
            "weight_condition": ("轻脂", "控卡", "高纤"),
        }
        matched = 0
        package_text = candidate.search_text.lower()
        for indicator_type in types:
            keywords = match_keywords.get(indicator_type, ())
            if any(keyword in package_text for keyword in keywords):
                matched += 1
        return _clip01(matched / max(len(types), 1))

    def _score_diagnosis_match(self, *, candidate: _PackageCandidate, diagnoses: list[_DiagnosisSignal]) -> float:
        """计算诊断匹配分。"""

        if not diagnoses:
            return 0.0

        package_text = candidate.search_text.lower()
        weighted_sum = 0.0
        total_weight = 0.0
        for signal in diagnoses:
            weight = math.exp(-signal.days_since / 180)
            total_weight += weight
            normalized_name = signal.name.lower()
            if normalized_name and normalized_name in package_text:
                weighted_sum += weight
        if total_weight <= 0:
            return 0.0
        return _clip01(weighted_sum / total_weight)

    def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端单例。"""

        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
    return ""


def _normalize_meal_type(raw_meal_type: Any) -> str:
    text = _normalize_text(raw_meal_type).upper()
    return _MEAL_TYPE_ALIASES.get(text, "")


def _infer_meal_type(*, package_code: str, package_name: str) -> str:
    """从套餐编码或名称推断餐次。"""

    haystack = f"{package_code} {package_name}".upper()
    if "BREAKFAST" in haystack or "早餐" in haystack:
        return SmartMealMealType.BREAKFAST.value
    if "LUNCH" in haystack or "LAUCH" in haystack or "午餐" in haystack:
        return SmartMealMealType.LUNCH.value
    if "DINNER" in haystack or "晚餐" in haystack:
        return SmartMealMealType.DINNER.value
    return ""


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = _normalize_text(value)
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _pick_first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _normalize_text(data.get(key))
        if value:
            return value
    return ""


def _pick_first_datetime(data: dict[str, Any], keys: tuple[str, ...]) -> datetime | None:
    for key in keys:
        parsed = _parse_datetime(data.get(key))
        if parsed is not None:
            return parsed
    return None


def _extract_rows(payload: Any) -> list[Any]:
    """从外部响应提取行数据。

    功能：
        对接接口存在 `rows/data/list` 多种返回结构，统一在这里做适配，避免业务逻辑
        到处判断响应结构分支。
    """

    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("rows", "data", "list", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for nested_key in ("rows", "data", "list", "items"):
                nested_value = value.get(nested_key)
                if isinstance(nested_value, list):
                    return nested_value
    return []


def _extract_food_terms(text: str) -> set[str]:
    """从自然语言中抽取食材词。

    功能：
        忌口和不耐受输入经常是自由文本（如“花生过敏、不吃虾”）。
        这里做轻量文本归一化，尽量把真正食材词抽出来用于食材匹配。
    """

    cleaned = _normalize_text(text)
    if not cleaned:
        return set()

    normalized = cleaned
    for token in ("过敏", "不吃", "忌口", "不能吃", "避免", "禁食"):
        normalized = normalized.replace(token, " ")
    normalized = re.sub(r"[()（）:：,，;；|/]+", " ", normalized)
    return {part.strip() for part in normalized.split() if len(part.strip()) >= 1}


def _normalize_terms(values: list[str]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        terms.update(_extract_food_terms(value))
    return {term.lower() for term in terms if term}


def _extract_ingredient_names(raw_ingredient_json: Any) -> list[str]:
    """解析食材 JSON。"""

    payload = raw_ingredient_json
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="ignore")
    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return []
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []

    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []

    ingredients: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        ingredient_name = _pick_first_text(item, ("ingredientName", "ingredient_name", "ingredient", "name"))
        if ingredient_name:
            ingredients.append(ingredient_name)
    return ingredients


def _extract_package_codes_from_confirmed_package(raw_confirmed_package: Any) -> list[tuple[str, str]]:
    """从 confirmed_package 中抽取 `package_code + meal_type`。

    功能：
        线上 `confirmed_package` 可能是嵌套 JSON、数组或对象混排，本函数递归解析，
        用于把行为数据规范化为统一的统计输入。
    """

    payload = raw_confirmed_package
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="ignore")
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return []

    extracted: list[tuple[str, str]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            package_code = _pick_first_text(node, _PACKAGE_CODE_KEYS)
            meal = _normalize_meal_type(_pick_first_text(node, _MEAL_TYPE_KEYS))
            if package_code and meal:
                extracted.append((package_code, meal))
            for value in node.values():
                _walk(value)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload)
    return extracted


def _keyword_overlap_score(tokens: list[str], target_text: str) -> float:
    normalized_tokens = [_normalize_text(token).lower() for token in tokens if _normalize_text(token)]
    if not normalized_tokens:
        return 0.0
    target = target_text.lower()
    hit_count = sum(1 for token in normalized_tokens if token in target)
    return _clip01(hit_count / len(normalized_tokens))


def _dish_overlap_score(candidate: _PackageCandidate, behaviors: list[_BehaviorSignal]) -> float:
    if not behaviors:
        return 0.0
    # V1 只有“套餐级历史”，没有完整的历史菜品快照；因此先用“近期是否吃过该套餐”做简化近邻信号。
    seen_codes = {signal.package_code for signal in behaviors[:3]}
    return 1.0 if candidate.package_code in seen_codes else 0.0


def _detect_high_risk_types(abnormal_indicators: list[dict[str, Any]]) -> set[str]:
    """识别高风险指标类型。

    功能：
        用可配置前的默认阈值兜底医疗安全。阈值故意偏保守，
        目的是先防止明显冲突，再在后续版本改成配置中心可调。
    """

    high_risk: set[str] = set()
    for item in abnormal_indicators:
        indicator_type = _normalize_text(item.get("type"))
        value = item.get("value")
        if indicator_type == "blood_glucose" and isinstance(value, (int, float)) and value >= 11.1:
            high_risk.add(indicator_type)
        if indicator_type == "blood_lipid" and isinstance(value, (int, float)) and value >= 6.2:
            high_risk.add(indicator_type)
        if indicator_type == "kidney_function" and isinstance(value, (int, float)) and value >= 200:
            high_risk.add(indicator_type)
        if indicator_type == "weight_condition" and isinstance(value, (int, float)) and value >= 32:
            high_risk.add(indicator_type)
    return high_risk


def _latest_days_by_package(behaviors: list[_BehaviorSignal]) -> dict[str, int]:
    now = datetime.now()
    latest: dict[str, int] = {}
    for signal in behaviors:
        days = max((now - signal.reservation_date).days, 0)
        existing = latest.get(signal.package_code)
        if existing is None or days < existing:
            latest[signal.package_code] = days
    return latest
