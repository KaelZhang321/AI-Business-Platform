"""健康四象限服务。

功能：
    基于 `study_id` 聚合体检源数据，按请求的 `quadrant_type` 选择计算分支生成四象限结果；
    同时支持“先读已确认持久化，未命中再实时计算”的查询策略。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Any

import aiomysql

from app.core.mysql import (
    build_business_mysql_conn_params,
    build_health_quadrant_dw_mysql_conn_params,
    build_health_quadrant_ods_mysql_conn_params,
)
from app.services.health_quadrant_repository import HealthQuadrantRepository
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

_DW_TABLE_SPLIT = "dwd_his_zt_physicalexam_conclusion_split"

_EXAM_BUCKETS = [
    ("exam_q1_basic_screening", "第一象限（基础筛查）"),
    ("exam_q2_imaging", "第二象限（影像评估）"),
    ("exam_q3_deep_screening", "第三象限（专项深度筛查）"),
    ("exam_q4_premium", "第四象限（丽滋特色项目）"),
]

_TREATMENT_BUCKETS = [
    ("treat_q1_red", "红色高风险区（救命：医疗级干预）"),
    ("treat_q2_orange", "橙色较高风险区（治病：专项健康管理）"),
    ("treat_q3_blue", "蓝色一般风险区（防病：生活方式医学）"),
    ("treat_q4_green", "绿色低风险区（抗衰：高端维养服务）"),
]

_IMAGING_KEYWORDS = ("影像", "CT", "MR", "MRI", "超声", "彩超", "X线", "DR", "PET")
_PREMIUM_KEYWORDS = ("全基因", "PET-MR", "PET/CT", "肿瘤早筛", "心脑血管高级评估")
_RED_RISK_KEYWORDS = ("肿瘤", "重度狭窄", "脑动脉硬化", "高血压危象", "心梗", "脑梗")
_ORANGE_RISK_KEYWORDS = ("睡眠障碍", "肥胖", "结节", "肝功能异常", "肾功能异常")
_BLUE_RISK_KEYWORDS = ("维生素D缺乏", "骨质疏松", "胰岛素抵抗", "免疫力降低", "荷尔蒙")
_DRAFT_TTL_HOURS = 24
_Q4_MASS_SPEC_KEYWORD = "质谱"


class HealthQuadrantServiceError(RuntimeError):
    """健康四象限服务异常。"""


class HealthQuadrantService:
    """健康四象限服务。

    功能：
        1. 读取持久化确认结果
        2. 未命中时聚合 ODS + DW 数据实时计算
        3. 把前端确认后的结果写回持久化表
    """

    def __init__(
        self,
        *,
        repository: HealthQuadrantRepository | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self._repository = repository or HealthQuadrantRepository()
        self._llm_service = llm_service or LLMService()

    async def query_quadrants(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_items: list[str],
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """查询四象限结果，优先命中持久化，再回退实时计算。

        功能：
            基于“同上下文签名复用结果”的原则，先读取 CONFIRMED/DRAFT 缓存，未命中再执行
            ODS + DW 聚合计算。该策略的目标是减少重复 LLM 调用和跨库查询成本。

        Args:
            study_id: 体检主单号，作为跨库聚合与持久化主维度。
            quadrant_type: 象限类型（`exam` 或 `treatment`），决定计算分支。
            single_exam_items: 前端补充的单项体检条目（可多条）。
            chief_complaint_items: 前端补充的主诉条目（可多条）。
            trace_id: 链路追踪 ID，缺失时自动生成。

        Returns:
            `{"quadrants":[...], "fromCache": bool}`，`fromCache=True` 表示命中持久化结果。

        Raises:
            HealthQuadrantServiceError: 当 `quadrant_type` 非法时抛出。

        Edge Cases:
            1. ODS/DW 任一侧短暂不可用时，允许部分源数据缺失并按可用数据继续计算。
            2. 仅当前端上下文和源系统版本信号（JLRQ/ZJRQ）同时一致时才命中旧结果。
        """

        # 1) 统一请求上下文：先做输入归一，避免“语义相同、字符串形态不同”导致签名分裂。
        normalized_trace_id = trace_id or uuid4().hex
        normalized_items = _normalize_single_exam_items(single_exam_items)
        normalized_complaints = _normalize_complaint_items(chief_complaint_items)
        logger.info(
            "health quadrant query start trace_id=%s study_id=%s quadrant_type=%s single_exam_count=%s complaint_count=%s",
            normalized_trace_id,
            study_id,
            quadrant_type,
            len(normalized_items),
            len(normalized_complaints),
        )

        # 2) 先取源系统版本信号（JLRQ/ZJRQ）：签名要感知源数据变更，不能仅看前端入参。
        source = await self._load_source_data(study_id=study_id)
        draft_not_older_than = datetime.now(timezone.utc) - timedelta(hours=_DRAFT_TTL_HOURS)

        # 3) 先读缓存：确认态优先，草稿态受 TTL 约束，避免误用过期草稿。
        cached, cached_status = await self._repository.get_preferred_payload(
            study_id=study_id,
            quadrant_type=quadrant_type,
            single_exam_items=normalized_items,
            chief_complaint_items=normalized_complaints,
            source_jlrq=source.get("sourceJlrq"),
            source_zjrq=source.get("sourceZjrq"),
            draft_not_older_than=draft_not_older_than,
            trace_id=normalized_trace_id,
        )
        if cached:
            logger.info(
                "health quadrant query cache hit trace_id=%s study_id=%s quadrant_type=%s status=%s",
                normalized_trace_id,
                study_id,
                quadrant_type,
                cached_status,
            )
            return {"quadrants": _normalize_quadrants_payload(cached), "fromCache": True}

        # 4) 缓存未命中时才进入实时计算分支，降低高并发下的跨库与 LLM 成本。
        if quadrant_type == "exam":
            quadrants = await self._build_exam_quadrants(
                source=source,
                single_exam_items=normalized_items,
                chief_complaint_items=normalized_complaints,
            )
        elif quadrant_type == "treatment":
            quadrants = self._build_treatment_quadrants(
                source=source,
                single_exam_items=normalized_items,
                chief_complaint_items=normalized_complaints,
            )
        else:
            raise HealthQuadrantServiceError("quadrant_type 仅支持 exam 或 treatment")

        logger.info(
            "health quadrant query computed trace_id=%s study_id=%s quadrant_type=%s",
            normalized_trace_id,
            study_id,
            quadrant_type,
        )

        # 5) 计算结果先落 DRAFT：重复请求可直接命中，等待前端确认后再提升为 CONFIRMED。
        await self._repository.upsert_draft_payload(
            study_id=study_id,
            quadrant_type=quadrant_type,
            single_exam_items=normalized_items,
            chief_complaint_items=normalized_complaints,
            source_jlrq=source.get("sourceJlrq"),
            source_zjrq=source.get("sourceZjrq"),
            payload={"quadrants": quadrants},
            trace_id=normalized_trace_id,
        )
        logger.info(
            "health quadrant draft persisted trace_id=%s study_id=%s quadrant_type=%s",
            normalized_trace_id,
            study_id,
            quadrant_type,
        )
        return {"quadrants": quadrants, "fromCache": False}

    async def confirm_quadrants(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_items: list[str],
        quadrants: list[dict[str, Any]],
        confirmed_by: str | None,
        trace_id: str | None = None,
    ) -> None:
        """确认并持久化四象限结果。

        功能：
            将前端确认后的四象限结果升级为 CONFIRMED，并以幂等方式写入持久化层，
            作为后续同上下文请求的权威返回结果。

        Args:
            study_id: 体检主单号。
            quadrant_type: 象限类型（`exam` 或 `treatment`）。
            single_exam_items: 单项体检条目列表（可多条）。
            chief_complaint_items: 主诉条目列表（可多条）。
            quadrants: 前端确认后的四象限结果。
            confirmed_by: 操作人（通常来自 `X-User-Id`）。
            trace_id: 链路追踪 ID，缺失时自动生成。

        Returns:
            无返回值；成功即表示已持久化。

        Edge Cases:
            即使前端传入与当前源系统版本不一致的数据，也会以当前 JLRQ/ZJRQ 参与签名，
            防止旧版本确认结果污染新版本上下文。
        """

        # 1) 入参归一化：确保确认链路与查询链路使用同一签名语义。
        normalized_trace_id = trace_id or uuid4().hex
        normalized_items = _normalize_single_exam_items(single_exam_items)
        normalized_complaints = _normalize_complaint_items(chief_complaint_items)

        # 2) 重新读取源系统版本时间：避免“先查后确认”的时间窗口内版本漂移。
        source = await self._load_source_data(study_id=study_id)
        payload = {"quadrants": _normalize_quadrants_payload({"quadrants": quadrants})}

        # 3) 使用 repository 的幂等写入策略，抵御并发确认与重试重放。
        await self._repository.upsert_confirmed_payload(
            study_id=study_id,
            quadrant_type=quadrant_type,
            single_exam_items=normalized_items,
            chief_complaint_items=normalized_complaints,
            source_jlrq=source.get("sourceJlrq"),
            source_zjrq=source.get("sourceZjrq"),
            payload=payload,
            confirmed_by=_normalize_text(confirmed_by),
            trace_id=normalized_trace_id,
        )
        logger.info(
            "health quadrant confirm persisted trace_id=%s study_id=%s quadrant_type=%s confirmed_by=%s",
            normalized_trace_id,
            study_id,
            quadrant_type,
            _normalize_text(confirmed_by),
        )

    async def close(self) -> None:
        """释放底层资源。"""

        await self._repository.close()

    async def _load_source_data(self, *, study_id: str) -> dict[str, Any]:
        """加载体检源数据。

        功能：
            上游两套库字段命名并不完全一致，这里采用“多候选列探测 + 降级 SQL”策略，
            降低字段变更对接口可用性的冲击。

        Args:
            study_id: 体检主单号。

        Returns:
            包含 `packageName/finalConclusion/splitRows/sourceJlrq/sourceZjrq` 的聚合字典。

        Edge Cases:
            1. ODS 或 DW 任一侧失败时返回部分数据，不让整个流程因单点抖动不可用。
            2. `sourceJlrq/sourceZjrq` 缺失时回退为 `None`，签名侧会稳定归一为空串。
        """

        # 1) 初始化为可降级默认值：确保任一数据源不可用时仍能返回结构化结果。
        package_name = ""
        final_conclusion = ""
        split_rows: list[dict[str, Any]] = []
        source_jlrq = None
        source_zjrq = None

        ods_pool: aiomysql.Pool | None = None
        dw_pool: aiomysql.Pool | None = None
        try:
            ods_pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=2,
                **build_health_quadrant_ods_mysql_conn_params(),
            )
            async with ods_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 业务背景：套餐名可能沉在 ods_tj_jcxx，终检意见通常在 ods_tj_jlb.JKYLBJ。
                    await cursor.execute(
                        """
SELECT
  jlb.JKYLBJ AS finalConclusion,
  xmzh.XMMC AS packageName,
  jlb.JLRQ AS sourceJlrq,
  jlb.ZJRQ AS sourceZjrq
FROM ods_tj_jlb jlb
JOIN ods_tj_jcxx jcxx ON jcxx.StudyID = jlb.StudyID
JOIN ods_tj_xmzh xmzh ON jcxx.ZHXMDM = xmzh.XMDM 
WHERE jlb.StudyID = %s
LIMIT 1
                        """,
                        (study_id,),
                    )
                    row = await cursor.fetchone()
                    if row:
                        # 2) ODS 作为版本信号源：JLRQ/ZJRQ 参与签名，驱动缓存有效性判断。
                        package_name = _normalize_text(row.get("packageName")) or ""
                        final_conclusion = _normalize_text(row.get("finalConclusion")) or ""
                        source_jlrq = row.get("sourceJlrq")
                        source_zjrq = row.get("sourceZjrq")
        except Exception as exc:
            # 3) ODS 异常不阻断主链路：保持可用性优先，后续由日志追踪修复。
            logger.warning("load ods source failed study_id=%s error=%s", study_id, exc)
            source_jlrq = None
            source_zjrq = None

        try:
            dw_pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=2,
                **build_health_quadrant_dw_mysql_conn_params(),
            )
            async with dw_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        f"""
SELECT
  category_name,
  one_item_name,
  two_item_name,
  abnormal_item
FROM {_DW_TABLE_SPLIT}
WHERE study_id = %s
                        """,
                        (study_id,),
                    )
                    split_rows = [dict(item) for item in await cursor.fetchall()]
        except Exception as exc:
            # 4) DW 异常同样降级：体检/治疗计算允许在“仅终检意见”条件下继续执行。
            logger.warning("load dw split failed study_id=%s error=%s", study_id, exc)
        finally:
            # 5) 无论成功失败都显式关闭连接池，避免压测/重试场景连接泄漏。
            if ods_pool is not None:
                ods_pool.close()
                await ods_pool.wait_closed()
            if dw_pool is not None:
                dw_pool.close()
                await dw_pool.wait_closed()

        return {
            "packageName": package_name,
            "finalConclusion": final_conclusion,
            "splitRows": split_rows,
            "sourceJlrq": source_jlrq,
            "sourceZjrq": source_zjrq,
        }

    async def _build_exam_quadrants(
        self,
        *,
        source: dict[str, Any],
        single_exam_items: list[dict[str, str]],
        chief_complaint_items: list[str],
    ) -> list[dict[str, Any]]:
        """构建体检四象限。

        功能：
            第一、二象限严格遵循你给的分流规则：非影像走 `one_item_name`，影像走 `two_item_name`；
            第三象限从 `JKYLBJ` 做抽取并映射标准项目名，再与第一、二象限去重；
            第四象限按主诉从业务库做 LIKE 召回，仅保留功能医学“质谱”类体检项目。

        Args:
            source: 聚合后的源数据，含 splitRows/finalConclusion 等。
            single_exam_items: 前端补充单项体检条目。
            chief_complaint_items: 前端补充主诉条目。

        Returns:
            体检四象限列表（固定 4 个象限）。

        Edge Cases:
            1. 当 splitRows 为空时，第三象限仍可基于终检意见与前端补充条目产出结果。
            2. 映射表未命中时保留原始抽取项，避免有效复查项被误丢弃。
        """

        buckets = _empty_buckets(_EXAM_BUCKETS)
        # 1) 基于分拆表先构建第一、二象限：这是“体检事实数据”最稳定的来源。
        for row in source.get("splitRows", []):
            one_item = _normalize_text(row.get("one_item_name"))
            two_item = _normalize_text(row.get("two_item_name"))
            abnormal_item = _normalize_text(row.get("abnormal_item"))
            category = _normalize_text(row.get("category"))

            # 1. 非影像异常归第一象限；影像异常归第二象限，符合“1+X”基础筛查语义。
            if one_item and not _looks_like_imaging(one_item, category):
                buckets[0]["abnormalIndicators"].append(one_item if not abnormal_item else f"{one_item}：{abnormal_item}")
            if two_item or (one_item and _looks_like_imaging(one_item, category)):
                imaging_name = two_item or one_item or ""
                buckets[1]["abnormalIndicators"].append(
                    imaging_name if not abnormal_item else f"{imaging_name}：{abnormal_item}"
                )

        # 2) 先建立 Q1/Q2 去重基线：后续 Q3/Q4 只补“新增价值项”，避免重复展示。
        existing_exam_keys = _build_exam_dedup_keys(
            buckets[0]["abnormalIndicators"] + buckets[1]["abnormalIndicators"]
        )

        # 3) 第三象限：终检意见抽取 -> 标准化映射 -> 与 Q1/Q2 去重。
        final_conclusion = _normalize_text(source.get("finalConclusion")) or ""
        extracted_items = await self._extract_deep_screening_items(final_conclusion=final_conclusion)
        mapped_items = await self._map_doctor_conclusion_items_to_standard(items=extracted_items)

        # 保留既有单项补充入口：前端人工补充条目属于业务确认输入，应并入第三象限。
        single_items = [item["itemText"] for item in single_exam_items if item.get("itemText")]
        q3_candidates = mapped_items + single_items
        q3_items = _deduplicate_exam_items_by_keys(q3_candidates, existing_exam_keys)
        if q3_items:
            buckets[2]["abnormalIndicators"].extend(q3_items)
            existing_exam_keys.update(_build_exam_dedup_keys(q3_items))

        # 4) 第四象限：基于主诉做 pathway LIKE 召回，再过滤为功能医学“质谱”检测项目。
        q4_candidates = await self._query_q4_mass_spec_projects(chief_complaint_items=chief_complaint_items)
        q4_items = _deduplicate_exam_items_by_keys(q4_candidates, existing_exam_keys)
        if q4_items:
            buckets[3]["abnormalIndicators"].extend(q4_items)
            existing_exam_keys.update(_build_exam_dedup_keys(q4_items))

        # 5) 统一补齐推荐方案与去重，保证确认页字段完整且可直接渲染。
        _finalize_exam_recommendations(buckets)
        return buckets

    def _build_treatment_quadrants(
        self,
        *,
        source: dict[str, Any],
        single_exam_items: list[dict[str, str]],
        chief_complaint_items: list[str],
    ) -> list[dict[str, Any]]:
        """构建治疗四象限。

        功能：
            按“红橙蓝绿”风险优先级对异常项进行分桶，把多源文本条目转成可执行的干预层级。

        Args:
            source: 聚合后的源数据。
            single_exam_items: 前端补充单项体检条目。
            chief_complaint_items: 前端补充主诉条目。

        Returns:
            治疗四象限列表（固定 4 个象限）。

        Edge Cases:
            未命中任何风险关键词的条目会进入绿色维养区，避免结果丢项。
        """

        buckets = _empty_buckets(_TREATMENT_BUCKETS)
        all_candidates: list[str] = []
        # 1) 先汇总所有候选条目：统一分层前必须先做数据面归集，避免漏判。
        for row in source.get("splitRows", []):
            for key in ("abnormal_item", "one_item_name", "two_item_name"):
                value = _normalize_text(row.get(key))
                if value:
                    all_candidates.append(value)
        for item in single_exam_items:
            if item.get("itemText"):
                all_candidates.append(item["itemText"])
        final_conclusion = _normalize_text(source.get("finalConclusion"))
        if final_conclusion:
            all_candidates.append(final_conclusion)
        all_candidates.extend(chief_complaint_items)

        # 2) 风险分层采用“高风险优先短路”策略，避免同条目被低优先级规则重复归档。
        for text in all_candidates:
            if any(keyword in text for keyword in _RED_RISK_KEYWORDS):
                buckets[0]["abnormalIndicators"].append(text)
                continue
            if any(keyword in text for keyword in _ORANGE_RISK_KEYWORDS):
                buckets[1]["abnormalIndicators"].append(text)
                continue
            if any(keyword in text for keyword in _BLUE_RISK_KEYWORDS):
                buckets[2]["abnormalIndicators"].append(text)
                continue
            buckets[3]["abnormalIndicators"].append(text)

        # 3) 最终统一补推荐策略与去重，保证前端确认动作有完整操作依据。
        _finalize_treatment_recommendations(buckets)
        return buckets

    async def _extract_deep_screening_items(self, *, final_conclusion: str) -> list[str]:
        """从终检意见抽取专项筛查项目。

        功能：
            终检意见通常是自然语言段落，规则很难覆盖。这里用轻量提示词做 JSON 提取，
            若 LLM 异常则降级为关键词切分，保证链路可用。

        Args:
            final_conclusion: 终检意见原文（JKYLBJ）。

        Returns:
            提取出的“进一步检查/复查/筛查”项目列表。

        Edge Cases:
            LLM 超时、输出非 JSON、或返回空结果时，会自动回退到规则切分兜底策略。
        """

        if not final_conclusion:
            return []
        prompt = (
            "你是体检终检意见抽取器。请从文本中提取“建议进一步检查/复查/筛查”的项目，"
            "仅返回 JSON：{\"items\":[\"...\"]}。\n"
            f"文本：{final_conclusion}"
        )
        try:
            # 1) 优先走 LLM 结构化提取：在长文本场景下比纯关键词更稳健。
            raw = await self._llm_service.chat(
                [
                    {"role": "system", "content": "你只输出合法JSON，不要解释。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout_seconds=8.0,
            )
            parsed = json_loads_safe(raw)
            items = parsed.get("items") if isinstance(parsed, dict) else []
            if isinstance(items, list):
                return [item.strip() for item in items if isinstance(item, str) and item.strip()]
        except Exception as exc:
            # 2) LLM 异常不外抛：提取失败不能阻塞整个四象限主链路。
            logger.warning("extract deep screening by llm failed error=%s", exc)

        # 降级策略：按常见标点切分，抽取包含“复查/进一步/筛查”的短语，避免空结果。
        fallback_tokens = (
            final_conclusion.replace("。", "；")
            .replace("，", "；")
            .replace(",", "；")
            .split("；")
        )
        result = []
        for token in fallback_tokens:
            text = token.strip()
            if not text:
                continue
            if "复查" in text or "进一步" in text or "筛查" in text:
                result.append(text)
        return result

    async def _map_doctor_conclusion_items_to_standard(self, *, items: list[str]) -> list[str]:
        """将终检意见抽取项映射到标准体检项目名。

        功能：
            基于 `lz_doctor_conclusion_exam_mapping` 做标准化映射，让第三象限输出可与一二象限
            做“同口径项目名”去重。映射未命中时保留原文，保证临床建议不丢失。

        Args:
            items: 从终检意见提取出的复查项目列表。

        Returns:
            标准化后的项目列表；未命中项返回原始文本。

        Edge Cases:
            1. 映射库不可用时返回原始列表，保持主流程可用。
            2. 同名项目可能存在多条映射，仅取第一条有效映射，避免结果抖动。
        """

        normalized_items = [text for text in (_normalize_text(item) for item in items) if text]
        if not normalized_items:
            return []

        conn_params = build_business_mysql_conn_params()
        pool: aiomysql.Pool | None = None
        mapped_lookup: dict[str, str] = {}
        try:
            pool = await aiomysql.create_pool(minsize=1, maxsize=2, **conn_params)
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 使用 IN 批量查询，避免逐条 round trip 放大数据库压力。
                    placeholders = ",".join(["%s"] * len(normalized_items))
                    await cursor.execute(
                        f"""
SELECT raw_exam_name, mapped_exam_name
FROM lz_doctor_conclusion_exam_mapping
WHERE is_active = 1
  AND raw_exam_name IN ({placeholders})
ORDER BY id ASC
                        """,
                        tuple(normalized_items),
                    )
                    rows = await cursor.fetchall()
                    for row in rows:
                        raw_name = _normalize_text(row.get("raw_exam_name"))
                        mapped_name = _normalize_text(row.get("mapped_exam_name"))
                        if not raw_name or not mapped_name:
                            continue
                        mapped_lookup.setdefault(raw_name, mapped_name)
        except Exception as exc:
            logger.warning("map doctor conclusion items failed count=%s error=%s", len(normalized_items), exc)
            return normalized_items
        finally:
            if pool is not None:
                pool.close()
                await pool.wait_closed()

        return [mapped_lookup.get(item, item) for item in normalized_items]

    async def _query_q4_mass_spec_projects(self, *, chief_complaint_items: list[str]) -> list[str]:
        """按主诉模糊匹配 pathway，召回第四象限候选项目。

        功能：
            第四象限采用“主诉 -> pathway trigger_name LIKE -> 检测节点联查”策略，仅保留功能医学
            质谱类体检项目，满足“本期只召回质谱项目”的范围约束。

        Args:
            chief_complaint_items: 主诉文本列表（可多条）。

        Returns:
            第四象限候选项目列表（未做跨象限去重）。

        Edge Cases:
            1. 主诉为空时直接返回空列表，不触发数据库查询。
            2. 数据库异常时返回空列表，避免第四象限失败拖垮整体响应。
        """

        normalized_complaints = [text for text in (_normalize_text(item) for item in chief_complaint_items) if text]
        if not normalized_complaints:
            return []

        conn_params = build_business_mysql_conn_params()
        pool: aiomysql.Pool | None = None
        try:
            pool = await aiomysql.create_pool(minsize=1, maxsize=2, **conn_params)
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 每条主诉都能触发召回，符合已确认的“任一主诉命中即召回”策略。
                    like_clauses = " OR ".join(["p.trigger_name LIKE %s"] * len(normalized_complaints))
                    params: list[str] = [f"%{item}%" for item in normalized_complaints]
                    params.insert(0, f"%{_Q4_MASS_SPEC_KEYWORD}%")
                    await cursor.execute(
                        f"""
SELECT DISTINCT n.exam_name
FROM lz_clinical_pathway p
JOIN lz_physicalexam_node n ON n.pathway_id = p.pathway_id
WHERE n.exam_type = 'FUNCTIONAL'
  AND n.exam_name LIKE %s
  AND ({like_clauses})
ORDER BY n.exam_name ASC
                        """,
                        tuple(params),
                    )
                    rows = await cursor.fetchall()
                    return [_normalize_text(row.get("exam_name")) for row in rows if _normalize_text(row.get("exam_name"))]
        except Exception as exc:
            logger.warning(
                "query q4 mass spec projects failed complaints=%s error=%s",
                normalized_complaints,
                exc,
            )
            return []
        finally:
            if pool is not None:
                pool.close()
                await pool.wait_closed()


def _normalize_single_exam_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """规范化单项体检列表。

    功能：
        前端可能提交空对象、重复条目或不同字段大小写。这里统一折叠成标准形状，
        避免进入持久化维度后出现“语义相同但命中失败”。
    """

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in items:
        item_id = _normalize_text(raw.get("itemId") if isinstance(raw, dict) else None) or ""
        item_text = _normalize_text(raw.get("itemText") if isinstance(raw, dict) else None) or ""
        if not item_id and not item_text:
            continue
        key = (item_id, item_text)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"itemId": item_id, "itemText": item_text})
    normalized.sort(key=lambda x: (x["itemId"], x["itemText"]))
    return normalized


def _normalize_complaint_items(items: list[str]) -> list[str]:
    """规范化主诉列表。"""

    normalized = []
    for item in items:
        text = _normalize_text(item)
        if text:
            normalized.append(text)
    return sorted(set(normalized))


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_exam_name_for_key(raw: str) -> str:
    """生成体检项目去重键。"""

    base = _normalize_text(raw) or ""
    # Q1/Q2 可能带“项目：异常描述”拼接，去重要回到“项目名”本体。
    if "：" in base:
        base = base.split("：", 1)[0].strip()
    return base


def _build_exam_dedup_keys(items: list[str]) -> set[str]:
    """从项目列表构建去重键集合。"""

    keys = set()
    for item in items:
        key = _normalize_exam_name_for_key(item)
        if key:
            keys.add(key)
    return keys


def _deduplicate_exam_items_by_keys(candidates: list[str], existing_keys: set[str]) -> list[str]:
    """按“标准化项目名”去重并过滤已存在项。"""

    result: list[str] = []
    local_seen: set[str] = set()
    for item in candidates:
        text = _normalize_text(item)
        if not text:
            continue
        key = _normalize_exam_name_for_key(text)
        if not key or key in existing_keys or key in local_seen:
            continue
        local_seen.add(key)
        result.append(text)
    return result


def _empty_buckets(defs: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "code": code,
            "name": name,
            "abnormalIndicators": [],
            "recommendationPlans": [],
        }
        for code, name in defs
    ]


def _looks_like_imaging(item_name: str, category: str | None) -> bool:
    base = item_name.upper()
    if any(keyword in base for keyword in _IMAGING_KEYWORDS):
        return True
    if category and any(keyword in category.upper() for keyword in _IMAGING_KEYWORDS):
        return True
    return False


def _finalize_exam_recommendations(buckets: list[dict[str, Any]]) -> None:
    # 规则解释：每个象限必须同时给“异常指标 + 推荐方案”，保证前端确认页数据完整。
    buckets[0]["recommendationPlans"] = ["基础异常复查包", "血液与代谢专项复检"]
    buckets[1]["recommendationPlans"] = ["影像专科复核", "必要时安排增强影像检查"]
    buckets[2]["recommendationPlans"] = ["终检意见专项深筛包", "医生会诊后追加个性化检查"]
    buckets[3]["recommendationPlans"] = ["全基因检测", "PET-MR 高端筛查评估"]
    for bucket in buckets:
        bucket["abnormalIndicators"] = _deduplicate_text_list(bucket["abnormalIndicators"])


def _finalize_treatment_recommendations(buckets: list[dict[str, Any]]) -> None:
    buckets[0]["recommendationPlans"] = ["高风险绿色通道", "专家门诊优先+每日指标跟踪"]
    buckets[1]["recommendationPlans"] = ["专项健康管理方案", "周度跟进+月度复盘"]
    buckets[2]["recommendationPlans"] = ["生活方式干预", "季度复查+营养补充"]
    buckets[3]["recommendationPlans"] = ["年度维养计划", "抗衰与健康促进管理"]
    for bucket in buckets:
        bucket["abnormalIndicators"] = _deduplicate_text_list(bucket["abnormalIndicators"])


def _deduplicate_text_list(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = _normalize_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_quadrants_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """把任意来源 payload 收敛为标准四象限结构。"""

    raw = payload.get("quadrants")
    if not isinstance(raw, list):
        return []

    normalized = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                # 兼容新旧字段：新契约使用 q_code/q_name，旧缓存可能仍是 code/name。
                "code": str(item.get("q_code") or item.get("code") or ""),
                "name": str(item.get("q_name") or item.get("name") or ""),
                "abnormalIndicators": _deduplicate_text_list(list(item.get("abnormalIndicators") or [])),
                "recommendationPlans": _deduplicate_text_list(list(item.get("recommendationPlans") or [])),
            }
        )
    return normalized


def json_loads_safe(raw: str) -> dict[str, Any] | list[Any] | None:
    """安全解析 JSON 字符串。"""

    try:
        return json.loads(raw)
    except Exception:
        return None
