from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bi.meeting_bi.schemas.registration import MatrixRow, RegionLevelCount, RegistrationDetail


def get_region_level_chart(db: Session) -> list[RegionLevelCount]:
    rows = db.execute(
        text(
            """
            SELECT
              SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region,
              real_identity,
              COUNT(DISTINCT customer_unique_id) AS register_count,
              COUNT(DISTINCT CASE WHEN sign_in_status = '已签到' THEN customer_unique_id END) AS arrive_count
            FROM meeting_registration
            WHERE market_service_attribution IS NOT NULL
              AND real_identity IS NOT NULL
              AND real_identity NOT LIKE '%市场%'
              AND real_identity NOT LIKE '%陪同%'
            GROUP BY region, real_identity
            ORDER BY region
            """
        )
    ).mappings().all()
    return [RegionLevelCount(**r) for r in rows]


def get_matrix_table(db: Session) -> list[MatrixRow]:
    rows = db.execute(
        text(
            """
            SELECT
              SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region,
              SUM(CASE WHEN real_identity LIKE '%千万%' THEN 1 ELSE 0 END) AS qianwan_register,
              SUM(CASE WHEN real_identity LIKE '%千万%' AND sign_in_status = '已签到' THEN 1 ELSE 0 END) AS qianwan_arrive,
              SUM(CASE WHEN real_identity LIKE '%百万%' OR real_identity LIKE '%300万%' THEN 1 ELSE 0 END) AS baiwan_register,
              SUM(CASE WHEN (real_identity LIKE '%百万%' OR real_identity LIKE '%300万%') AND sign_in_status = '已签到' THEN 1 ELSE 0 END) AS baiwan_arrive,
              SUM(CASE WHEN real_identity IS NULL OR (real_identity NOT LIKE '%千万%' AND real_identity NOT LIKE '%百万%' AND real_identity NOT LIKE '%300万%') THEN 1 ELSE 0 END) AS putong_register,
              SUM(CASE WHEN (real_identity IS NULL OR (real_identity NOT LIKE '%千万%' AND real_identity NOT LIKE '%百万%' AND real_identity NOT LIKE '%300万%')) AND sign_in_status = '已签到' THEN 1 ELSE 0 END) AS putong_arrive,
              COUNT(DISTINCT customer_unique_id) AS total_register,
              COUNT(DISTINCT CASE WHEN sign_in_status = '已签到' THEN customer_unique_id END) AS total_arrive
            FROM meeting_registration
            WHERE market_service_attribution IS NOT NULL
              AND real_identity IS NOT NULL
              AND real_identity NOT LIKE '%市场%'
              AND real_identity NOT LIKE '%陪同%'
            GROUP BY region
            ORDER BY total_register DESC
            """
        )
    ).mappings().all()
    return [MatrixRow(**{k: int(v) if k != "region" else v for k, v in r.items()}) for r in rows]


def get_registration_detail(db: Session, region: str | None = None, level: str | None = None) -> list[RegistrationDetail]:
    conditions = ["market_service_attribution IS NOT NULL"]
    params: dict[str, str] = {}
    if region:
        conditions.append("SUBSTRING_INDEX(market_service_attribution, ',', 1) = :region")
        params["region"] = region
    if level:
        if level == "未分类":
            conditions.append("real_identity IS NULL")
        else:
            conditions.append("real_identity = :level")
            params["level"] = level

    where = " AND ".join(conditions)
    rows = db.execute(
        text(
            f"""
            SELECT
              customer_name,
              sign_in_status,
              customer_category,
              real_identity,
              attendee_role,
              store_name,
              SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region
            FROM meeting_registration
            WHERE {where}
            ORDER BY sign_in_status DESC, customer_name
            """
        ),
        params,
    ).mappings().all()
    return [RegistrationDetail(**r) for r in rows]
