"""智能订餐套餐推荐服务。

功能：
    提供「硬过滤 + 全量排序」的一体化推荐链路，
    在候选规模较小（全量套餐约几十个）的约束下，优先保证可解释性和上线稳定性。
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any

import aiomysql
import httpx

from app.core.config import settings
from app.services.health_quadrant_mysql_pools import HealthQuadrantMySQLPools
from app.services.smart_meal_llm_service import SmartMealLLMService
from app.utils.json_utils import parse_dirty_json_object, summarize_log_text

logger = logging.getLogger(__name__)

_DIAGNOSIS_ENDPOINT = f"{settings.dw_route_url.rstrip('/')}/customer-diagnosis-items"
_INTOLERANCE_ENDPOINT = f"{settings.dw_route_url.rstrip('/')}/food-intolerance-items"

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
class _PackageCandidate:
    """套餐候选。

    功能：
        聚合套餐主信息与菜品/食材信息，供硬过滤、排序和重排共用，
        避免每个阶段重复拼接与重复解析 JSON。
    """

    package_code: str
    package_name: str
    package_type: str
    applicable_people: str
    core_target: str
    nutrition_feature: str
    dish_names: set[str]
    ingredient_names: set[str]

    @property
    def search_text(self) -> str:
        """返回用于关键词匹配的统一检索文本。"""

        parts = [
            self.package_name,
            self.package_type,
            self.applicable_people,
            self.core_target,
            self.nutrition_feature,
        ]
        parts.extend(sorted(self.dish_names))
        parts.extend(sorted(self.ingredient_names))
        return " ".join(part for part in parts if part)


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
        4) Top3 收口。

    Args:
        mysql_pools: 可选共享连接池，未传入时服务内部自建并负责关闭。

    Edge Cases:
        1. 外部接口超时/失败时，不中断主链路，只做降级与日志记录。
        2. 候选套餐被硬过滤清空时，返回空结果而非业务异常。
    """

    def __init__(self, *, mysql_pools: HealthQuadrantMySQLPools | None = None) -> None:
        self._mysql_pools = mysql_pools or HealthQuadrantMySQLPools(minsize=1, maxsize=3)
        self._owned_mysql_pools = mysql_pools is None
        self._http_client: httpx.AsyncClient | None = None
        self._llm_service = SmartMealLLMService()

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
        await self._llm_service.close()
        if self._owned_mysql_pools:
            await self._mysql_pools.close()

    async def recommend_packages(
        self,
        *,
        id_card_no: str,
        age: int | None,
        sex: str | None,
        health_tags: list[str],
        diet_preferences: list[str],
        dietary_restrictions: list[str],
        abnormal_indicators: dict[str, list[str]],
        trace_id: str | None = None,
    ) -> list[dict[str, str | float]]:
        """推荐套餐。

        功能：
            执行完整推荐链路并返回 Top3 结果。该方法是服务对外唯一编排入口，
            目的是把“规则、降级、可观测”集中在一个事务化流程中，避免调用方自己拼链路。

        Args:
            id_card_no: 客户身份证号（原值）。
            age: 年龄（可选，当前仅保留请求契约，不参与评分）。
            sex: 性别（可选，当前仅保留请求契约，不参与评分）。
            health_tags: 健康标签列表。
            diet_preferences: 用餐偏好列表。
            dietary_restrictions: 忌口自然语言列表。
            abnormal_indicators: 异常指标字典（key=异常类别，value=异常描述列表）。
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
        if not id_card_no.strip():
            raise SmartMealPackageRecommendServiceError("bad_request: id_card_no 不能为空")

        # 1. 先拉外部增强信息；诊断/不耐受任一失败都降级，不阻断推荐主链路。
        diagnoses, diagnosis_fetch_status = await self._safe_fetch_diagnoses(id_card_no=id_card_no, trace_id=trace_id)
        intolerance_terms, intolerance_fetch_status = await self._safe_fetch_intolerance_terms(
            id_card_no=id_card_no,
            dietary_restrictions=dietary_restrictions,
            trace_id=trace_id,
        )

        # 2. 拉取当前可售套餐全集并执行硬过滤。
        candidates = await self._query_candidates()
        if not candidates:
            logger.info(
                "smart meal recommend no candidates trace_id=%s id_card_no=%s",
                trace_id,
                id_card_no,
            )
            return []

        filtered_candidates, filtered_by_intolerance, filtered_by_high_risk = self._apply_hard_filters(
            candidates=candidates,
            intolerance_terms=intolerance_terms,
            abnormal_indicators=abnormal_indicators,
        )
        if not filtered_candidates:
            logger.info(
                "smart meal recommend hard-filter empty trace_id=%s id_card_no=%s candidate_total=%s",
                trace_id,
                id_card_no,
                len(candidates),
            )
            return []

        rule_scored_candidates = self._score_candidates(
            candidates=filtered_candidates,
            health_tags=health_tags,
            diet_preferences=diet_preferences,
            abnormal_indicators=abnormal_indicators,
            diagnoses=diagnoses,
            age=age,
            sex=sex,
        )
        if not rule_scored_candidates:
            return []

        llm_ranked_candidates, llm_rank_status, fallback_reason = await self._rank_candidates_with_llm(
            candidates=filtered_candidates,
            rule_scored_candidates=rule_scored_candidates,
            diagnoses=diagnoses,
            age=age,
            sex=sex,
            health_tags=health_tags,
            diet_preferences=diet_preferences,
            abnormal_indicators=abnormal_indicators,
            trace_id=trace_id,
        )
        final_candidates = llm_ranked_candidates if llm_ranked_candidates is not None else rule_scored_candidates[:3]
        ranking_mode = "llm" if llm_ranked_candidates is not None else "rule_fallback"

        duration_ms = int((perf_counter() - started_at) * 1000)
        logger.info(
            "smart meal recommend completed trace_id=%s id_card_no=%s "
            "candidate_total_before_filter=%s candidate_total_after_filter=%s filtered_by_intolerance_count=%s "
            "filtered_by_high_risk_count=%s diagnosis_fetch_status=%s intolerance_fetch_status=%s "
            "ranking_mode=%s llm_rank_status=%s fallback_reason=%s no_candidate=%s total_latency_ms=%s",
            trace_id,
            id_card_no,
            len(candidates),
            len(filtered_candidates),
            filtered_by_intolerance,
            filtered_by_high_risk,
            diagnosis_fetch_status,
            intolerance_fetch_status,
            ranking_mode,
            llm_rank_status,
            fallback_reason,
            int(not final_candidates),
            duration_ms,
        )
        return final_candidates

    async def _rank_candidates_with_llm(
        self,
        *,
        candidates: list[_PackageCandidate],
        rule_scored_candidates: list[_ScoredPackage],
        diagnoses: list[_DiagnosisSignal],
        age: int | None,
        sex: str | None,
        health_tags: list[str],
        diet_preferences: list[str],
        abnormal_indicators: dict[str, list[str]],
        trace_id: str | None,
    ) -> tuple[list[dict[str, str | float]] | None, str, str]:
        """使用 LLM 对硬过滤后的套餐做主排序。

        功能：
            当前版本把 LLM 定位为“主排序器”，规则打分仅在失败场景下兜底。
            这样既能利用套餐文本字段的语义信息，又不会让异常输出直接击穿线上接口。
        """

        prompt = self._build_llm_rank_prompt(
            candidates=candidates,
            diagnoses=diagnoses,
            age=age,
            sex=sex,
            health_tags=health_tags,
            diet_preferences=diet_preferences,
            abnormal_indicators=abnormal_indicators,
        )
        try:
            raw = await self._llm_service.chat(
                messages=[
                    {"role": "system", "content": "你是高净值健康管理系统的核心临床营养风控与排序引擎。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout_seconds=45.0,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("smart meal recommend llm failed trace_id=%s error=%r", trace_id, exc)
            return None, "timeout", "llm_exception"

        payload = parse_dirty_json_object(raw)
        if not payload:
            logger.warning(
                "smart meal recommend llm invalid json trace_id=%s raw=%s",
                trace_id,
                summarize_log_text(raw),
            )
            return None, "invalid_json", "llm_invalid_json"

        validated = self._validate_llm_rank_payload(payload=payload, candidates=candidates)
        if validated is None:
            return None, "invalid_payload", "llm_invalid_payload"
        if len(validated) == 0:
            return None, "empty", "llm_empty"
        return validated, "ok", ""

    def _build_llm_rank_prompt(
        self,
        *,
        candidates: list[_PackageCandidate],
        diagnoses: list[_DiagnosisSignal],
        age: int | None,
        sex: str | None,
        health_tags: list[str],
        diet_preferences: list[str],
        abnormal_indicators: dict[str, list[str]],
    ) -> str:
        """构造套餐排序提示词。

        功能：
            LLM 只处理硬过滤后的安全候选，因此提示词聚焦“匹配度排序”而不是风险判定。
        """

        diagnosis_text = "；".join(
            f"{signal.name}(距今天{signal.days_since}天)"
            for signal in diagnoses
            if signal.name
        ) or "无"
        package_lines = []
        for candidate in candidates:
            package_lines.append(
                json.dumps(
                    {
                        "package_code": candidate.package_code,
                        "package_name": candidate.package_name,
                        "package_type": candidate.package_type,
                        "applicable_people": candidate.applicable_people,
                        "core_target": candidate.core_target,
                        "nutrition_feature": candidate.nutrition_feature,
                    },
                    ensure_ascii=False,
                )
            )

        prompt = f"""
        # Task
        请基于客户的多维度健康特征，对【候选营养套餐】进行医疗安全筛查与靶向匹配，挑选出最适配的 1-3 个套餐并进行打分排序。
        
        # Rules & Logic
        1. 医疗红线（一票否决）：严格交叉比对套餐属性与客户的【异常指标】和【医生诊断】。若套餐成分存在任何医学禁忌（如高尿酸匹配了高嘌呤，糖尿病匹配了高GI），必须直接剔除，严禁输出。
        2. 匹配权重：医疗靶向干预价值（如精准契合慢病调理） > 饮食禁忌规避 > 口味偏好满足。
        3. 评分锚点（0-100分）：
           - 90-100分：完美契合医生诊断的调理方向，且满足客户口味偏好。
           - 75-89分：符合医疗安全且对健康标签有益，但口味匹配度一般。
           - <75分：安全无害，但缺乏针对性的通用健康餐。
        4. 格式要求：仅允许使用提供的 package_code。可以返回 1-3 条，无需凑数。
        5. 结构约束：必须且只能输出合法的 JSON 字符串，严禁包含 Markdown 格式（绝不可输出 ```json 标签）或任何前言后语。
        
        # Output JSON Schema
        {{
          "ranked_packages": [
            {{
              "package_code": "string",
              "reason": "必须先输出思考过程。说明套餐如何契合异常指标与诊断，以及为何给出该分数",
              "match_score": "number (0-100的数字，最多两位小数)"
            }}
          ]
        }}
        
        # Inputs
        客户年龄：{age if age is not None else '未知'}
        客户性别：{sex or '未知'}
        健康标签：{'；'.join(health_tags) if health_tags else '无'}
        口味偏好：{'；'.join(diet_preferences) if diet_preferences else '无'}
        异常指标：{json.dumps(abnormal_indicators, ensure_ascii=False)}
        医生诊断：{diagnosis_text}
        
        候选套餐（包含套餐详情特征）：
        {chr(10).join(package_lines)}
        """

        return prompt

    def _validate_llm_rank_payload(
        self,
        *,
        payload: dict[str, Any],
        candidates: list[_PackageCandidate],
    ) -> list[dict[str, str | float]] | None:
        """校验并规整 LLM 排序结果。

        功能：
            把模型输出收口成稳定契约，避免非法 package_code 或异常分数污染对外响应。
        """

        raw_items = payload.get("ranked_packages")
        if not isinstance(raw_items, list):
            return None

        candidate_index = {candidate.package_code: candidate for candidate in candidates}
        validated: list[dict[str, str | float]] = []
        seen_codes: set[str] = set()
        for item in raw_items:
            if not isinstance(item, dict):
                return None
            package_code = _normalize_text(item.get("package_code"))
            if not package_code or package_code in seen_codes:
                return None
            candidate = candidate_index.get(package_code)
            if candidate is None:
                return None

            score = item.get("match_score")
            if not isinstance(score, (int, float)):
                score = _parse_score(score)
            if score is None:
                return None
            normalized_score = round(max(0.0, min(float(score), 100.0)), 2)
            reason = _normalize_text(item.get("reason"))
            if not reason:
                return None

            seen_codes.add(package_code)
            validated.append(
                {
                    "package_code": candidate.package_code,
                    "package_name": candidate.package_name,
                    "match_score": normalized_score,
                    "reason": reason,
                }
            )
        return validated

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

        rows = payload["rows"]
        now = datetime.now()
        signals: list[_DiagnosisSignal] = []
        for row in rows:
            # 诊断中心历史返回会出现 dict/str 混排；这里做类型兜底，避免因为单条脏数据中断整条推荐链路。
            if isinstance(row, dict):
                diagnosis_name = _pick_first_text(row, _DIAGNOSIS_NAME_KEYS) or _normalize_text(row.get("label_value"))
                if not diagnosis_name:
                    continue
                diagnosis_time = _pick_first_datetime(row, _DIAGNOSIS_TIME_KEYS) or _parse_datetime(row.get("record_date"))
                days_since = (now - diagnosis_time).days if diagnosis_time else 365
                signals.append(_DiagnosisSignal(name=diagnosis_name, days_since=max(days_since, 0)))
                continue
            if isinstance(row, str):
                diagnosis_name = _normalize_text(row)
                if diagnosis_name:
                    signals.append(_DiagnosisSignal(name=diagnosis_name, days_since=365))
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

        rows = payload["rows"]
        terms: set[str] = set()
        for row in rows:
            if isinstance(row, str):
                term = _extract_food_terms(row)
                if len(term.strip()) > 0:
                    terms.add(term.strip())
        return terms

    async def _query_candidates(self) -> list[_PackageCandidate]:
        """查询当前可售套餐全集。

        功能：
            裁剪版方案不再区分餐次，直接读取当前可售套餐全集作为排序候选，
            用更简单的在线链路换取更低的实现复杂度和更稳定的首版行为。
        """

        pool = await self._mysql_pools.get_ods_pool()
        sql = """
            SELECT
                p.package_code,
                p.package_name,
                p.package_type,
                p.applicable_people,
                p.core_target,
                p.nutrition_feature,
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
                    await cursor.execute(sql)
                    rows = await cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            raise SmartMealPackageRecommendServiceError("db_failed: 套餐候选查询失败") from exc

        candidate_map: dict[str, _PackageCandidate] = {}
        for row in rows:
            package_code = _normalize_text(row.get("package_code"))
            package_name = _normalize_text(row.get("package_name"))
            if not package_code or not package_name:
                continue

            candidate = candidate_map.get(package_code)
            if candidate is None:
                candidate = _PackageCandidate(
                    package_code=package_code,
                    package_name=package_name,
                    package_type=_normalize_text(row.get("package_type")) or "UNKNOWN",
                    applicable_people=_normalize_text(row.get("applicable_people")),
                    core_target=_normalize_text(row.get("core_target")),
                    nutrition_feature=_normalize_text(row.get("nutrition_feature")),
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

    def _apply_hard_filters(
        self,
        *,
        candidates: list[_PackageCandidate],
        intolerance_terms: set[str],
        abnormal_indicators: dict[str, list[str]],
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
        abnormal_indicators: dict[str, list[str]],
        diagnoses: list[_DiagnosisSignal],
        age: int | None,
        sex: str | None,
    ) -> list[dict[str, str | float]]:
        """计算候选套餐绝对评分。

        功能：
            评分阶段使用固定权重，确保上线初期具备可解释性与可回放性。
            当异常指标缺失时执行权重重分配，避免“空指标字段”把整体分数硬拉低。
        """

        abnormal_types = _normalize_abnormal_types(abnormal_indicators)
        has_abnormal = bool(abnormal_types)

        scored: list[dict[str, str | float]] = []
        for candidate in candidates:
            f_health = _keyword_overlap_score(health_tags, candidate.search_text)
            f_abnormal = self._score_abnormal_match(candidate=candidate, abnormal_types=abnormal_types)
            f_preference = _keyword_overlap_score(diet_preferences, candidate.search_text)
            f_diagnosis = self._score_diagnosis_match(candidate=candidate, diagnoses=diagnoses)

            if has_abnormal:
                base = (
                    0.26 * f_health
                    + 0.22 * f_abnormal
                    + 0.14 * f_preference
                    + 0.38 * f_diagnosis
                )
            else:
                base = (
                    0.38 * f_health
                    + 0.14 * f_preference
                    + 0.48 * f_diagnosis
                )

            # 裁剪版直接输出排序分，不再引入二次重排，确保线上结果更容易回放和解释。
            match_score = round(100 * _clip01(base), 2)
            scored.append(
                {
                    "package_code": candidate.package_code,
                    "package_name": candidate.package_name,
                    "match_score": match_score,
                    "reason": self._build_rule_reason(
                        candidate=candidate,
                        health_tags=health_tags,
                        diet_preferences=diet_preferences,
                        abnormal_types=abnormal_types,
                        diagnoses=diagnoses,
                    ),
                }
            )

        scored.sort(key=lambda item: (-float(item["match_score"]), str(item["package_code"])))
        return scored

    def _build_rule_reason(
        self,
        *,
        candidate: _PackageCandidate,
        health_tags: list[str],
        diet_preferences: list[str],
        abnormal_types: set[str],
        diagnoses: list[_DiagnosisSignal],
    ) -> str:
        """生成规则回退场景的可展示理由。

        功能：
            回退链路不能再次依赖 LLM，这里用规则命中项拼装一条简短可解释文案，
            保证前端无论走主排还是回退都能拿到统一字段。
        """

        reasons: list[str] = []
        package_text = candidate.search_text.lower()

        matched_health = [_normalize_text(tag) for tag in health_tags if _normalize_text(tag).lower() in package_text]
        if matched_health:
            reasons.append(f"命中健康标签：{'、'.join(matched_health[:2])}")

        matched_preferences = [
            _normalize_text(tag)
            for tag in diet_preferences
            if _normalize_text(tag).lower() in package_text
        ]
        if matched_preferences:
            reasons.append(f"贴合口味偏好：{'、'.join(matched_preferences[:2])}")

        if self._score_abnormal_match(candidate=candidate, abnormal_types=abnormal_types) > 0:
            reasons.append("营养特点与异常指标方向较匹配")

        if self._score_diagnosis_match(candidate=candidate, diagnoses=diagnoses) > 0:
            reasons.append("与医生诊断提示方向较一致")

        if candidate.core_target:
            reasons.append(f"核心目标：{candidate.core_target}")
        elif candidate.nutrition_feature:
            reasons.append(f"营养特点：{candidate.nutrition_feature}")

        if not reasons:
            return "基于现有规则排序，该套餐在当前可用候选中相对更匹配。"
        return "；".join(reasons[:2]) + "。"

    def _contains_intolerance(self, *, candidate: _PackageCandidate, intolerance_terms: set[str]) -> bool:
        """判断套餐是否命中不耐受项。"""
        if not candidate.dish_names:
            return False
        if not intolerance_terms:
            return False
        for ingredient in candidate.ingredient_names:
            normalized_ingredient = ingredient.lower()
            for term in intolerance_terms:
                normalized_term = term.lower()
                if normalized_term in normalized_ingredient or normalized_ingredient in normalized_term:
                    return True
        return False

    def _is_high_risk_blocked(self, *, candidate: _PackageCandidate, abnormal_indicators: dict[str, list[str]]) -> bool:
        """判断套餐是否命中高风险硬禁配。

        功能：
            V1 没有完整营养成分表，先采用“异常类别 + 套餐关键词”的保守规则，
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

    def _score_abnormal_match(self, *, candidate: _PackageCandidate, abnormal_types: set[str]) -> float:
        """计算异常指标匹配分。"""

        if not abnormal_types:
            return 0.0

        match_keywords = {
            "blood_glucose": ("控糖", "低糖", "粗粮"),
            "blood_lipid": ("轻脂", "低脂", "清淡"),
            "kidney_function": ("低钠", "清淡", "优蛋白"),
            "weight_condition": ("轻脂", "控卡", "高纤"),
        }
        matched = 0
        package_text = candidate.search_text.lower()
        for indicator_type in abnormal_types:
            keywords = match_keywords.get(indicator_type, ())
            if any(keyword in package_text for keyword in keywords):
                matched += 1
        return _clip01(matched / max(len(abnormal_types), 1))

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


def _parse_score(value: Any) -> float | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
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
    for token in ("过敏", "不吃", "忌口", "不能吃", "避免", "禁食", "特异性IgG抗体", "sIgE抗体", "升高"):
        normalized = normalized.replace(token, " ")
    normalized = re.sub(r"[（\(].+[）\)]", " ", normalized)
    new_text = re.split(r"[:：]", normalized)
    if len(new_text) >= 2:
        normalized = new_text[0].strip()
    return normalized


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

def _keyword_overlap_score(tokens: list[str], target_text: str) -> float:
    normalized_tokens = [_normalize_text(token).lower() for token in tokens if _normalize_text(token)]
    if not normalized_tokens:
        return 0.0
    target = target_text.lower()
    hit_count = sum(1 for token in normalized_tokens if token in target)
    return _clip01(hit_count / len(normalized_tokens))

def _normalize_abnormal_types(abnormal_indicators: dict[str, list[str]]) -> set[str]:
    """把异常指标字典归一成内部指标类型集合。

    功能：
        输入契约改为 `{异常类别: [异常描述...]}` 后，排序与重排逻辑仍依赖稳定的内部类型键。
        这里集中做一次映射，避免业务代码分散判断中英文、别名和噪声文本。
    """

    mapping = {
        "血糖异常": "blood_glucose",
        "血糖": "blood_glucose",
        "blood_glucose": "blood_glucose",
        "体重": "weight_condition",
        "体重异常": "weight_condition",
        "weight_condition": "weight_condition",
        "血脂异常": "blood_lipid",
        "血脂": "blood_lipid",
        "blood_lipid": "blood_lipid",
        "肾功": "kidney_function",
        "肾功能": "kidney_function",
        "kidney_function": "kidney_function",
    }
    normalized_types: set[str] = set()
    for category in abnormal_indicators:
        category_text = _normalize_text(category)
        if not category_text:
            continue
        normalized_type = mapping.get(category_text, mapping.get(category_text.lower(), ""))
        if normalized_type:
            normalized_types.add(normalized_type)
    return normalized_types


def _detect_high_risk_types(abnormal_indicators: dict[str, list[str]]) -> set[str]:
    """识别高风险指标类型。

    功能：
        新契约只传异常文本，不再包含结构化数值。V1 采用“异常类别命中即高风险保守过滤”策略：
        对血糖/血脂/肾功相关套餐先做硬禁配，优先保证医疗安全边界。
    """

    normalized_types = _normalize_abnormal_types(abnormal_indicators)
    high_risk_allow_list = {"blood_glucose", "blood_lipid", "kidney_function"}
    return {indicator_type for indicator_type in normalized_types if indicator_type in high_risk_allow_list}
