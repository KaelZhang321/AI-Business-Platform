"""会议 BI 固定看板与 AI 问数路由。

该路由同时承载两类能力：
1. 固定指标 / 图表接口，供前端直接拉取稳定 BI 看板
2. 会议 BI 垂直问数接口，供自然语言转 SQL 使用
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

import aiomysql

from app.api.dependencies import get_business_mysql_pool
from app.bi.meeting_bi.schemas.ai_query import MeetingBIQueryRequest, MeetingBIQueryResponse
from app.bi.meeting_bi.schemas.common import BIChartConfig
from app.bi.meeting_bi.services.chart_store import get_chart

try:
    from app.bi.meeting_bi.ai.query_executor import MeetingBIQueryExecutor
except ImportError:  # pragma: no cover - openai/chromadb not installed in test env
    MeetingBIQueryExecutor = None  # type: ignore[assignment,misc]
from app.bi.meeting_bi.schemas.achievement import AchievementBar, AchievementDetail, AchievementRow
from app.bi.meeting_bi.schemas.customer import CustomerProfile
from app.bi.meeting_bi.schemas.kpi import KpiOverview
from app.bi.meeting_bi.schemas.operations import OperationsKpi, TrendPoint
from app.bi.meeting_bi.schemas.progress import ProgressSummary
from app.bi.meeting_bi.schemas.proposal import ProposalDetail, ProposalRow
from app.bi.meeting_bi.schemas.registration import MatrixRow, RegionLevelCount, RegistrationDetail
from app.bi.meeting_bi.schemas.source import SourceCount, TargetArrival, TargetCustomerDetail
from app.bi.meeting_bi.services.achievement_service import (
    get_achievement_chart,
    get_achievement_detail,
    get_achievement_table,
)
from app.bi.meeting_bi.services.customer_service import get_customer_profile
from app.bi.meeting_bi.services.kpi_service import get_kpi_overview
from app.bi.meeting_bi.services.operations_service import get_operations_kpi, get_trend_data
from app.bi.meeting_bi.services.progress_service import get_progress
from app.bi.meeting_bi.services.proposal_service import get_proposal_detail, get_proposal_overview
from app.bi.meeting_bi.services.registration_service import (
    get_matrix_table,
    get_region_level_chart,
    get_registration_detail,
)
from app.bi.meeting_bi.services.source_service import (
    get_source_distribution,
    get_target_arrival,
    get_target_customer_detail,
)

router = APIRouter()


@router.get("/bi/kpi/overview", response_model=KpiOverview, tags=["会议BI"])
async def kpi_overview(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_kpi_overview(db)


@router.get("/bi/registration/chart", response_model=list[RegionLevelCount], tags=["会议BI"])
async def registration_chart(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_region_level_chart(db)


@router.get("/bi/registration/matrix", response_model=list[MatrixRow], tags=["会议BI"])
async def registration_matrix(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_matrix_table(db)


@router.get("/bi/registration/detail", response_model=list[RegistrationDetail], tags=["会议BI"])
async def registration_detail(
    region: str | None = Query(None),
    level: str | None = Query(None),
    db: aiomysql.Pool = Depends(get_business_mysql_pool),
):
    return await get_registration_detail(db, region, level)


@router.get("/bi/customer/profile", response_model=CustomerProfile, tags=["会议BI"])
async def customer_profile(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_customer_profile(db)


@router.get("/bi/source/distribution", response_model=list[SourceCount], tags=["会议BI"])
async def source_distribution(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_source_distribution(db)


@router.get("/bi/source/target-arrival", response_model=list[TargetArrival], tags=["会议BI"])
async def source_target_arrival(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_target_arrival(db)


@router.get("/bi/source/target-detail", response_model=list[TargetCustomerDetail], tags=["会议BI"])
async def source_target_detail(region: str | None = Query(None), db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_target_customer_detail(db, region)


@router.get("/bi/operations/kpi", response_model=OperationsKpi, tags=["会议BI"])
async def operations_kpi(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: aiomysql.Pool = Depends(get_business_mysql_pool),
):
    return await get_operations_kpi(db, date_from, date_to)


@router.get("/bi/operations/trend", response_model=list[TrendPoint], tags=["会议BI"])
async def operations_trend(
    scene: str | None = Query(None),
    db: aiomysql.Pool = Depends(get_business_mysql_pool)
):
    return await get_trend_data(db, scene)


@router.get("/bi/achievement/chart", response_model=list[AchievementBar], tags=["会议BI"])
async def achievement_chart(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_achievement_chart(db)


@router.get("/bi/achievement/table", response_model=list[AchievementRow], tags=["会议BI"])
async def achievement_table(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_achievement_table(db)


@router.get("/bi/achievement/detail", response_model=list[AchievementDetail], tags=["会议BI"])
async def achievement_detail(region: str | None = Query(None), db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_achievement_detail(db, region)


@router.get("/bi/progress/ranking", response_model=ProgressSummary, tags=["会议BI"])
async def progress_ranking(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_progress(db)


@router.get("/bi/proposal/overview", response_model=list[ProposalRow], tags=["会议BI"])
async def proposal_overview(db: aiomysql.Pool = Depends(get_business_mysql_pool)):
    return await get_proposal_overview(db)


@router.get("/bi/proposal/detail", response_model=list[ProposalDetail], tags=["会议BI"])
async def proposal_detail(
    region: str | None = Query(None),
    proposal_type: str | None = Query(None),
    db: aiomysql.Pool = Depends(get_business_mysql_pool),
):
    return await get_proposal_detail(db, region, proposal_type)


# ─────────────────────────────────────────────────────────────────────────────
# AI 问数路由
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/bi/ai/query", response_model=MeetingBIQueryResponse, tags=["会议BI-AI"])
async def bi_ai_query(
    req: MeetingBIQueryRequest,
    db: aiomysql.Pool = Depends(get_business_mysql_pool),
):
    """执行会议 BI 自然语言问数并同步返回完整结果。"""
    if MeetingBIQueryExecutor is None:
        raise HTTPException(status_code=503, detail="Meeting BI AI executor unavailable")
    executor = MeetingBIQueryExecutor(pool=db)
    result = await executor.query(req.question, conversation_id=req.conversation_id)
    return MeetingBIQueryResponse(
        sql=result.sql,
        answer=result.answer or "",
        columns=list(result.results[0].keys()) if result.results else [],
        rows=result.results,
        chart=BIChartConfig(**result.chart_spec) if isinstance(result.chart_spec, dict) else result.chart_spec,
    )


@router.post("/bi/ai/query/stream", tags=["会议BI-AI"])
async def bi_ai_query_stream(
    req: MeetingBIQueryRequest,
    db: aiomysql.Pool = Depends(get_business_mysql_pool),
):
    """以 SSE 方式流式返回会议 BI 问数过程。"""
    if MeetingBIQueryExecutor is None:
        raise HTTPException(status_code=503, detail="Meeting BI AI executor unavailable")
    executor = MeetingBIQueryExecutor(pool=db)
    return EventSourceResponse(
        executor.stream(req.question, conversation_id=req.conversation_id)
    )


@router.get("/bi/chart/{chart_id}", tags=["会议BI-AI"])
async def bi_get_chart(chart_id: str):
    """获取缓存图表配置。

    功能：
        让图表型回答可以在企微卡片或外部跳转场景中通过 `chart_id` 二次拉取配置。
    """
    data = await get_chart(chart_id)
    if data is None:
        raise HTTPException(status_code=404, detail="图表不存在或已过期")
    return {"code": 0, "message": "ok", "data": data}
