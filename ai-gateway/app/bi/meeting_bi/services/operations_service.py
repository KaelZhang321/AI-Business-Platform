from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bi.meeting_bi.schemas.operations import OperationsKpi, TrendPoint


def _sum_people_count(db: Session, condition_sql: str, params: dict[str, str]) -> int:
    row = db.execute(
        text(f"SELECT COALESCE(SUM(people_count), 0) AS cnt FROM meeting_schedule_stats WHERE {condition_sql}"),
        params,
    ).mappings().first()
    return int(row["cnt"] or 0)


def get_operations_kpi(db: Session, date_from: str | None = None, date_to: str | None = None) -> OperationsKpi:
    params: dict[str, str] = {}
    date_clause = ""
    if date_from and date_to:
        date_clause = " AND schedule_date BETWEEN :date_from AND :date_to"
        params.update({"date_from": date_from, "date_to": date_to})

    return OperationsKpi(
        checkin_count=_sum_people_count(db, f"time_period = '实际签到人数'{date_clause}", params),
        pickup_count=_sum_people_count(db, f"time_period = '当日接机人数'{date_clause}", params),
        leave_count=_sum_people_count(db, f"time_period = '离开人数'{date_clause}", params),
        hospital_count=_sum_people_count(db, f"time_period LIKE '%医院%'{date_clause}", params),
    )


def get_trend_data(db: Session) -> list[TrendPoint]:
    rows = db.execute(
        text(
            """
            SELECT
              schedule_date,
              CASE
                WHEN time_period LIKE '%上午%' THEN '上午'
                WHEN time_period LIKE '%下午%' THEN '下午'
                WHEN time_period LIKE '%午餐%' THEN '中午'
                WHEN time_period LIKE '%晚餐%' THEN '晚上'
                WHEN time_period LIKE '%晚上%' THEN '晚上'
                ELSE '全天'
              END AS day_time_period,
              CASE
                WHEN time_period LIKE '%参加会议%' THEN '参会'
                WHEN time_period LIKE '%签到%' THEN '抵达'
                WHEN time_period LIKE '%离开%' THEN '离开'
                WHEN time_period LIKE '%午餐%' THEN '用餐'
                WHEN time_period LIKE '%晚餐%' THEN '用餐'
                WHEN time_period LIKE '%医院%' THEN '到院'
                ELSE '其他'
              END AS scene_label,
              SUM(people_count) AS people_count
            FROM meeting_schedule_stats
            WHERE time_period NOT LIKE '%率%'
              AND time_period NOT LIKE '%占比%'
            GROUP BY schedule_date, day_time_period, scene_label
            HAVING scene_label != '其他'
            ORDER BY schedule_date, day_time_period
            """
        )
    ).mappings().all()
    return [TrendPoint(schedule_date=str(r["schedule_date"]), day_time_period=r["day_time_period"], scene_label=r["scene_label"], people_count=int(r["people_count"])) for r in rows]
