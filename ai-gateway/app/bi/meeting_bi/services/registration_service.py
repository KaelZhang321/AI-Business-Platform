import aiomysql

from app.bi.meeting_bi.schemas.registration import MatrixRow, RegionLevelCount, RegistrationDetail


async def _fetch_all(pool: aiomysql.Pool, sql: str, params: dict[str, str] | None = None) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params or {})
            return await cur.fetchall() or []


async def get_region_level_chart(pool: aiomysql.Pool) -> list[RegionLevelCount]:
    rows = await _fetch_all(
        pool,
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
        """,
    )
    return [RegionLevelCount(**r) for r in rows]


async def get_matrix_table(pool: aiomysql.Pool) -> list[MatrixRow]:
    rows = await _fetch_all(
        pool,
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
        """,
    )
    return [MatrixRow(**{k: int(v) if k != "region" else v for k, v in r.items()}) for r in rows]


async def get_registration_detail(pool: aiomysql.Pool, region: str | None = None, level: str | None = None) -> list[RegistrationDetail]:
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
    rows = await _fetch_all(
        pool,
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
        """,
        params,
    )
    return [RegistrationDetail(**r) for r in rows]
