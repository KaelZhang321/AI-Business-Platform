from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.bi.meeting_bi.db.dependencies import get_bi_db
from app.bi.meeting_bi.schemas.ai_query import MeetingBIQueryRequest, MeetingBIQueryResponse
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
def kpi_overview(db: Session = Depends(get_bi_db)):
    return get_kpi_overview(db)


@router.get("/bi/registration/chart", response_model=list[RegionLevelCount], tags=["会议BI"])
def registration_chart(db: Session = Depends(get_bi_db)):
    return get_region_level_chart(db)


@router.get("/bi/registration/matrix", response_model=list[MatrixRow], tags=["会议BI"])
def registration_matrix(db: Session = Depends(get_bi_db)):
    return get_matrix_table(db)


@router.get("/bi/registration/detail", response_model=list[RegistrationDetail], tags=["会议BI"])
def registration_detail(
    region: str | None = Query(None),
    level: str | None = Query(None),
    db: Session = Depends(get_bi_db),
):
    return get_registration_detail(db, region, level)


@router.get("/bi/customer/profile", response_model=CustomerProfile, tags=["会议BI"])
def customer_profile(db: Session = Depends(get_bi_db)):
    return get_customer_profile(db)


@router.get("/bi/source/distribution", response_model=list[SourceCount], tags=["会议BI"])
def source_distribution(db: Session = Depends(get_bi_db)):
    return get_source_distribution(db)


@router.get("/bi/source/target-arrival", response_model=list[TargetArrival], tags=["会议BI"])
def source_target_arrival(db: Session = Depends(get_bi_db)):
    return get_target_arrival(db)


@router.get("/bi/source/target-detail", response_model=list[TargetCustomerDetail], tags=["会议BI"])
def source_target_detail(region: str | None = Query(None), db: Session = Depends(get_bi_db)):
    return get_target_customer_detail(db, region)


@router.get("/bi/operations/kpi", response_model=OperationsKpi, tags=["会议BI"])
def operations_kpi(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_bi_db),
):
    return get_operations_kpi(db, date_from, date_to)


@router.get("/bi/operations/trend", response_model=list[TrendPoint], tags=["会议BI"])
def operations_trend(db: Session = Depends(get_bi_db)):
    return get_trend_data(db)


@router.get("/bi/achievement/chart", response_model=list[AchievementBar], tags=["会议BI"])
def achievement_chart(db: Session = Depends(get_bi_db)):
    return get_achievement_chart(db)


@router.get("/bi/achievement/table", response_model=list[AchievementRow], tags=["会议BI"])
def achievement_table(db: Session = Depends(get_bi_db)):
    return get_achievement_table(db)


@router.get("/bi/achievement/detail", response_model=list[AchievementDetail], tags=["会议BI"])
def achievement_detail(region: str | None = Query(None), db: Session = Depends(get_bi_db)):
    return get_achievement_detail(db, region)


@router.get("/bi/progress/ranking", response_model=ProgressSummary, tags=["会议BI"])
def progress_ranking(db: Session = Depends(get_bi_db)):
    return get_progress(db)


@router.get("/bi/proposal/overview", response_model=list[ProposalRow], tags=["会议BI"])
def proposal_overview(db: Session = Depends(get_bi_db)):
    return get_proposal_overview(db)


@router.get("/bi/proposal/detail", response_model=list[ProposalDetail], tags=["会议BI"])
def proposal_detail(
    region: str | None = Query(None),
    proposal_type: str | None = Query(None),
    db: Session = Depends(get_bi_db),
):
    return get_proposal_detail(db, region, proposal_type)


# ─────────────────────────────────────────────────────────────────────────────
# AI 问数路由
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/bi/ai/query", response_model=MeetingBIQueryResponse, tags=["会议BI-AI"])
async def bi_ai_query(req: MeetingBIQueryRequest):
    """自然语言问数（同步返回完整结果）。"""
    executor = MeetingBIQueryExecutor()
    result = await executor.query(req.question, conversation_id=req.conversation_id)
    return MeetingBIQueryResponse(
        sql=result.sql,
        answer=result.answer or "",
        columns=list(result.results[0].keys()) if result.results else [],
        rows=result.results,
        chart=result.chart_spec,
    )


@router.post("/bi/ai/query/stream", tags=["会议BI-AI"])
async def bi_ai_query_stream(req: MeetingBIQueryRequest):
    """自然语言问数（SSE 流式推送）。"""
    executor = MeetingBIQueryExecutor()
    return EventSourceResponse(
        executor.stream(req.question, conversation_id=req.conversation_id)
    )


@router.get("/bi/chart/{chart_id}", tags=["会议BI-AI"])
async def bi_get_chart(chart_id: str):
    """获取已缓存的图表配置（用于企微卡片跳转）。"""
    data = await get_chart(chart_id)
    if data is None:
        raise HTTPException(status_code=404, detail="图表不存在或已过期")
    return {"code": 0, "message": "ok", "data": data}
