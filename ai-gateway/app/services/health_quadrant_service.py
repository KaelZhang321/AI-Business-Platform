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
from app.utils.text_utils import normalize_text_or_none as _normalize_text
from app.services.health_quadrant_llm_service import HealthQuadrantLLMService
from app.services.health_quadrant_mysql_pools import HealthQuadrantMySQLPools
from app.services.health_quadrant_repository import HealthQuadrantRepository
from app.services.health_quadrant_repository import HealthQuadrantRepositoryError
from app.services.health_quadrant_treatment_repository import (
    HealthQuadrantTreatmentRepository,
    HealthQuadrantTreatmentRepositoryError,
)

logger = logging.getLogger(__name__)

_EXAM_BUCKETS = [
    ("q1", "第一象限（基础筛查）"),
    ("q2", "第二象限（影像评估）"),
    ("q3", "第三象限（专项深度筛查）"),
    ("q4", "第四象限（丽滋特色项目）"),
]

_TREATMENT_BUCKETS = [
    ("q1", "红色高风险区（救命：医疗级干预）"),
    ("q2", "橙色较高风险区（治病：专项健康管理）"),
    ("q3", "蓝色一般风险区（防病：生活方式医学）"),
    ("q4", "绿色低风险区（抗衰：高端维养服务）"),
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
        return_text = ""
        if self.value_or_desc is None or len(self.value_or_desc.strip()) == 0 or self.value_or_desc in self.item_name:
            return_text = self.item_name
        else:
            return_text = f"{self.item_name}：{self.value_or_desc}"
        if re.search("^\d{1,2}分$", return_text):
            return_text = "人体成分评分：" + return_text
        return return_text


@dataclass(frozen=True)
class _TreatmentCandidateProject:
    """治疗知识库召回后的候选项目。"""

    candidate_id: str
    project_name: str
    quadrant: str
    belong_system: str
    core_effect: str
    indications: str
    contraindications: str


@dataclass(frozen=True)
class _TreatmentLLMResult:
    """治疗四象限单次 LLM 输出的标准化结果。"""

    triage_items: list[_TreatmentTriageItem]
    sorted_recommendations: dict[str, list[str]]
    triage_dropped: int
    dropped_by_missing_sorted_recommendations: int


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
        business_pool: aiomysql.Pool | None = None,
    ) -> None:
        self._repository = repository or HealthQuadrantRepository(pool=business_pool)
        # 健康四象限的终检意见抽取需要稳定结构化输出，默认优先走 Ark（ARK_DEFAULT_MODEL）。
        self._llm_service = llm_service or HealthQuadrantLLMService()
        self._mysql_pools = mysql_pools or HealthQuadrantMySQLPools(
            minsize=1,
            maxsize=3,
            business_pool=business_pool,
        )
        self._owns_mysql_pools = mysql_pools is None
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
                cached_quadrants = _normalize_quadrants_payload(cached)
                if _has_quadrant_cache_content(cached_quadrants):
                    logger.info(
                        "health quadrant query cache hit trace_id=%s study_id=%s quadrant_type=%s status=%s",
                        normalized_trace_id,
                        study_id,
                        quadrant_type,
                        cached_status,
                    )
                    return {"quadrants": cached_quadrants, "fromCache": True}
                logger.info(
                    "health quadrant query cache ignored trace_id=%s study_id=%s quadrant_type=%s status=%s reason=empty_quadrant_content",
                    normalized_trace_id,
                    study_id,
                    quadrant_type,
                    cached_status,
                )

            # 4) 缓存未命中时才进入实时计算分支，降低高并发下的跨库与 LLM 成本。
            compute_started_at = time.perf_counter()
            should_persist_draft = True
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
                quadrants, should_persist_draft = await self._build_treatment_quadrants(
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
            if should_persist_draft:
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
            else:
                logger.info(
                    "health quadrant skip draft persist trace_id=%s study_id=%s quadrant_type=%s reason=treatment_single_pass_fallback",
                    normalized_trace_id,
                    study_id,
                    quadrant_type,
                )
            return {"quadrants": quadrants, "fromCache": False}
        except HealthQuadrantServiceError:
            # 已是业务可解释错误，直接上抛给路由层做统一错误码映射。
            raise
        except HealthQuadrantRepositoryError as exc:
            logger.error(
                "health quadrant query repository failed trace_id=%s study_id=%s quadrant_type=%s error=%s",
                normalized_trace_id,
                study_id,
                quadrant_type,
                exc,
                exc_info=True,
            )
            raise HealthQuadrantServiceError("persist_failed: 四象限持久化访问失败") from exc
        except Exception as exc:
            logger.error(
                "health quadrant query unexpected failed trace_id=%s study_id=%s quadrant_type=%s error_type=%s error=%r",
                normalized_trace_id,
                study_id,
                quadrant_type,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise HealthQuadrantServiceError("query_failed: 四象限查询流程异常") from exc
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
        except HealthQuadrantServiceError:
            raise
        except HealthQuadrantRepositoryError as exc:
            logger.error(
                "health quadrant confirm repository failed trace_id=%s study_id=%s quadrant_type=%s error=%s",
                normalized_trace_id,
                study_id,
                quadrant_type,
                exc,
                exc_info=True,
            )
            raise HealthQuadrantServiceError("confirm_failed: 四象限确认持久化失败") from exc
        except Exception as exc:
            logger.error(
                "health quadrant confirm unexpected failed trace_id=%s study_id=%s quadrant_type=%s error_type=%s error=%r",
                normalized_trace_id,
                study_id,
                quadrant_type,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise HealthQuadrantServiceError("confirm_failed: 四象限确认流程异常") from exc
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

        # 逐资源独立保护，避免一个 close 失败导致后续资源泄漏。
        try:
            await self._repository.close()
        except Exception as exc:
            logger.warning("health quadrant close repository failed error=%s", exc, exc_info=True)

        try:
            await self._treatment_repository.close()
        except Exception as exc:
            logger.warning("health quadrant close treatment repository failed error=%s", exc, exc_info=True)

        if self._owns_mysql_pools:
            try:
                await self._mysql_pools.close()
            except Exception as exc:
                logger.warning("health quadrant close mysql pools failed error=%s", exc, exc_info=True)

        if self._dw_http_client is not None:
            try:
                await self._dw_http_client.aclose()
            except Exception as exc:
                logger.warning("health quadrant close dw http client failed error=%s", exc, exc_info=True)
            finally:
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

        try:
            buckets = _empty_buckets(_EXAM_BUCKETS)
            # 1) 基于分拆表先构建第一、二象限：这是“体检事实数据”最稳定的来源。
            q1_q2_started_at = time.perf_counter()
            for row in source.get("splitRows", []):
                one_item = _normalize_text(row.get("one_item_name"))
                two_item = _normalize_text(row.get("two_item_name"))
                abnormal_item = _normalize_text(row.get("abnormal_item"))
                if re.search("^\d{1, 2}分$", abnormal_item) or re.search("人体成[份分]", one_item):
                    abnormal_item = "人体成份检查：" + abnormal_item
                category = _normalize_text(row.get("category_name"))
                if not abnormal_item:
                    continue

                # 1. 非影像异常归第一象限；影像异常归第二象限，符合“1+X”基础筛查语义。
                if one_item and category != '影像类':
                    buckets[0]["abnormal_indicators"].append(abnormal_item)
                    buckets[0]["recommendation_plans"].append(one_item)
                if two_item or (one_item and category == '影像类'):
                    imaging_name = two_item or one_item or ""
                    buckets[1]["abnormal_indicators"].append(abnormal_item)
                    buckets[1]["recommendation_plans"].append(imaging_name)

            # 对第一、二象限的推荐方案去重
            buckets[0]["recommendation_plans"] = list(_build_exam_dedup_keys(buckets[0]["recommendation_plans"]))
            buckets[1]["recommendation_plans"] = list(_build_exam_dedup_keys(buckets[1]["recommendation_plans"]))
            logger.info(
                "health quadrant stage duration stage=service.exam.q1_q2_build duration_ms=%s trace_id=%s study_id=%s",
                int((time.perf_counter() - q1_q2_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
            )

            # 2) 先建立 Q1/Q2 去重基线：后续 Q3/Q4 只补“新增价值项”，避免重复展示。
            existing_exam_keys = _build_exam_dedup_keys(
                buckets[0]["recommendation_plans"] + buckets[1]["recommendation_plans"]
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
                buckets[2]["recommendation_plans"].extend(q3_items)

            # 单项体检是结构化人工补充输入：项目名进入 recommendation_plans，异常描述进入 abnormal_indicators。
            single_plan_seen: set[str] = set()
            for item in single_exam_items:
                item_text = _normalize_text(item.get("itemText"))
                if not item_text:
                    continue
                item_key = _normalize_exam_name_for_key(item_text)
                if not item_key or item_key in existing_exam_keys or item_key in single_plan_seen:
                    continue
                single_plan_seen.add(item_key)
                buckets[2]["recommendation_plans"].append(item_text)

                abnormal_indicator = _normalize_text(item.get("abnormalIndicator"))
                if abnormal_indicator:
                    buckets[2]["abnormal_indicators"].append(abnormal_indicator)
            if single_plan_seen:
                existing_exam_keys.update(single_plan_seen)
            logger.info(
                "health quadrant stage duration stage=service.exam.q3_merge duration_ms=%s trace_id=%s study_id=%s q3_plan_count=%s single_plan_count=%s",
                int((time.perf_counter() - q3_merge_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
                len(buckets[2]["recommendation_plans"]),
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
                buckets[3]["abnormal_indicators"].extend(chief_complaint_items)
                buckets[3]["recommendation_plans"].extend(q4_items)
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
            _finalize_exam_recommendations(chief_complaint_items, buckets)
            logger.info(
                "health quadrant stage duration stage=service.exam.finalize duration_ms=%s trace_id=%s study_id=%s",
                int((time.perf_counter() - finalize_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
            )
            return buckets
        finally:
            logger.info(
                "health quadrant stage duration stage=service.exam.total duration_ms=%s trace_id=%s study_id=%s",
                int((time.perf_counter() - total_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
            )

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
    ) -> tuple[list[dict[str, Any]], bool]:
        """构建治疗四象限。

        功能：
            治疗链路改为“单次 LLM”：
            1) 先从 MySQL 读取全量 active 项目池并拼装 `project_name(版本)`
            2) 单次 LLM 输出 triage+safety+sorted_recommendations
            3) 服务端按 RED->ORANGE->BLUE->GREEN 执行 Top3 与跨象限去重

        Args:
            source: 聚合后的源数据。
            single_exam_items: 前端补充单项体检条目。
            chief_complaint_text: 前端补充主诉。
            study_id: 体检主单号，仅用于日志追踪。
            trace_id: 链路追踪 ID。

        Returns:
            `(buckets, should_persist_draft)`。
            当模型两次失败或输出非法时返回空推荐，且 `should_persist_draft=False`，
            防止降级结果污染 DRAFT 缓存。

        Edge Cases:
            1. 单次 LLM 失败会自动重试 1 次；仍失败降级空推荐。
            2. 安全过滤后无项目时，仍返回完整四象限结构，保证前端契约稳定。
        """
        total_started_at = time.perf_counter()
        normalized_trace_id = trace_id or "-"
        normalized_study_id = study_id or "-"

        try:
            # 1) 输入归一化：先统一异常指标文本，保证签名稳定且便于日志审计。
            normalize_started_at = time.perf_counter()
            abnormal_items_text = _build_treatment_triage_inputs(
                jcjg=source.get("jcjg") or "",
                single_exam_items=single_exam_items
            )
            logger.info(
                "health quadrant stage duration stage=service.treatment.normalize duration_ms=%s trace_id=%s study_id=%s in_count=%s",
                int((time.perf_counter() - normalize_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
                len([line for line in abnormal_items_text.splitlines() if line.strip()]),
            )
            if not _normalize_text(abnormal_items_text):
                buckets = _empty_buckets(_TREATMENT_BUCKETS)
                _finalize_treatment_recommendations(buckets)
                return buckets, True

            # 2) 读取全量 active 项目池（不截断），由单次 LLM 做统一分诊与安全判定。
            candidate_started_at = time.perf_counter()
            candidates = await self._match_treatment_candidates(
                trace_id=normalized_trace_id,
                study_id=normalized_study_id,
            )
            logger.info(
                "health quadrant stage duration stage=service.treatment.load_candidates duration_ms=%s trace_id=%s study_id=%s out_count=%s",
                int((time.perf_counter() - candidate_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
                len(candidates),
            )
            if not candidates:
                buckets = _build_treatment_quadrant_buckets(
                    triage_items=[],
                    selected_recommendations_by_quadrant={quadrant: [] for quadrant in _TREATMENT_QUADRANT_TO_INDEX},
                    fallback_message="当前系统暂无可匹配的治疗项目",
                )
                _finalize_treatment_recommendations(buckets)
                return buckets, True

            # 3) 单次 LLM：输出 triage/safety/sorted_recommendations，并在服务端做强校验与归一化。
            llm_started_at = time.perf_counter()
            llm_result = await self._single_pass_treatment_llm_with_retry(
                sex=sex,
                age=age,
                abnormal_items_text=abnormal_items_text,
                chief_complaint_text=chief_complaint_text,
                candidates=candidates,
                trace_id=normalized_trace_id,
                study_id=normalized_study_id,
            )
            logger.info(
                "health quadrant stage duration stage=service.treatment.single_llm duration_ms=%s trace_id=%s study_id=%s triage_count=%s safe_count=%s",
                int((time.perf_counter() - llm_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
                len(llm_result.triage_items),
                len(llm_result.sorted_recommendations),
            )

            # 3.1) 模型失败降级：保持返回结构稳定，但不写入草稿，防止缓存污染。
            if llm_result is None:
                buckets = _build_treatment_quadrant_buckets(
                    triage_items=[],
                    selected_recommendations_by_quadrant={quadrant: [] for quadrant in _TREATMENT_QUADRANT_TO_INDEX},
                    fallback_message="本次智能分析未完成，请稍后重试",
                )
                _finalize_treatment_recommendations(buckets)
                return buckets, False

            # 4) 服务端后处理：先每象限 TopK，再 RED->GREEN 跨象限去重并再次 TopK。
            post_started_at = time.perf_counter()
            selected_recommendations_by_quadrant = _select_recommendations_from_single_pass_result(
                candidates=candidates,
                sorted_recommendations=llm_result.sorted_recommendations,
                top_k=5
            )
            logger.info(
                "health quadrant stage duration stage=service.treatment.post_process duration_ms=%s trace_id=%s study_id=%s",
                int((time.perf_counter() - post_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id
            )

            # 5) 装填响应：异常指标来自 triage，推荐方案来自单次 LLM + 服务端后处理。
            fill_started_at = time.perf_counter()
            buckets = _build_treatment_quadrant_buckets(
                triage_items=llm_result.triage_items,
                selected_recommendations_by_quadrant=selected_recommendations_by_quadrant,
            )
            _finalize_treatment_recommendations(buckets)
            logger.info(
                "health quadrant stage duration stage=service.treatment.fill duration_ms=%s trace_id=%s study_id=%s quadrant_count=%s",
                int((time.perf_counter() - fill_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
                len(buckets),
            )
            return buckets, True
        finally:
            logger.info(
                "health quadrant stage duration stage=service.treatment.total duration_ms=%s trace_id=%s study_id=%s",
                int((time.perf_counter() - total_started_at) * 1000),
                normalized_trace_id,
                normalized_study_id,
            )

    async def _match_treatment_candidates(
        self,
        *,
        trace_id: str,
        study_id: str,
    ) -> list[_TreatmentCandidateProject]:
        """按 triage 结果执行知识库召回（Match）。

        功能：
            单次 LLM 方案下，Match 阶段不再按 triage 条目召回，而是直接加载全量 active 项目池，
            由模型统一做“分诊+安全+排序”。这样能避免多阶段模型漂移导致的链路不一致。

        Args:
            trace_id: 链路追踪 ID。
            study_id: 体检主单号。

        Returns:
            按候选排序规则稳定输出的候选项目列表。

        Raises:
            HealthQuadrantServiceError: 当仓储查询失败时抛出。
        """

        try:
            rows = await self._treatment_repository.match_candidates(triage_items=[])
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
        seen: set[str] = set()
        for row in rows:
            project_name = _normalize_text(row.get("project_name"))
            package_version = _normalize_text(row.get("package_version")) or ""
            belong_system = _normalize_text(row.get("belong_system")) or ""
            if not project_name or not package_version:
                continue
            dedupe_key = "-".join([project_name, package_version])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            candidate_id = dedupe_key
            candidates.append(
                _TreatmentCandidateProject(
                    candidate_id=candidate_id,
                    # 只在这里把 package_version 融入展示名，后续流程不再单独传递该字段。
                    project_name=dedupe_key,
                    quadrant="",
                    belong_system=belong_system,
                    core_effect=_normalize_text(row.get("core_effect")) or "",
                    indications=_normalize_text(row.get("indications")) or "",
                    contraindications=_normalize_text(row.get("contraindications")) or "",
                )
            )
        candidates.sort(key=lambda item: item.project_name)
        return candidates

    async def _single_pass_treatment_llm_with_retry(
        self,
        *,
        sex: str,
        age: int | None,
        abnormal_items_text: str,
        candidates: list[_TreatmentCandidateProject],
        chief_complaint_text: str | None,
        trace_id: str,
        study_id: str,
    ) -> _TreatmentLLMResult | None:
        """执行治疗四象限单次 LLM，并在失败时自动重试 1 次。

        功能：
            按“最多两次”策略执行模型调用：首次失败或输出不合法时自动重试一次；
            若仍失败返回 `None`，由上层降级为空推荐且不写入 DRAFT。
        """

        for attempt in range(2):
            attempt_started_at = time.perf_counter()
            try:
                llm_result = await self._single_pass_treatment_llm_once(
                    sex=sex,
                    age=age,
                    abnormal_items_text=abnormal_items_text,
                    candidates=candidates,
                    chief_complaint_text=chief_complaint_text,
                    trace_id=trace_id,
                    study_id=study_id,
                )
                logger.info(
                    "health quadrant treatment single llm success trace_id=%s study_id=%s attempt=%s duration_ms=%s",
                    trace_id,
                    study_id,
                    attempt + 1,
                    int((time.perf_counter() - attempt_started_at) * 1000),
                )
                return llm_result
            except HealthQuadrantServiceError as exc:
                logger.warning(
                    "health quadrant treatment single llm failed trace_id=%s study_id=%s attempt=%s error=%s",
                    trace_id,
                    study_id,
                    attempt + 1,
                    exc,
                )
                if attempt == 1:
                    return None
        return None

    async def _single_pass_treatment_llm_once(
        self,
        *,
        sex: str,
        age: int | None,
        abnormal_items_text: str,
        candidates: list[_TreatmentCandidateProject],
        chief_complaint_text: str | None,
        trace_id: str,
        study_id: str,
    ) -> _TreatmentLLMResult:
        """执行一次单次 LLM 调用并做结构化解析。

        功能：
            统一使用一个提示词让模型输出 triage+safety+sorted_recommendations，
            然后在服务端按严格规则解析，避免模型输出漂移直接污染业务结果。
        """

        prompt = _build_treatment_single_pass_prompt(
            sex=sex,
            age=age,
            abnormal_items_text=abnormal_items_text,
            chief_complaint_text=chief_complaint_text,
            candidates=candidates,
        )
        llm_started_at = time.perf_counter()
        try:
            raw = await self._llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout_seconds=360.0,
            )
        except Exception as exc:
            logger.error(
                "health quadrant treatment single llm request failed trace_id=%s study_id=%s error_type=%s error=%r",
                trace_id,
                study_id,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise HealthQuadrantServiceError("single_llm_failed: 模型调用失败") from exc
        logger.info(
            "health quadrant stage duration stage=service.treatment.single_llm_request duration_ms=%s trace_id=%s study_id=%s candidate_count=%s",
            int((time.perf_counter() - llm_started_at) * 1000),
            trace_id,
            study_id,
            len(candidates),
        )

        parsed = json_loads_safe(raw)
        if not isinstance(parsed, dict):
            raise HealthQuadrantServiceError("single_llm_failed: 模型返回非 JSON 对象")

        triage_rows = _extract_treatment_triage_rows(parsed)
        sorted_recommendations_raw = parsed.get("sorted_recommendations")
        if not isinstance(triage_rows, list) or not isinstance(sorted_recommendations_raw, dict):
            logger.error(
                "health quadrant treatment single llm payload invalid trace_id=%s study_id=%s payload_keys=%s",
                trace_id,
                study_id,
                list(parsed.keys()),
            )
            raise HealthQuadrantServiceError("single_llm_failed: triage/safety/sorted_recommendations 结构非法")

        triage_items_map: dict[str, _TreatmentTriageItem] = {}
        triage_dropped = 0
        for row in triage_rows:
            item = _parse_treatment_triage_row(row)
            if item is None:
                triage_dropped += 1
                continue
            existed = triage_items_map.get(item.dedupe_key)
            if existed is None:
                triage_items_map[item.dedupe_key] = item
                continue
            if _TREATMENT_QUADRANT_PRIORITY[item.quadrant] < _TREATMENT_QUADRANT_PRIORITY[existed.quadrant]:
                triage_items_map[item.dedupe_key] = item

        sorted_recommendations: dict[str, list[str]] = {}
        dropped_by_missing_sorted_recommendations = 0
        for quadrant in _TREATMENT_QUADRANT_TO_INDEX:
            rows = sorted_recommendations_raw.get(quadrant)
            if not isinstance(rows, list):
                dropped_by_missing_sorted_recommendations += 1
                sorted_recommendations[quadrant] = []
                continue
            sorted_recommendations[quadrant] = []
            seen: set[str] = set()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                project_name = _normalize_text(row.get("project_name"))
                if not project_name or project_name in seen:
                    continue
                seen.add(project_name)
                sorted_recommendations[quadrant].append(project_name)

        return _TreatmentLLMResult(
            triage_items=list(triage_items_map.values()),
            sorted_recommendations=sorted_recommendations,
            triage_dropped=triage_dropped,
            dropped_by_missing_sorted_recommendations=dropped_by_missing_sorted_recommendations,
        )

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
            "abnormal_indicators": [],
            "recommendation_plans": [],
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


def _finalize_exam_recommendations(chief_complaint_items: list, buckets: list[dict[str, Any]]) -> None:
    # 规则解释：保留前序链路已经写入的个性化推荐项，再补默认推荐模板，避免覆盖业务输入。
    if len(chief_complaint_items) > 0:
        _merge_recommendation_defaults(buckets[3], ["全基因检测"])
    for bucket in buckets:
        bucket["abnormal_indicators"] = _deduplicate_text_list(bucket["abnormal_indicators"])


def _finalize_treatment_recommendations(buckets: list[dict[str, Any]]) -> None:
    for bucket in buckets:
        bucket["abnormal_indicators"] = _deduplicate_text_list(bucket["abnormal_indicators"])
        bucket["recommendation_plans"] = _deduplicate_text_list(bucket["recommendation_plans"])


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
    return "\n\n".join(merged)


def _build_treatment_single_pass_prompt(
    *,
    sex: str,
    age: int | None,
    abnormal_items_text: str,
    chief_complaint_text: str | None,
    candidates: list[_TreatmentCandidateProject],
) -> str:
    """构建治疗四象限单次 LLM Prompt。"""

    complaints = _normalize_text(chief_complaint_text) or "无主诉"
    candidate_payload = [
        {
            "project_name": item.project_name,
            "system_name": item.belong_system,
            "core_effect": item.core_effect,
            "indications": item.indications,
            "contraindications": item.contraindications,
        }
        for item in candidates
    ]
    candidate_payload = sorted(candidate_payload, key=lambda x: x['project_name'])

    return f"""
        # 角色设定
        你是一个全球顶级的临床决策支持系统（CDSS）大脑。你集成了“资深分诊专家”、“严苛安全风控官”和“临床路径优化师”三重身份。你的任务是输入患者的完整体检与病史数据以及项目产品库，经过严密的逻辑推导，一次性输出绝对安全、精准匹配且严格排序的【治疗四象限干预方案】。

        # 核心执行步骤与规则（必须严格按顺序执行）

        ### 第一阶段：患者状态评估与分诊（Triage）
        仔细分析患者的【异常检查指标】和【主诉/症状】，将每一项独立的异常指标映射到对应的医学系统和风险象限，不要遗漏异常指标。
        1. **风险象限标准（取高原则）**：
           - 【RED】红色高风险区（急治/救命）：危急重症、即刻心脑血管意外风险、急性靶器官损伤或疑似恶性肿瘤。
           - 【ORANGE】橙色较高风险区（干预/治病）：疾病持续进展期、明显异常（如重度代谢异常、明显结节）、需专项重点干预。
           - 【BLUE】蓝色一般风险区（调整/防病）：临界异常、亚健康、轻度失调，需生活方式或功能调理。
           - 【GREEN】绿色低风险区（维养/抗衰）：无明显病理性异常，健康巩固与主动抗衰。
        2. **医学系统归属**：必须从以下列表中选择（消化系统、呼吸系统、内分泌系统、心脑血管、泌尿生殖、骨骼运动、神经系统、免疫系统、专科项目）。
        3. **禁止臆测**：仅基于输入数据评级，每一项异常独立生成记录。
        4. 原子化拆分（绝对禁止合并打包）：必须将输入中的每一项独立异常指标严格拆分为单独的记录！
        - ❌ 严禁合并：绝不允许使用“及”、“和”、“综合征”或“等多项”进行概括组合。
        - ✅ 正确拆分：心电图若有3个具体异常，必须输出3条独立对象；食物不耐受若有11项，必须逐一输出11条独立对象（如：“麦芽特异性IgG抗体1级”、“小米特异性IgG抗体1级”），绝不能输出“多项食物不耐受”。
        5. 字段精简与去重（绝对禁止语义重复）：当提取影像学、心电图等【定性结论】（如“左室舒张功能改变”、“V1呈rSr'型”）时，如果名称本身已经完整表达了异常情况，请将其填入 `item_name`，并将 `value_or_desc` 严格置为空字符串 `""`。
        - ❌ 错误做法：`item_name`: "V1呈rSr'型", `value_or_desc`: "V1呈rSr'型"（导致重复拼凑）
        - ✅ 正确做法（定性）：`item_name`: "心电图V1呈rSr'型", `value_or_desc`: ""
        - ✅ 正确做法（定量）：`item_name`: "二尖瓣反流", `value_or_desc`: "微量"

        ### 第二阶段：禁忌症安全审查（Safety Gatekeeper）
        以“生命至上，宁错杀不放过”为绝对底线，对【候选项目池】中的每一个项目进行独立审查。
        1. **语义包含与同义穿透**：识别口语化病史（如患者说“放过支架”，必须触发生理/器械等隐性禁忌症）。
        2. **就高不就低**：只要患者的病史/症状疑似触碰该项目的禁忌症，或无法 100% 确认安全，必须判定为“拦截（is_contraindicated: true）”。

        ### 第三阶段：精准匹配与顺位排序（Pathway Optimization）
        结合第一阶段的分诊象限和第二阶段的安全结果，将**绝对安全（未被拦截）**的项目装填到对应的象限中，并严格按以下优先级（Tier）降序排列：
        - **绝对安全底线**：被判定为 `is_contraindicated: true` 的项目，绝对禁止出现在最终推荐列表中！
        - **匹配与顺位规则（降序排列）**：
          1. **第一顺位（核心首选）**：其适应症/功效**高度靶向**患者【当前最急迫主诉】或【该象限最危急指标】。
          2. **第二顺位（常规优选）**：对应常规异常指标，非最急迫诉求。
          3. **第三顺位（对症备选）**：能较好改善患者主诉症状。
        - **完整输出**：完成排序后，输出每个象限内**所有**符合条件的安全项目，不做数量截断。若该象限无安全匹配项目，输出空列表 `[]`。

        # 输出格式限制
        必须输出纯 JSON 格式，严格遵循以下结构（禁止包含 Markdown 标签或额外说明）：
        {{
          "triage_results": [
            {{
              "item_name": "提炼核心指标或症状名称（如：'二尖瓣反流'、'心电图碎裂QRS波'）",
              "value_or_desc": "具体的数值、程度或描述（如：'微量'、'53次/分'）。若 item_name 已完整表达，此项必须留空 \"\"，严禁与 item_name 语义重复！",
              "quadrant": "RED / ORANGE / BLUE / GREEN",
              "belong_system": "归属医学系统"
            }}
          ],
          "sorted_recommendations": {{
            "RED": [
              {{
                 "project_name": "项目名称",
                 "tier": "第一顺位 / 第二顺位 / 第三顺位",
                 "recommendation_reason": "结合主诉、分诊结果和核心功效，给出顺位判定及推荐理由（限50字）"
              }}
            ],
            "ORANGE": [],
            "BLUE": [],
            "GREEN": []
          }}
        }}

        # 待处理数据输入区：
        【患者基础画像】：
        - 性别：{sex}
        - 年龄：{age if age is not None else "未知"}岁

        【当前体检异常指标】：
        {abnormal_items_text}

        【患者当次主诉/症状】：
        {complaints}

        【系统候选项目池】（请严格按照以下字段定义理解项目属性）：
        - `project_name`: 项目名称-版本
        - `system_name`：所属医学系统
        - `core_effect`: 核心功效（用于评估项目价值）
        - `indications`: 适应症（用于评估匹配度与对症情况）
        - `contraindications`: 禁忌症（执行安全拦截的唯一依据，极其重要！）

        候选池 JSON 数据：
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
    if not item_name or not quadrant or not belong_system:
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


def _extract_treatment_triage_rows(payload: dict[str, Any]) -> list[Any] | None:
    """兼容多种 LLM 顶层键名，提取 triage 结果数组。

    功能：
        不同模型后端或提示词漂移时，常见会把 `triage_results` 输出成
        `triageResults` / `items`，或包在一层 `data` 下。这里做轻量兼容，
        只接受“列表”作为最终结果，避免误把字符串等非法值当作有效输入。
    """

    preferred_keys = ("triage_results", "triageResults", "items", "results")
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    # 部分模型会额外包一层 data/result；只做一层解包，避免过度宽松引入误判。
    nested_container = payload.get("data")
    if not isinstance(nested_container, dict):
        nested_container = payload.get("result")
    if isinstance(nested_container, dict):
        for key in preferred_keys:
            value = nested_container.get(key)
            if isinstance(value, list):
                return value
    return None


def _parse_treatment_safety_row(raw: Any) -> tuple[str | None, bool] | None:
    """解析单条 safety 结果，兼容 candidate_id 与 project_name 双键回填。"""

    if not isinstance(raw, dict):
        return None
    project_name = _normalize_text(raw.get("project_name"))
    is_contraindicated = raw.get("is_contraindicated")
    if not isinstance(is_contraindicated, bool):
        return None
    return project_name, is_contraindicated


def _build_treatment_quadrant_buckets_from_triage(
    *,
    triage_items: list[_TreatmentTriageItem],
) -> list[dict[str, Any]]:
    """仅根据 triage 结果构建四象限骨架。"""

    buckets = _empty_buckets(_TREATMENT_BUCKETS)
    for item in triage_items:
        bucket = buckets[_TREATMENT_QUADRANT_TO_INDEX[item.quadrant]]
        bucket["abnormal_indicators"].append(item.dedupe_key)
    return buckets


def _build_treatment_quadrant_buckets(
    *,
    triage_items: list[_TreatmentTriageItem],
    selected_recommendations_by_quadrant: dict[str, list[str]],
    fallback_message: str | None = None,
) -> list[dict[str, Any]]:
    """将 triage 与后处理后的推荐项目装填为四象限结果。"""

    buckets = _build_treatment_quadrant_buckets_from_triage(triage_items=triage_items)
    for quadrant, bucket_index in _TREATMENT_QUADRANT_TO_INDEX.items():
        bucket = buckets[bucket_index]
        for project_name in selected_recommendations_by_quadrant.get(quadrant, []):
            if project_name:
                bucket["recommendation_plans"].append(project_name)
    if not any(bucket["recommendation_plans"] for bucket in buckets):
        buckets[-1]["abnormal_indicators"].append(_normalize_text(fallback_message) or _TREATMENT_EMPTY_MESSAGE)
    return buckets


def _select_recommendations_from_single_pass_result(
    *,
    candidates: list[_TreatmentCandidateProject],
    sorted_recommendations: dict[str, list[str]],
    top_k: int = 3
) -> tuple[dict[str, list[str]], int]:
    """将单次 LLM 输出收敛为可直接装填的四象限推荐结果。

    功能：
        1) 每象限先按模型顺序取 Top3；
        2) 再按 RED->ORANGE->BLUE->GREEN 执行跨象限去重并再次 Top3。
    """

    # 1) 象限内 TopK：先按照模型排序结果过滤并截断。
    by_quadrant_topK: dict[str, list[str]] = {}
    for quadrant in _TREATMENT_QUADRANT_TO_INDEX:
        ranked_names = sorted_recommendations.get(quadrant, [])
        deduped_ranked_names: list[str] = []
        seen: set[str] = set()
        for name in ranked_names:
            normalized_name = _normalize_text(name)
            if not normalized_name or normalized_name in seen:
                continue
            seen.add(normalized_name)
            deduped_ranked_names.append(normalized_name)
        by_quadrant_topK[quadrant] = deduped_ranked_names[:top_k]

    # 2) 跨象限去重：高优先象限先占位，后续象限先去重再取 Top3。
    selected: set[str] = set()
    result: dict[str, list[str]] = {}
    for quadrant in _TREATMENT_QUADRANT_TO_INDEX:
        final_names: list[str] = []
        for name in by_quadrant_topK.get(quadrant, []):
            if name in selected:
                continue
            selected.add(name)
            final_names.append(name)
        result[quadrant] = final_names[:top_k]
    return result


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

    existing = _deduplicate_text_list(list(bucket.get("recommendation_plans") or []))
    merged = list(existing)
    existing_set = set(existing)
    for item in defaults:
        if item in existing_set:
            continue
        merged.append(item)
        existing_set.add(item)
    bucket["recommendation_plans"] = merged


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
                "abnormal_indicators": _deduplicate_text_list(list(item.get("abnormal_indicators") or [])),
                "recommendation_plans": _deduplicate_text_list(list(item.get("recommendation_plans") or [])),
            }
        )
    return normalized


def _has_quadrant_cache_content(quadrants: list[dict[str, Any]]) -> bool:
    """缓存四象限至少包含一条异常指标或推荐方案时才算业务命中。"""

    return any(
        bool(quadrant.get("abnormal_indicators")) or bool(quadrant.get("recommendation_plans"))
        for quadrant in quadrants
    )


def json_loads_safe(raw: str) -> dict[str, Any] | list[Any] | None:
    """安全解析 JSON 字符串。"""

    try:
        return json.loads(raw)
    except Exception:
        return None
