import aiomysql

from app.bi.meeting_bi.schemas.customer import CustomerProfile, PieSlice


async def _fetch_all(pool: aiomysql.Pool, sql: str) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql)
            return await cur.fetchall() or []


async def get_customer_profile(pool: aiomysql.Pool) -> CustomerProfile:
    level_rows = await _fetch_all(
        pool,
        """
        SELECT real_identity AS name, COUNT(DISTINCT customer_unique_id) AS value
        FROM meeting_registration
        WHERE real_identity IS NOT NULL
          AND real_identity NOT LIKE '%市场%'
          AND real_identity NOT LIKE '%陪同%'
        GROUP BY name
        ORDER BY value DESC
        """,
    )
    total_level = sum(r["value"] for r in level_rows) or 1
    level_dist = [
        PieSlice(name=r["name"], value=int(r["value"]), percentage=round(int(r["value"]) / total_level * 100, 2))
        for r in level_rows
    ]

    role_rows = await _fetch_all(
        pool,
        """
        SELECT
          CASE
            WHEN (TRIM(real_identity) = '' OR real_identity IS NULL) THEN '未分类'
            WHEN real_identity LIKE '%陪同%' THEN '陪同'
            WHEN real_identity LIKE '%观摩%' THEN '观摩'
            WHEN real_identity LIKE '%市场%' THEN '市场'
            ELSE '客户'
          END AS name,
          COUNT(DISTINCT customer_unique_id) AS value
        FROM meeting_registration
        WHERE real_identity IS NOT NULL
        GROUP BY name
        ORDER BY value DESC
        """,
    )
    total_role = sum(r["value"] for r in role_rows) or 1
    role_dist = [
        PieSlice(name=r["name"], value=int(r["value"]), percentage=round(int(r["value"]) / total_role * 100, 2))
        for r in role_rows
    ]

    new_old_rows = await _fetch_all(
        pool,
        """
        SELECT
          IF(customer_category LIKE '%新%', '新客户', '老客户') AS name,
          COUNT(DISTINCT customer_unique_id) AS value
        FROM meeting_registration
        WHERE TRIM(customer_category) != ''
          AND customer_category IS NOT NULL
          AND (customer_category LIKE '%新%' OR customer_category LIKE '%老%')
        GROUP BY name
        ORDER BY value DESC
        """,
    )
    total_no = sum(r["value"] for r in new_old_rows) or 1
    new_old_dist = [
        PieSlice(name=r["name"], value=int(r["value"]), percentage=round(int(r["value"]) / total_no * 100, 2))
        for r in new_old_rows
    ]

    return CustomerProfile(
        level_distribution=level_dist,
        role_distribution=role_dist,
        new_old_distribution=new_old_dist,
    )
