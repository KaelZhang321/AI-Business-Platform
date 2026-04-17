"""健康四象限服务。

功能：
    基于 `study_id` 聚合体检源数据，按请求的 `quadrant_type` 选择计算分支生成四象限结果；
    同时支持“先读已确认持久化，未命中再实时计算”的查询策略。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import aiomysql
import httpx

from app.core.config import settings
from app.services.health_quadrant_llm_service import HealthQuadrantLLMService
from app.services.health_quadrant_mysql_pools import HealthQuadrantMySQLPools
from app.services.health_quadrant_repository import HealthQuadrantRepository
from app.services.health_quadrant_treatment_repository import (
    HealthQuadrantTreatmentRepository,
    HealthQuadrantTreatmentRepositoryError,
)

logger = logging.getLogger(__name__)

_EXAM_BUCKETS = [
    ("exam_q1", "第一象限（基础筛查）"),
    ("exam_q2", "第二象限（影像评估）"),
    ("exam_q3", "第三象限（专项深度筛查）"),
    ("exam_q4", "第四象限（丽滋特色项目）"),
]

_TREATMENT_BUCKETS = [
    ("treat_q1", "红色高风险区（救命：医疗级干预）"),
    ("treat_q2", "橙色较高风险区（治病：专项健康管理）"),
    ("treat_q3", "蓝色一般风险区（防病：生活方式医学）"),
    ("treat_q4", "绿色低风险区（抗衰：高端维养服务）"),
]

_IMAGING_KEYWORDS = ("影像", "CT", "MR", "MRI", "超声", "彩超", "X线", "DR", "PET")
_PREMIUM_KEYWORDS = ("全基因", "PET-MR", "PET/CT", "肿瘤早筛", "心脑血管高级评估")
_DRAFT_TTL_HOURS = 24
_Q4_MASS_SPEC_KEYWORD = "质谱"
_TREATMENT_QUADRANT_PRIORITY = {
    "RED": 0,
    "ORANGE": 1,
    "BLUE": 2,
    "GREEN": 3,
}
_TREATMENT_QUADRANT_TO_INDEX = {
    "RED": 0,
    "ORANGE": 1,
    "BLUE": 2,
    "GREEN": 3,
}
_TREATMENT_SYSTEM_ENUM = {
    "消化系统",
    "心脑血管",
    "神经系统",
    "内分泌系统",
    "免疫系统",
    "骨骼运动",
    "呼吸系统",
    "泌尿系统",
    "生殖系统",
}
_TREATMENT_EMPTY_MESSAGE = "无安全可推荐项目"


@dataclass(frozen=True)
class _TreatmentTriageItem:
    """治疗分诊阶段的标准化条目。"""

    item_name: str
    value_or_desc: str
    quadrant: str
    belong_system: str
    reason: str

    @property
    def dedupe_key(self) -> str:
        """用于同指标冲突裁决的稳定键。"""
        if self.value_or_desc.startswith(self.item_name):
            return self.value_or_desc
        return f"{self.item_name} + {self.value_or_desc}"


@dataclass(frozen=True)
class _TreatmentCandidateProject:
    """治疗知识库召回后的候选项目。"""

    candidate_id: str
    project_name: str
    package_version: str
    quadrant: str
    belong_system: str
    trigger_item: str
    trigger_value_or_desc: str
    priority_level: int
    sort_order: int
    match_source: str
    contraindications: str


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
        llm_service: HealthQuadrantLLMService | None = None,
        mysql_pools: HealthQuadrantMySQLPools | None = None,
        treatment_repository: HealthQuadrantTreatmentRepository | None = None,
    ) -> None:
        self._repository = repository or HealthQuadrantRepository()
        # 健康四象限的终检意见抽取需要稳定结构化输出，默认优先走 Ark（ARK_DEFAULT_MODEL）。
        self._llm_service = llm_service or HealthQuadrantLLMService()
        self._mysql_pools = mysql_pools or HealthQuadrantMySQLPools(minsize=1, maxsize=3)
        self._treatment_repository = treatment_repository or HealthQuadrantTreatmentRepository(
            mysql_pools=self._mysql_pools
        )
        self._dw_http_client: httpx.AsyncClient | None = None

    def _get_dw_http_client(self) -> httpx.AsyncClient:
        """懒加载 DW 路由 HTTP 客户端。

        功能：
            DW 数据源已经改为通过业务接口获取，连接复用能显著降低高并发下的 TLS/Socket 建连开销。
            这里集中管理 AsyncClient，避免在 `_load_source_data` 中每次请求都新建客户端。
        """

        if self._dw_http_client is None:
            self._dw_http_client = httpx.AsyncClient(timeout=10.0)
        return self._dw_http_client

    async def warmup(self) -> None:
        """预热服务依赖资源。

        功能：
            在启动期预建多数据源连接池，减少首个业务请求触发建池带来的冷启动时延。
            该能力是性能优化，不改变业务语义。
        """

        await self._mysql_pools.warmup()

    async def query_quadrants(
        self,
        *,
        sex: str,
        age: int | None,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_text: str | None = None,
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
                每条支持 `itemId/itemText/abnormalIndicator`。
            chief_complaint_text: 前端补充的主诉文本（可为空）。
            trace_id: 链路追踪 ID，缺失时自动生成。

        Returns:
            `{"quadrants":[...], "fromCache": bool}`，`fromCache=True` 表示命中持久化结果。

        Raises:
            HealthQuadrantServiceError: 当 `quadrant_type` 非法时抛出。

        Edge Cases:
            1. ODS/DW 任一侧短暂不可用时，允许部分源数据缺失并按可用数据继续计算。
            2. 仅当前端上下文和源系统版本信号（JLRQ/ZJRQ）同时一致时才命中旧结果。
        """
        total_started_at = time.perf_counter()

        # 1) 统一请求上下文：先做输入归一，避免“语义相同、字符串形态不同”导致签名分裂。
        normalize_started_at = time.perf_counter()
        normalized_trace_id = trace_id or uuid4().hex
        normalized_items = _normalize_single_exam_items(single_exam_items)
        normalized_complaint_text = _normalize_text(chief_complaint_text)
        logger.info(
            "health quadrant stage duration stage=service.query.normalize duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
            int((time.perf_counter() - normalize_started_at) * 1000),
            normalized_trace_id,
            study_id,
            quadrant_type,
        )
        try:
            # 2) 先取源系统版本信号（JLRQ/ZJRQ）：签名要感知源数据变更，不能仅看前端入参。
            source_started_at = time.perf_counter()
            source = await self._load_source_data(study_id=study_id, trace_id=normalized_trace_id)
            logger.info(
                "health quadrant stage duration stage=service.query.load_source duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
                int((time.perf_counter() - source_started_at) * 1000),
                normalized_trace_id,
                study_id,
                quadrant_type,
            )
            draft_not_older_than = datetime.now() - timedelta(hours=_DRAFT_TTL_HOURS)

            # 3) 先读缓存：确认态优先，草稿态受 TTL 约束，避免误用过期草稿。
            cache_lookup_started_at = time.perf_counter()
            cached, cached_status = await self._repository.get_preferred_payload(
                study_id=study_id,
                quadrant_type=quadrant_type,
                single_exam_items=normalized_items,
                chief_complaint_text=normalized_complaint_text,
                source_jlrq=source.get("sourceJlrq"),
                source_zjrq=source.get("sourceZjrq"),
                draft_not_older_than=draft_not_older_than,
                trace_id=normalized_trace_id,
            )
            logger.info(
                "health quadrant stage duration stage=service.query.cache_lookup duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s cache_hit=%s cache_status=%s",
                int((time.perf_counter() - cache_lookup_started_at) * 1000),
                normalized_trace_id,
                study_id,
                quadrant_type,
                bool(cached),
                cached_status,
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
            compute_started_at = time.perf_counter()
            if quadrant_type == "exam":
                quadrants = await self._build_exam_quadrants(
                    source=source,
                    sex=sex,
                    age=age,
                    single_exam_items=normalized_items,
                    chief_complaint_text=normalized_complaint_text,
                    study_id=study_id,
                    trace_id=normalized_trace_id
                )
            elif quadrant_type == "treatment":
                quadrants = await self._build_treatment_quadrants(
                    source=source,
                    sex=sex,
                    age=age,
                    single_exam_items=normalized_items,
                    chief_complaint_text=normalized_complaint_text,
                    study_id=study_id,
                    trace_id=normalized_trace_id,
                )
            else:
                raise HealthQuadrantServiceError("quadrant_type 仅支持 exam 或 treatment")
            logger.info(
                "health quadrant stage duration stage=service.query.compute duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
                int((time.perf_counter() - compute_started_at) * 1000),
                normalized_trace_id,
                study_id,
                quadrant_type,
            )

            logger.info(
                "health quadrant query computed trace_id=%s study_id=%s quadrant_type=%s",
                normalized_trace_id,
                study_id,
                quadrant_type,
            )

            # 5) 计算结果先落 DRAFT：重复请求可直接命中，等待前端确认后再提升为 CONFIRMED。
            draft_persist_started_at = time.perf_counter()
            await self._repository.upsert_draft_payload(
                study_id=study_id,
                quadrant_type=quadrant_type,
                single_exam_items=normalized_items,
                chief_complaint_text=normalized_complaint_text,
                source_jlrq=source.get("sourceJlrq"),
                source_zjrq=source.get("sourceZjrq"),
                payload={"quadrants": quadrants},
                trace_id=normalized_trace_id,
            )
            logger.info(
                "health quadrant stage duration stage=service.query.persist_draft duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
                int((time.perf_counter() - draft_persist_started_at) * 1000),
                normalized_trace_id,
                study_id,
                quadrant_type,
            )
            logger.info(
                "health quadrant draft persisted trace_id=%s study_id=%s quadrant_type=%s",
                normalized_trace_id,
                study_id,
                quadrant_type,
            )
            return {"quadrants": quadrants, "fromCache": False}
        finally:
            logger.info(
                "health quadrant stage duration stage=service.query.total duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
                int((time.perf_counter() - total_started_at) * 1000),
                normalized_trace_id,
                study_id,
                quadrant_type,
            )

    async def confirm_quadrants(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_text: str | None,
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
                每条支持 `itemId/itemText/abnormalIndicator`。
            chief_complaint_text: 主诉条目。
            quadrants: 前端确认后的四象限结果。
            confirmed_by: 操作人（通常来自 `X-User-Id`）。
            trace_id: 链路追踪 ID，缺失时自动生成。

        Returns:
            无返回值；成功即表示已持久化。

        Edge Cases:
            即使前端传入与当前源系统版本不一致的数据，也会以当前 JLRQ/ZJRQ 参与签名，
            防止旧版本确认结果污染新版本上下文。
        """
        total_started_at = time.perf_counter()

        # 1) 入参归一化：确保确认链路与查询链路使用同一签名语义。
        normalize_started_at = time.perf_counter()
        normalized_trace_id = trace_id or uuid4().hex
        normalized_items = _normalize_single_exam_items(single_exam_items)
        normalized_complaint_text = _normalize_text(chief_complaint_text)
        logger.info(
            "health quadrant stage duration stage=service.confirm.normalize duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
            int((time.perf_counter() - normalize_started_at) * 1000),
            normalized_trace_id,
            study_id,
            quadrant_type,
        )

        try:
            # 2) 重新读取源系统版本时间：避免“先查后确认”的时间窗口内版本漂移。
            source_started_at = time.perf_counter()
            source = await self._load_source_data(study_id=study_id, trace_id=normalized_trace_id)
            logger.info(
                "health quadrant stage duration stage=service.confirm.load_source duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
                int((time.perf_counter() - source_started_at) * 1000),
                normalized_trace_id,
                study_id,
                quadrant_type,
            )
            payload = {"quadrants": _normalize_quadrants_payload({"quadrants": quadrants})}

            # 3) 使用 repository 的幂等写入策略，抵御并发确认与重试重放。
            persist_started_at = time.perf_counter()
            await self._repository.upsert_confirmed_payload(
                study_id=study_id,
                quadrant_type=quadrant_type,
                single_exam_items=normalized_items,
                chief_complaint_text=normalized_complaint_text,
                source_jlrq=source.get("sourceJlrq"),
                source_zjrq=source.get("sourceZjrq"),
                payload=payload,
                confirmed_by=_normalize_text(confirmed_by),
                trace_id=normalized_trace_id,
            )
            logger.info(
                "health quadrant stage duration stage=service.confirm.persist_confirmed duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
                int((time.perf_counter() - persist_started_at) * 1000),
                normalized_trace_id,
                study_id,
                quadrant_type,
            )
            logger.info(
                "health quadrant confirm persisted trace_id=%s study_id=%s quadrant_type=%s confirmed_by=%s",
                normalized_trace_id,
                study_id,
                quadrant_type,
                _normalize_text(confirmed_by),
            )
        finally:
            logger.info(
                "health quadrant stage duration stage=service.confirm.total duration_ms=%s trace_id=%s study_id=%s quadrant_type=%s",
                int((time.perf_counter() - total_started_at) * 1000),
                normalized_trace_id,
                study_id,
                quadrant_type,
            )

    async def close(self) -> None:
        """释放底层资源。

        功能：
            在应用 shutdown 阶段统一释放 repository 与多数据源连接池，
            避免实例重启后残留无主连接。
        """

        await self._repository.close()
        await self._treatment_repository.close()
        await self._mysql_pools.close()
        if self._dw_http_client is not None:
            await self._dw_http_client.aclose()
            self._dw_http_client = None

    async def _load_source_data(self, *, study_id: str, trace_id: str | None = None) -> dict[str, Any]:
        """加载体检源数据。

        功能：
            ODS 主数据继续走 MySQL 直连；DW 异常拆分数据改为经业务路由获取，
            通过接口契约屏蔽底层表结构变更，降低网关对 DW 物理表的耦合。

        Args:
            study_id: 体检主单号。

        Returns:
            包含 `packageName/finalConclusion/splitRows/sourceJlrq/sourceZjrq` 的聚合字典。

        Edge Cases:
            1. ODS 或 DW 任一侧失败时返回部分数据，不让整个流程因单点抖动不可用。
            2. `sourceJlrq/sourceZjrq` 缺失时回退为 `None`，签名侧会稳定归一为空串。
        """
        total_started_at = time.perf_counter()
        normalized_trace_id = trace_id or "-"

        # 1) 初始化为可降级默认值：确保任一数据源不可用时仍能返回结构化结果。
        package_name = ""
        final_conclusion = ""
        split_rows: list[dict[str, Any]] = []
        source_jlrq = None
        source_zjrq = None
        jcjg = ""

        ods_started_at = time.perf_counter()
        ods_status = "success"
        try:
            ods_pool = await self._mysql_pools.get_ods_pool()
            async with ods_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 业务背景：套餐名可能沉在 ods_tj_jcxx，终检意见通常在 ods_tj_jlb.JKYLBJ。
                    await cursor.execute(
                        """
                        SELECT
                          jlb.JKYLBJ AS finalConclusion,
                          jlb.JCJG AS jcjg,
                          xmzh.XMMC AS packageName,
                          jlb.JLRQ AS sourceJlrq,
                          jlb.ZJRQ AS sourceZjrq
                        FROM ods_tj_jlb jlb
                        JOIN ods_tj_jcxx jcxx ON jcxx.ID = jlb.StudyID
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
                        jcjg = _normalize_text(row.get("jcjg")) or ""
                        source_jlrq = row.get("sourceJlrq")
                        source_zjrq = row.get("sourceZjrq")
        except Exception as exc:
            # 3) ODS 异常不阻断主链路：保持可用性优先，后续由日志追踪修复。
            ods_status = "failed"
            logger.warning("load ods source failed study_id=%s error=%s", study_id, exc)
            source_jlrq = None
            source_zjrq = None
        finally:
            logger.info(
                "health quadrant stage duration stage=service.source.ods_query duration_ms=%s trace_id=%s study_id=%s status=%s",
                int((time.perf_counter() - ods_started_at) * 1000),
                normalized_trace_id,
                study_id,
                ods_status,
            )

        dw_started_at = time.perf_counter()
        dw_status = "success"
        dw_url = ""
        try:
            # 4) 通过 DW 路由接口取异常拆分数据，避免网关继续直连 DW 物理表。
            client = self._get_dw_http_client()
            dw_base_url = settings.dw_route_url.rstrip("/")
            dw_url = f"{dw_base_url}/physicalexam-conclusion-split/{study_id}"
            response = await client.get(dw_url)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict):
                data = payload.get("rows")
                rows = data if isinstance(data, list) else []
            else:
                rows = []
            split_rows = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                # 业务规则：仅保留 delete_flag=0 的有效记录，并规范化字段名。
                delete_flag = row.get("delete_flag")
                if str(delete_flag) != "0":
                    continue
                split_rows.append(
                    {
                        "category_name": _normalize_text(row.get("category_name")) or "",
                        "one_item_name": _normalize_text(row.get("one_item_name")) or "",
                        "two_item_name": _normalize_text(row.get("two_item_name")) or "",
                        "abnormal_item": _normalize_text(row.get("abnormal_item")) or "",
                    }
                )
        except Exception as exc:
            # 5) DW 路由异常同样降级：体检/治疗计算允许在“仅终检意见”条件下继续执行。
            dw_status = "failed"
            status_code = None
            body_snippet = ""
            if isinstance(exc, httpx.HTTPStatusError):
                status_code = exc.response.status_code
                body_snippet = (exc.response.text or "")[:300]
            logger.warning(
                "load dw split failed trace_id=%s study_id=%s url=%s status_code=%s error_type=%s error=%r body_snippet=%s",
                normalized_trace_id,
                study_id,
                dw_url,
                status_code,
                type(exc).__name__,
                exc,
                body_snippet,
            )
        finally:
            logger.info(
                "health quadrant stage duration stage=service.source.dw_query duration_ms=%s trace_id=%s study_id=%s status=%s",
                int((time.perf_counter() - dw_started_at) * 1000),
                normalized_trace_id,
                study_id,
                dw_status,
            )

        logger.info(
            "health quadrant stage duration stage=service.source.total duration_ms=%s trace_id=%s study_id=%s",
            int((time.perf_counter() - total_started_at) * 1000),
            normalized_trace_id,
            study_id,
        )

        return {
            "packageName": package_name,
            "finalConclusion": final_conclusion,
            'jcjg': jcjg,
            "splitRows": split_rows,
            "sourceJlrq": source_jlrq,
            "sourceZjrq": source_zjrq,
        }

    async def _build_exam_quadrants(
        self,
        *,
        sex: str,
        age: int | None,
        source: dict[str, Any],
        single_exam_items: list[dict[str, str]],
        chief_complaint_text: str | None,
        study_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """构建体检四象限。

        功能：
            第一、二象限严格遵循你给的分流规则：非影像走 `one_item_name`，影像走 `two_item_name`；
            第三象限从 `JKYLBJ` 做抽取并映射标准项目名，再与第一、二象限去重；
            第四象限按主诉从业务库做 LIKE 召回，仅保留功能医学“质谱”类体检项目。

        Args:
            source: 聚合后的源数据，含 splitRows/finalConclusion 等。
            single_exam_items: 前端补充单项体检条目。
                `itemText` 作为单项项目名，`abnormalIndicator` 作为异常指标描述。
            chief_complaint_text: 前端补充主诉文本。

        Returns:
            体检四象限列表（固定 4 个象限）。

        Edge Cases:
            1. 当 splitRows 为空时，第三象限仍可基于终检意见与前端补充条目产出结果。
            2. 映射表未命中时保留原始抽取项，避免有效复查项被误丢弃。
        """
        total_started_at = time.perf_counter()
        normalized_trace_id = trace_id or "-"
        normalized_study_id = study_id or "-"

        buckets = _empty_buckets(_EXAM_BUCKETS)
        # 1) 基于分拆表先构建第一、二象限：这是“体检事实数据”最稳定的来源。
        q1_q2_started_at = time.perf_counter()
        for row in source.get("splitRows", []):
            one_item = _normalize_text(row.get("one_item_name"))
            two_item = _normalize_text(row.get("two_item_name"))
            abnormal_item = _normalize_text(row.get("abnormal_item"))
            category = _normalize_text(row.get("category_name"))
            if not abnormal_item:
                continue

            # 1. 非影像异常归第一象限；影像异常归第二象限，符合“1+X”基础筛查语义。
            if one_item and category != '影像类':
                buckets[0]["abnormalIndicators"].append(abnormal_item)
                buckets[0]["recommendationPlans"].append(one_item)
            if two_item or (one_item and category == '影像类'):
                imaging_name = two_item or one_item or ""
                buckets[1]["abnormalIndicators"].append(abnormal_item)
                buckets[1]["recommendationPlans"].append(imaging_name)

        # 对第一、二象限的推荐方案去重
        buckets[0]["recommendationPlans"] = list(_build_exam_dedup_keys(buckets[0]["recommendationPlans"]))
        buckets[1]["recommendationPlans"] = list(_build_exam_dedup_keys(buckets[1]["recommendationPlans"]))
        logger.info(
            "health quadrant stage duration stage=service.exam.q1_q2_build duration_ms=%s trace_id=%s study_id=%s",
            int((time.perf_counter() - q1_q2_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
        )

        # 2) 先建立 Q1/Q2 去重基线：后续 Q3/Q4 只补“新增价值项”，避免重复展示。
        existing_exam_keys = _build_exam_dedup_keys(
            buckets[0]["recommendationPlans"] + buckets[1]["recommendationPlans"]
        )

        # 3) 第三象限：终检意见抽取 -> 标准化映射 -> 与 Q1/Q2 去重。
        q3_extract_started_at = time.perf_counter()
        final_conclusion = _normalize_text(source.get("finalConclusion")) or ""
        extracted_items = await self._extract_deep_screening_items(
            final_conclusion=final_conclusion,
            trace_id=normalized_trace_id,
            study_id=normalized_study_id,
        )
        logger.info(
            "health quadrant stage duration stage=service.exam.q3_extract duration_ms=%s trace_id=%s study_id=%s extracted_count=%s",
            int((time.perf_counter() - q3_extract_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
            len(extracted_items),
        )
        q3_merge_started_at = time.perf_counter()
        mapped_items = await self._map_doctor_conclusion_items_to_standard(items=extracted_items)
        q3_items = _deduplicate_exam_items_by_keys(mapped_items or extracted_items, existing_exam_keys)
        if q3_items:
            # 终检意见抽取项属于第三象限“专项深度筛查”。
            buckets[2]["recommendationPlans"].extend(q3_items)

        # 单项体检是结构化人工补充输入：项目名进入 recommendationPlans，异常描述进入 abnormalIndicators。
        single_plan_seen: set[str] = set()
        for item in single_exam_items:
            item_text = _normalize_text(item.get("itemText"))
            if not item_text:
                continue
            item_key = _normalize_exam_name_for_key(item_text)
            if not item_key or item_key in existing_exam_keys or item_key in single_plan_seen:
                continue
            single_plan_seen.add(item_key)
            buckets[2]["recommendationPlans"].append(item_text)

            abnormal_indicator = _normalize_text(item.get("abnormalIndicator"))
            if abnormal_indicator:
                buckets[2]["abnormalIndicators"].append(abnormal_indicator)
        if single_plan_seen:
            existing_exam_keys.update(single_plan_seen)
        logger.info(
            "health quadrant stage duration stage=service.exam.q3_merge duration_ms=%s trace_id=%s study_id=%s q3_plan_count=%s single_plan_count=%s",
            int((time.perf_counter() - q3_merge_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
            len(buckets[2]["recommendationPlans"]),
            len(single_plan_seen),
        )

        # 4) 第四象限：基于主诉做 pathway LIKE 召回，再过滤为功能医学“质谱”检测项目。
        q4_started_at = time.perf_counter()
        # 主诉文本允许为空；统一按中英文逗号切分为条目列表，确保 Q4 召回和去重逻辑稳定。
        normalized_complaint_text = _normalize_text(chief_complaint_text) or ""
        # 按稳定排序输出主诉条目，确保测试和签名口径一致，避免同语义输入顺序抖动。
        chief_complaint_items = sorted(item for item in re.split(r"[，,]", normalized_complaint_text) if item)
        q4_candidates = await self._query_q4_mass_spec_projects(chief_complaint_items=chief_complaint_items)
        q4_items = _deduplicate_exam_items_by_keys(q4_candidates, existing_exam_keys)
        if q4_items:
            buckets[3]["abnormalIndicators"].extend(chief_complaint_items)
            buckets[3]["recommendationPlans"].extend(q4_items)
            existing_exam_keys.update(_build_exam_dedup_keys(q4_items))
        logger.info(
            "health quadrant stage duration stage=service.exam.q4_recall duration_ms=%s trace_id=%s study_id=%s q4_candidate_count=%s q4_result_count=%s",
            int((time.perf_counter() - q4_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
            len(q4_candidates),
            len(q4_items),
        )

        # 5) 统一补齐推荐方案与去重，保证确认页字段完整且可直接渲染。
        finalize_started_at = time.perf_counter()
        _finalize_exam_recommendations(buckets)
        logger.info(
            "health quadrant stage duration stage=service.exam.finalize duration_ms=%s trace_id=%s study_id=%s",
            int((time.perf_counter() - finalize_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
        )
        logger.info(
            "health quadrant stage duration stage=service.exam.total duration_ms=%s trace_id=%s study_id=%s",
            int((time.perf_counter() - total_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
        )
        return buckets

    async def _build_treatment_quadrants(
        self,
        *,
        sex: str,
        age: int | None,
        source: dict[str, Any],
        single_exam_items: list[dict[str, str]],
        chief_complaint_text: str | None,
        study_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """构建治疗四象限。

        功能：
            治疗链路采用三阶段编排：
            1) Triage: LLM 分诊定象限 + 归属系统
            2) Match: 基于系统/指标从知识库召回候选项目
            3) Safety: 一次批量做禁忌审查并剔除，再按 DB 规则装填四象限

        Args:
            source: 聚合后的源数据。
            single_exam_items: 前端补充单项体检条目。
            chief_complaint_text: 前端补充主诉。
            study_id: 体检主单号，仅用于日志追踪。
            trace_id: 链路追踪 ID。

        Returns:
            治疗四象限列表（固定 4 个象限）。

        Edge Cases:
            安全审查后若全部项目被剔除，仍返回四个空象限，保证前端结构稳定。
        """
        total_started_at = time.perf_counter()
        normalized_trace_id = trace_id or "-"
        normalized_study_id = study_id or "-"

        # 1) 输入归一化：把 jcjg + 单项收敛成 triage 语料，避免提示词遗漏关键上下文。
        normalize_started_at = time.perf_counter()
        abnormal_items_text = _build_treatment_triage_inputs(
            jcjg=source["jcjg"],
            single_exam_items=single_exam_items
        )
        logger.info(
            "health quadrant stage duration stage=service.treatment.normalize duration_ms=%s trace_id=%s study_id=%s in_count=%s",
            int((time.perf_counter() - normalize_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
            len(abnormal_items_text),
        )
        if not abnormal_items_text:
            buckets = _empty_buckets(_TREATMENT_BUCKETS)
            _finalize_treatment_recommendations(buckets)
            return buckets

        # 2) Triage 阶段：顶层失败必须硬失败；行级失败只丢弃异常行。
        triage_started_at = time.perf_counter()
        triage_items, triage_dropped = await self._triage_treatment_items(
            sex=sex,
            age=age,
            abnormal_items_text=_normalize_text(abnormal_items_text),
            chief_complaint_text=_normalize_text(chief_complaint_text),
            trace_id=normalized_trace_id,
            study_id=normalized_study_id,
        )
        logger.info(
            "health quadrant stage duration stage=service.treatment.triage duration_ms=%s trace_id=%s study_id=%s in_count=%s out_count=%s dropped_count=%s",
            int((time.perf_counter() - triage_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
            len(abnormal_items_text),
            len(triage_items),
            triage_dropped,
        )
        if not triage_items:
            buckets = _empty_buckets(_TREATMENT_BUCKETS)
            _finalize_treatment_recommendations(buckets)
            return buckets

        # 3) Match 阶段：仅负责召回，不做安全过滤。
        match_started_at = time.perf_counter()
        candidates = await self._match_treatment_candidates(
            triage_items=triage_items,
            trace_id=normalized_trace_id,
            study_id=normalized_study_id,
        )
        logger.info(
            "health quadrant stage duration stage=service.treatment.match duration_ms=%s trace_id=%s study_id=%s in_count=%s out_count=%s",
            int((time.perf_counter() - match_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
            len(triage_items),
            len(candidates),
        )
        if not candidates:
            buckets = _build_treatment_quadrant_buckets_from_triage(triage_items=triage_items)
            _finalize_treatment_recommendations(buckets)
            return buckets

        # 4) Safety 阶段：对所有候选项目一次性做禁忌症过滤，避免多次模型调用带来的时延和不一致。
        #   - Safety 后执行每象限 Top3 限流，只保留优先级最高的 3 个项目。
        #   - dropped_count 统计口径：禁忌剔除 + 未覆盖剔除 + Top3 裁剪剔除。
        safety_started_at = time.perf_counter()
        safe_candidates, safety_dropped = await self._filter_treatment_candidates_by_safety(
            candidates=candidates,
            chief_complaint_text=chief_complaint_text,
            trace_id=normalized_trace_id,
            study_id=normalized_study_id,
        )
        logger.info(
            "health quadrant stage duration stage=service.treatment.safety duration_ms=%s trace_id=%s study_id=%s in_count=%s out_count=%s dropped_count=%s",
            int((time.perf_counter() - safety_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
            len(candidates),
            len(safe_candidates),
            safety_dropped,
        )

        # 5) Fill 阶段：按 triage 和安全过滤结果装填固定四象限结构，保证前端渲染契约不变。
        fill_started_at = time.perf_counter()
        buckets = _build_treatment_quadrant_buckets(
            triage_items=triage_items,
            safe_candidates=safe_candidates,
        )
        _finalize_treatment_recommendations(buckets)
        logger.info(
            "health quadrant stage duration stage=service.treatment.fill duration_ms=%s trace_id=%s study_id=%s quadrant_count=%s",
            int((time.perf_counter() - fill_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
            len(buckets),
        )
        logger.info(
            "health quadrant stage duration stage=service.treatment.total duration_ms=%s trace_id=%s study_id=%s",
            int((time.perf_counter() - total_started_at) * 1000),
            normalized_trace_id,
            normalized_study_id,
        )
        return buckets

    async def _triage_treatment_items(
        self,
        *,
        sex: str,
        age: int | None,
        abnormal_items_text: str,
        chief_complaint_text: str | None,
        trace_id: str,
        study_id: str,
    ) -> tuple[list[_TreatmentTriageItem], int]:
        """执行治疗四象限分诊（Triage）并做行级容错。

        功能：
            使用单次 LLM 请求输出结构化分诊结论。顶层解析失败直接硬失败，
            行级字段不合法只剔除异常行，避免单条脏数据拖垮整单。

        Args:
            triage_inputs: 待分诊异常项与主诉列表。
            source: 源数据，用于补充终检意见上下文。
            trace_id: 链路追踪 ID。
            study_id: 体检主单号。

        Returns:
            `(triage_items, dropped_count)`。

        Raises:
            HealthQuadrantServiceError: 当 LLM 调用失败、输出非 JSON 或顶层结构非法时抛出。
        """

        prompt = _build_treatment_triage_prompt(
            sex=sex,
            age=age,
            abnormal_items_text=abnormal_items_text,
            chief_complaint_text=chief_complaint_text
        )
        llm_started_at = time.perf_counter()
        try:
            raw = await self._llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout_seconds=120.0,
            )
        except Exception as exc:
            logger.error(
                "health quadrant treatment triage llm failed trace_id=%s study_id=%s error_type=%s error=%r",
                trace_id,
                study_id,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise HealthQuadrantServiceError("triage_failed: 治疗四象限分诊失败") from exc
        logger.info(
            "health quadrant stage duration stage=service.treatment.triage_llm_request duration_ms=%s trace_id=%s study_id=%s",
            int((time.perf_counter() - llm_started_at) * 1000),
            trace_id,
            study_id,
        )
        parsed = json_loads_safe(raw)
        if not isinstance(parsed, dict):
            raise HealthQuadrantServiceError("triage_failed: 分诊模型返回非 JSON 对象")
        rows = parsed.get("triage_results")
        if not isinstance(rows, list):
            raise HealthQuadrantServiceError("triage_failed: triage_results 非法")

        # 以“条目+描述”为主键，冲突时保留更高风险象限（RED > ORANGE > BLUE > GREEN）。
        normalized_map: dict[str, _TreatmentTriageItem] = {}
        dropped = 0
        for row in rows:
            triage_item = _parse_treatment_triage_row(row)
            if triage_item is None:
                dropped += 1
                continue
            existed = normalized_map.get(triage_item.dedupe_key)
            if existed is None:
                normalized_map[triage_item.dedupe_key] = triage_item
                continue
            if _TREATMENT_QUADRANT_PRIORITY[triage_item.quadrant] < _TREATMENT_QUADRANT_PRIORITY[existed.quadrant]:
                normalized_map[triage_item.dedupe_key] = triage_item
        return list(normalized_map.values()), dropped

    async def _match_treatment_candidates(
        self,
        *,
        triage_items: list[_TreatmentTriageItem],
        trace_id: str,
        study_id: str,
    ) -> list[_TreatmentCandidateProject]:
        """按 triage 结果执行知识库召回（Match）。

        功能：
            Match 阶段的职责是“多路召回并并集去重”，不做安全判断。召回策略优先级：
            indicator_name 精确命中 > indications 模糊补充。

        Args:
            triage_items: Triage 阶段产出的有效条目。
            trace_id: 链路追踪 ID。
            study_id: 体检主单号。

        Returns:
            按候选排序规则稳定输出的候选项目列表。

        Raises:
            HealthQuadrantServiceError: 当仓储查询失败时抛出。
        """

        try:
            rows = await self._treatment_repository.match_candidates(triage_items=triage_items)
        except HealthQuadrantTreatmentRepositoryError as exc:
            logger.error(
                "health quadrant treatment match failed trace_id=%s study_id=%s error=%s",
                trace_id,
                study_id,
                exc,
                exc_info=True,
            )
            raise HealthQuadrantServiceError("match_failed: 治疗四象限知识库召回失败") from exc

        candidates: list[_TreatmentCandidateProject] = []
        seen: set[tuple[str, str, str, str]] = set()
        for row in rows:
            project_name = _normalize_text(row.get("project_name"))
            package_version = _normalize_text(row.get("package_version")) or "-"
            quadrant = _normalize_text(row.get("quadrant"))
            belong_system = _normalize_text(row.get("belong_system"))
            trigger_item = _normalize_text(row.get("trigger_item"))
            if (
                not project_name
                or not package_version
                or not quadrant
                or quadrant not in _TREATMENT_QUADRANT_TO_INDEX
                or not belong_system
                or not trigger_item
            ):
                continue
            dedupe_key = (project_name, package_version, quadrant, trigger_item)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            candidate_id = f"{project_name}||{package_version}||{quadrant}||{trigger_item}"
            candidates.append(
                _TreatmentCandidateProject(
                    candidate_id=candidate_id,
                    project_name=project_name,
                    package_version=package_version,
                    quadrant=quadrant,
                    belong_system=belong_system,
                    trigger_item=trigger_item,
                    # 兼容历史 mapping 数据只提供 trigger_item 的场景，避免新字段要求打断主链路。
                    trigger_value_or_desc=trigger_item,
                    priority_level=_safe_int(row.get("priority_level"), default=1000),
                    sort_order=_safe_int(row.get("sort_order"), default=1000),
                    match_source=_normalize_text(row.get("match_source")) or "unknown",
                    contraindications=_normalize_text(row.get("contraindications")) or "",
                )
            )
        candidates.sort(key=lambda item: (item.priority_level, item.sort_order, item.project_name))
        return candidates

    async def _filter_treatment_candidates_by_safety(
        self,
        *,
        candidates: list[_TreatmentCandidateProject],
        chief_complaint_text: str | None,
        trace_id: str,
        study_id: str,
    ) -> tuple[list[_TreatmentCandidateProject], int]:
        """执行单次全量安全审查（Filter）。

        功能：
            1. 一次性提交全部候选项目给 Safety LLM 做禁忌审查；
            2. 对未被有效审查覆盖的项目按“安全优先”默认剔除；
            3. 在安全过滤后对每个象限仅保留 Top3 项目，避免单象限推荐过载。

        Args:
            candidates: Match 阶段候选项目。
            chief_complaint_text: 主诉，用于禁忌风险判断。
            trace_id: 链路追踪 ID。
            study_id: 体检主单号。

        Returns:
            `(safe_candidates, dropped_count)`，其中 dropped_count 包含禁忌剔除与未覆盖剔除。

        Raises:
            HealthQuadrantServiceError: 当 Safety 模型调用失败或顶层结构非法时抛出。
        """

        if not candidates:
            return [], 0

        # 先做一次全量安全过滤，再做每象限裁剪，避免“先分桶后审查”导致的多次模型调用成本。
        safe_candidates, dropped_count = await self._filter_treatment_candidates_by_quadrant_safety(
            candidates=candidates,
            chief_complaint_text=chief_complaint_text,
            trace_id=trace_id,
            study_id=study_id,
        )

        # 3) 安全过滤后执行每象限 Top3 裁剪，防止单象限项目过多造成前端信息噪声。
        limited_candidates, top_limit_dropped = _limit_treatment_candidates_per_quadrant(
            candidates=safe_candidates,
            top_n=3,
        )
        dropped_count += top_limit_dropped
        return limited_candidates, dropped_count

    async def _filter_treatment_candidates_by_quadrant_safety(
        self,
        *,
        candidates: list[_TreatmentCandidateProject],
        chief_complaint_text: str | None,
        trace_id: str,
        study_id: str,
    ) -> tuple[list[_TreatmentCandidateProject], int]:
        """执行单次 Safety 审查并返回安全候选。

        功能：
            把全部候选项目一次性提交给 Safety LLM 进行禁忌症过滤。
            本方法只负责“安全过滤”，Top3 裁剪由上层方法统一执行。

        Returns:
            `(safe_candidates, dropped_count)`。
        """

        if not candidates:
            return [], 0

        prompt = _build_treatment_safety_prompt(
            chief_complaint_text=chief_complaint_text,
            candidates=candidates,
        )
        llm_started_at = time.perf_counter()
        try:
            raw = await self._llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout_seconds=120.0,
            )
        except Exception as exc:
            logger.error(
                "health quadrant treatment safety llm failed trace_id=%s study_id=%s error_type=%s error=%r",
                trace_id,
                study_id,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise HealthQuadrantServiceError("safety_failed: 治疗四象限安全审查失败") from exc
        logger.info(
            "health quadrant stage duration stage=service.treatment.safety_llm_request duration_ms=%s trace_id=%s study_id=%s in_count=%s",
            int((time.perf_counter() - llm_started_at) * 1000),
            trace_id,
            study_id,
            len(candidates),
        )

        parsed = json_loads_safe(raw)
        if not isinstance(parsed, dict):
            raise HealthQuadrantServiceError(f"safety_failed: 安全模型返回非 JSON 对象")
        rows = parsed.get("safety_checks")
        if not isinstance(rows, list):
            raise HealthQuadrantServiceError(f"safety_failed: safety_checks 非法")

        # 兼容两类模型输出：
        # 1) 精确输出 candidate_id（优先，歧义最小）；
        # 2) 仅输出 project_name（保留历史 Prompt 行为，按名称回退匹配）。
        review_by_candidate_id: dict[str, bool] = {}
        review_by_project_name: dict[str, bool] = {}
        for row in rows:
            parsed_row = _parse_treatment_safety_row(row)
            if parsed_row is None:
                continue
            candidate_id, project_name, is_contraindicated = parsed_row
            if candidate_id:
                review_by_candidate_id[candidate_id] = is_contraindicated
            if project_name:
                review_by_project_name[project_name] = is_contraindicated

        safe_candidates: list[_TreatmentCandidateProject] = []
        dropped_count = 0
        for candidate in candidates:
            verdict = review_by_candidate_id.get(candidate.candidate_id)
            if verdict is None:
                verdict = review_by_project_name.get(candidate.project_name)
            if verdict is None:
                dropped_count += 1
                continue
            if verdict:
                dropped_count += 1
                continue
            safe_candidates.append(candidate)
        return safe_candidates, dropped_count

    async def _extract_deep_screening_items(
        self,
        *,
        final_conclusion: str,
        trace_id: str | None = None,
        study_id: str | None = None,
    ) -> list[str]:
        """从终检意见抽取专项筛查项目。

        功能：
            终检意见通常是自然语言段落，规则很难覆盖。这里用轻量提示词做 JSON 提取，
            若 LLM 异常则降级为关键词切分，保证链路可用。

        Args:
            final_conclusion: 终检意见原文（JKYLBJ）。

        Returns:
            提取出的“进一步检查/复查/筛查”项目列表。

        Edge Cases:
            LLM 超时、输出非 JSON、或返回空结果时，返回空列表。
        """
        normalized_trace_id = trace_id or "-"
        normalized_study_id = study_id or "-"
        if not final_conclusion:
            logger.info("health quadrant deep screening skipped because final_conclusion is empty")
            return []
        logger.info(
            "health quadrant deep screening llm start conclusion_length=%s",
            len(final_conclusion)
        )
        llm_request_started_at = time.perf_counter()
        prompt = f"""
            # 角色设定
            你是一个专业的临床医疗文本数据抽取引擎（NER Engine）。你的任务是从医生撰写的【终检意见】中，精准提取出建议患者去进行的“复查”、“筛查”、“监测”或“进一步检查”的医疗项目实体。
            
            # 提取规则（请严格遵守底线）：
            1. **绝对忠实原文**：禁止进行任何脱离文本的医学推理！即使你认为患者需要查A，但原文没写，也绝对不能输出A。
            2. **精准切分**：遇到顿号“、”、逗号“，”或“和”、“或”连接的多个独立检查项目时（例如“UA、血脂、空腹血糖”），必须将其拆分为独立的数组元素。
            3. **严格排他**：
               - 排除**治疗或干预建议**（如：调脂治疗、控制体重、饮食调节、规范治疗等）。
               - 排除**就诊科室建议**（如：甲状腺外科就诊、心内科就诊等，除非明确要求提取）。
               - 排除**非具体的宽泛指导**（如：按影像检查推荐随诊复查、进一步检查）。
            4. **上下文指代还原（重要）**：当医生建议复查“标志物”、“抗体”、“指标”、“结节”等【泛指代名词】时，必须结合该段落的前文语境，找到具体指代的项目名称并完整提取。
               - 示例：前文写“标志物CYFRA21-1高”，后文建议“择期复查标志物”，则提取结果必须是“标志物CYFRA21-1”或“CYFRA21-1”，严禁仅提取“标志物”。
            5. **完整保留修饰语与代号**：如果检查项目带有具体的定语修饰、英文缩写或数字代号（如“动态心电监测”、“动态血压监测(ABPM或HBPM)”、“CYFRA21-1”），请完整合并提取，绝对不要截断。
            
            # 输出格式
            请仅输出合法的 JSON 格式，不要包含任何额外的解释性文字（如 Markdown 的 ```json 标签等，只需纯 JSON 文本）。JSON 结构如下：
            {{
              "recommended_exams": [
                "项目名称1",
                "项目名称2"
              ]
            }}
            
            # 待处理文本：
            {final_conclusion}
        """
        try:
            # 1) 优先走 LLM 结构化提取：在长文本场景下比纯关键词更稳健。
            raw = await self._llm_service.chat(
                [
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout_seconds=120.0,
            )
            logger.info(
                "health quadrant stage duration stage=service.exam.q3_llm_request duration_ms=%s trace_id=%s study_id=%s status=success",
                int((time.perf_counter() - llm_request_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
            )
            logger.info(
                "health quadrant deep screening llm raw received raw_length=%s raw_preview=%s",
                len(raw),
                raw[:240],
            )
            parse_started_at = time.perf_counter()
            parsed = json_loads_safe(raw)
            items = parsed.get("recommended_exams") if isinstance(parsed, dict) else []
            if isinstance(items, list):
                normalized_items = [item.strip() for item in items if isinstance(item, str) and item.strip()]
                logger.info(
                    "health quadrant stage duration stage=service.exam.q3_llm_parse duration_ms=%s trace_id=%s study_id=%s parsed_count=%s",
                    int((time.perf_counter() - parse_started_at) * 1000),
                    normalized_trace_id,
                    normalized_study_id,
                    len(normalized_items),
                )
                logger.info(
                    "health quadrant deep screening llm parsed items_count=%s items_preview=%s",
                    len(normalized_items),
                    normalized_items,
                )
                return normalized_items
            logger.info(
                "health quadrant stage duration stage=service.exam.q3_llm_parse duration_ms=%s trace_id=%s study_id=%s parsed_count=0",
                int((time.perf_counter() - parse_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
            )
            logger.warning(
                "health quadrant deep screening llm parsed but recommended_exams is not list parsed_type=%s",
                type(parsed).__name__,
            )
        except Exception as exc:
            # 2) LLM 异常不外抛：提取失败不能阻塞整个四象限主链路。
            logger.info(
                "health quadrant stage duration stage=service.exam.q3_llm_request duration_ms=%s trace_id=%s study_id=%s status=failed",
                int((time.perf_counter() - llm_request_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
            )
            logger.warning(
                "extract deep screening by llm failed error_type=%s error=%r",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            return []

        logger.info("health quadrant deep screening llm returned empty items")
        return []

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

        mapped_lookup: dict[str, str] = {}
        try:
            pool = await self._mysql_pools.get_business_pool()
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

        return [mapped_lookup.get(item, item) for item in normalized_items if item in mapped_lookup]

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

        try:
            pool = await self._mysql_pools.get_business_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 每条主诉都能触发召回，符合已确认的“任一主诉命中即召回”策略。
                    like_clauses = " OR ".join(["p.trigger_name LIKE %s"] * len(normalized_complaints))
                    params: list[str] = [f"%{item}%" for item in normalized_complaints]
                    await cursor.execute(
                        f"""
                        SELECT DISTINCT n.exam_name
                        FROM lz_clinical_pathway p
                        JOIN lz_physicalexam_node n ON n.pathway_id = p.pathway_id
                        WHERE n.exam_type = 'FUNCTIONAL'
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


def _normalize_single_exam_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """规范化单项体检列表。

    功能：
        前端可能提交空对象、重复条目或不同字段大小写。这里统一折叠成标准形状，
        避免进入持久化维度后出现“语义相同但命中失败”。
    """

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in items:
        item_id = _normalize_text(raw.get("itemId") if isinstance(raw, dict) else None) or ""
        item_text = _normalize_text(raw.get("itemText") if isinstance(raw, dict) else None) or ""
        abnormal_indicator = _normalize_text(raw.get("abnormalIndicator") if isinstance(raw, dict) else None) or ""
        if not item_id and not item_text and not abnormal_indicator:
            continue
        key = (item_id, item_text, abnormal_indicator)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "itemId": item_id,
                "itemText": item_text,
                "abnormalIndicator": abnormal_indicator,
            }
        )
    normalized.sort(key=lambda x: (x["itemId"], x["itemText"], x["abnormalIndicator"]))
    return normalized


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_int(value: Any, *, default: int) -> int:
    """安全转换整数，避免脏数据把排序链路打断。"""

    try:
        return int(value)
    except Exception:
        return default


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
            "q_code": code,
            "q_name": name,
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
    # 规则解释：保留前序链路已经写入的个性化推荐项，再补默认推荐模板，避免覆盖业务输入。
    _merge_recommendation_defaults(buckets[3], ["全基因检测", "PET-MR 高端筛查评估"])
    for bucket in buckets:
        bucket["abnormalIndicators"] = _deduplicate_text_list(bucket["abnormalIndicators"])


def _finalize_treatment_recommendations(buckets: list[dict[str, Any]]) -> None:
    for bucket in buckets:
        bucket["abnormalIndicators"] = _deduplicate_text_list(bucket["abnormalIndicators"])
        bucket["recommendationPlans"] = _deduplicate_text_list(bucket["recommendationPlans"])


def _build_treatment_triage_inputs(
    *,
    jcjg: str,
    single_exam_items: list[dict[str, str]],
) -> list[str]:
    """构造治疗分诊输入语料。

    功能：
        分诊提示词依赖“套餐异常指标+单项异常指标”的完整上下文。这里把多源数据归一并去重，
        防止 LLM 因输入碎片化出现象限漏判。
    """

    merged: list[str] = []
    merged.append(jcjg)
    for item in single_exam_items:
        abnormal_indicator = _normalize_text(item.get("abnormalIndicator"))
        if abnormal_indicator:
            merged.append(abnormal_indicator)
    return "\n".join(merged)


def _build_treatment_triage_prompt(
    *,
    sex: str,
    age: int | None,
    abnormal_items_text: str,
    chief_complaint_text: str
) -> str:
    """构建治疗分诊 Prompt。"""
    return f"""
        # 角色设定
        你是一位拥有 20 年临床与功能医学经验的顶级健康管理分诊专家（Triage Expert）。你的任务是根据患者的【异常体检指标】和【主诉症状】，严格按照我提供的“医疗风险四象限标准”，对每一项异常进行危险评级，并输出结构化的 JSON 结果。
        
        # 医疗风险四象限评级标准（必须严格遵守）
        
        1. **【RED】红色高风险区（急治/救命）**：
           - 判定标准：指标严重偏离正常值，存在确诊的重大疾病隐患、即刻的心脑血管意外风险（如不稳定斑块、重度狭窄）、急性靶器官损伤或高度疑似恶性肿瘤（肿瘤标志物极高）。
           - 核心词：危急、重度、随时有生命或致残危险、需立即就医。
        
        2. **【ORANGE】橙色较高风险区（干预/治病）**：
           - 判定标准：健康风险明确，指标明显异常（如中重度代谢综合征、严重睡眠障碍、结节明显进展、脏器功能轻度下降），不立即干预将在中短期内恶化为重大疾病。
           - 核心词：明显异常、持续进展、需专项方案重点干预。
        
        3. **【BLUE】蓝色一般风险区（调整/防病）**：
           - 判定标准：指标处于临界值或轻微异常（如轻度血脂异常、轻度胰岛素抵抗、维生素D缺乏、免疫力低下、女性荷尔蒙轻微失调），风险相对可控。
           - 核心词：临界、轻度、亚健康、需生活方式与营养干预。
        
        4. **【GREEN】绿色低风险区（维养/抗衰）**：
           - 判定标准：健康状况良好，无明显病理性异常指标。主要基于客户年龄、轻微体感或主动抗衰需求进行日常保养。
           - 核心词：健康维持、免疫巩固、抗衰老、日常营养补充。
        
        # 分析规则
        1. **取高原则**：如果一个指标同时满足两个象限的特征，必须强行归入更高危的象限（RED > ORANGE > BLUE > GREEN）。
        2. **禁止臆测**：绝不允许凭空捏造患者没有的症状或指标。只对输入的数据进行评级。
        3. **拆分独立项**：每一个独立的异常指标或主诉，必须独立生成一条记录，不可合并。
        
        # 输出格式限制
        请仅输出合法的 JSON 格式，禁止包含任何 Markdown 标记（如 ```json）或其他解释性语言。JSON 结构必须严格如下：
        {{
          "triage_results": [
            {{
              "item_name": "异常指标或主诉的名称",
              "value_or_desc": "异常指标取值或症状描述（没有具体数值则不用填）",
              "quadrant": "RED / ORANGE / BLUE / GREEN (必须是这四个大写英文之一)",
              "belong_system": "该异常归属的医学系统(必须从以下列表中选择：消化系统、呼吸系统、内分泌系统、内分泌系统、心脑血管、泌尿系统、生殖系统、骨骼运动、神经系统、免疫系统)",
              "reason": "结合四象限标准，给出简短且专业的医学判定理由(限50字以内)"
            }}
          ]
        }}
        
        # 待分析患者数据：
        【基本信息】：性别：{sex}，年龄：{age if age is not None else "未知"}岁
        【异常检查指标】：
        {abnormal_items_text}
        【患者主诉/症状】：
        {chief_complaint_text}
        """.strip()


def _build_treatment_safety_prompt(
    *,
    chief_complaint_text: str | None,
    candidates: list[_TreatmentCandidateProject],
) -> str:
    """构建治疗安全审查 Prompt。"""

    # 安全审查以自由文本主诉为主输入：为空时显式标记“无主诉”，降低模型臆测风险。
    complaints = _normalize_text(chief_complaint_text) or "无主诉"
    candidate_payload = [
        {
            "candidate_id": item.candidate_id,
            "project_name": item.project_name,
            "package_version": item.package_version,
            "quadrant": item.quadrant,
            "belong_system": item.belong_system,
            "trigger_item": item.trigger_item,
            "contraindications": item.contraindications,
        }
        for item in candidates
    ]
    return f"""
        # 角色设定
        你是一个顶级的临床决策支持系统（CDSS）引擎，身兼两职：
        1. **安全风控官**：严格审查候选项目的禁忌症，宁错杀不放过。
        2. **临床路径优化师**：在绝对安全的前提下，结合患者的主诉和病史，为每个治疗象限挑选出最合适的 Top 3 核心干预项目。
        
        # 任务一：安全审查原则（生命至上）
        1. **语义包含与同义穿透**：识别患者不规范的口语化病史。如患者表述“心衰”、“放过支架”，必须精准触发生理或器械类禁忌症拦截。
        2. **就高不就低**：若无法 100% 确认安全，必须判定为“拦截（is_contraindicated: true）”。
        
        # 任务二：各象限 Top 3 优选原则（精准医疗）
        1. **绝对安全前提**：所有在任务一中被判定为 `is_contraindicated: true` 的项目，**绝对禁止**出现在推荐列表中！
        2. **限制数量**：按照 RED（红）、ORANGE（橙）、BLUE（蓝）、GREEN（绿）四个象限进行输出。每个象限最多只推荐 3 个项目（宁缺毋滥，如果没有符合该象限的合适项目，输出空列表）。
        3. **排序权重**：
           - 匹配度：高度契合患者当前最严重主诉的项目优先。
           - 标签库：带有“优选(PREFERRED)”标签的候选项目优先于“备选(ALTERNATIVE)”。
        
        # 输出格式限制
        必须输出纯 JSON 格式。包含 `safety_checks`（全部候选项目的体检报告）和 `top_recommendations`（各象限过滤后的最终 Top 3 方案）。
        {{
          "safety_checks": [
            {{
              "project_name": "候选项目名称",
              "is_contraindicated": true 或 false,
              "reason": "是否拦截的医学推理（限30字）"
            }}
          ],
          "top_recommendations": {{
            "RED": [
              {{
                 "project_name": "项目名称",
                 "recommendation_reason": "结合主诉给出为何它能排进前三的专业理由"
              }}
            ],
            "ORANGE": [ ... ],
            "BLUE": [ ... ],
            "GREEN": [ ... ]
          }}
        }}
        
        # 待处理数据：
        患者主诉：
        {complaints}
        候选项目：
        {json.dumps(candidate_payload, ensure_ascii=False)}
        """.strip()


def _parse_treatment_triage_row(raw: Any) -> _TreatmentTriageItem | None:
    """解析并校验单条 triage 记录。"""

    if not isinstance(raw, dict):
        return None
    item_name = _normalize_text(raw.get("item_name"))
    value_or_desc = _normalize_text(raw.get("value_or_desc"))
    quadrant = _normalize_text(raw.get("quadrant"))
    belong_system = _normalize_text(raw.get("belong_system"))
    reason = _normalize_text(raw.get("reason")) or ""
    if not item_name or not value_or_desc or not quadrant or not belong_system:
        return None
    normalized_quadrant = quadrant.upper()
    if normalized_quadrant not in _TREATMENT_QUADRANT_TO_INDEX:
        return None
    if belong_system not in _TREATMENT_SYSTEM_ENUM:
        return None
    return _TreatmentTriageItem(
        item_name=item_name,
        value_or_desc=value_or_desc,
        quadrant=normalized_quadrant,
        belong_system=belong_system,
        reason=reason,
    )


def _parse_treatment_safety_row(raw: Any) -> tuple[str | None, str | None, bool] | None:
    """解析单条 safety 结果，兼容 candidate_id 与 project_name 双键回填。"""

    if not isinstance(raw, dict):
        return None
    candidate_id = _normalize_text(raw.get("candidate_id"))
    project_name = _normalize_text(raw.get("project_name"))
    is_contraindicated = raw.get("is_contraindicated")
    if not isinstance(is_contraindicated, bool):
        return None
    if not candidate_id and not project_name:
        return None
    return candidate_id, project_name, is_contraindicated


def _build_treatment_quadrant_buckets_from_triage(
    *,
    triage_items: list[_TreatmentTriageItem],
) -> list[dict[str, Any]]:
    """仅根据 triage 结果构建四象限骨架。"""

    buckets = _empty_buckets(_TREATMENT_BUCKETS)
    for item in triage_items:
        bucket = buckets[_TREATMENT_QUADRANT_TO_INDEX[item.quadrant]]
        bucket["abnormalIndicators"].append(item.item_name + item.value_or_desc)
    return buckets


def _build_treatment_quadrant_buckets(
    *,
    triage_items: list[_TreatmentTriageItem],
    safe_candidates: list[_TreatmentCandidateProject],
) -> list[dict[str, Any]]:
    """将 triage 与安全通过的候选项目装填为四象限结果。"""

    buckets = _build_treatment_quadrant_buckets_from_triage(triage_items=triage_items)
    for candidate in safe_candidates:
        bucket = buckets[_TREATMENT_QUADRANT_TO_INDEX[candidate.quadrant]]
        bucket["recommendationPlans"].append(f"{candidate.project_name} ({candidate.package_version})")
    if not any(bucket["recommendationPlans"] for bucket in buckets):
        buckets[-1]["abnormalIndicators"].append(_TREATMENT_EMPTY_MESSAGE)
    return buckets


def _limit_treatment_candidates_per_quadrant(
    *,
    candidates: list[_TreatmentCandidateProject],
    top_n: int,
) -> tuple[list[_TreatmentCandidateProject], int]:
    """对安全过滤后的候选按象限做 TopN 裁剪。

    功能：
        Safety 阶段之后若单象限候选过多，会导致报告可读性下降。这里按候选排序稳定裁剪，
        保证每个象限最多展示 `top_n` 项，同时返回被裁剪数量用于监控。
    """

    if top_n <= 0:
        return [], len(candidates)

    kept_candidates: list[_TreatmentCandidateProject] = []
    dropped_count = 0
    for quadrant in _TREATMENT_QUADRANT_TO_INDEX:
        quadrant_candidates = [item for item in candidates if item.quadrant == quadrant]
        if len(quadrant_candidates) <= top_n:
            kept_candidates.extend(quadrant_candidates)
            continue
        kept_candidates.extend(quadrant_candidates[:top_n])
        dropped_count += len(quadrant_candidates) - top_n
    return kept_candidates, dropped_count


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


def _merge_recommendation_defaults(bucket: dict[str, Any], defaults: list[str]) -> None:
    """合并默认推荐模板，避免覆盖前序计算阶段写入的业务推荐项。"""

    existing = _deduplicate_text_list(list(bucket.get("recommendationPlans") or []))
    merged = list(existing)
    existing_set = set(existing)
    for item in defaults:
        if item in existing_set:
            continue
        merged.append(item)
        existing_set.add(item)
    bucket["recommendationPlans"] = merged


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
                "q_code": str(item.get("q_code") or item.get("code") or ""),
                "q_name": str(item.get("q_name") or item.get("name") or ""),
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
