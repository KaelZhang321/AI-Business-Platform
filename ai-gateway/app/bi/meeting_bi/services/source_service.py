import aiomysql

from app.bi.meeting_bi.schemas.source import SourceCount, TargetArrival, TargetCustomerDetail


async def _fetch_all(pool: aiomysql.Pool, sql: str, params: dict[str, str] | None = None) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params or {})
            return await cur.fetchall() or []


async def get_source_distribution(pool: aiomysql.Pool) -> list[SourceCount]:
    rows = await _fetch_all(
        pool,
        """
        SELECT
          SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region,
          CASE
            WHEN store_name LIKE '%盟主%' THEN '盟主'
            WHEN store_name LIKE '%商务%' THEN '商务'
            ELSE '店铺'
          END AS source_type,
          COUNT(DISTINCT customer_unique_id) AS customer_count
        FROM meeting_registration
        WHERE market_service_attribution IS NOT NULL
          AND store_name IS NOT NULL
        GROUP BY region, source_type
        ORDER BY region, customer_count DESC
        """,
    )
    return [SourceCount(**r) for r in rows]


async def get_target_arrival(pool: aiomysql.Pool) -> list[TargetArrival]:
    target_rows = await _fetch_all(
        pool,
        """
        SELECT region, COUNT(DISTINCT customer_unique_id) AS target_count
        FROM meeting_customer_analysis
        WHERE min_deal >= 100
          AND region IS NOT NULL
        GROUP BY region
        """,
    )
    targets = {r["region"]: int(r["target_count"]) for r in target_rows}

    arrive_rows = await _fetch_all(
        pool,
        """
        SELECT mca.region, COUNT(DISTINCT mca.customer_unique_id) AS arrive_count
        FROM meeting_customer_analysis AS mca
        INNER JOIN meeting_registration AS mr ON mca.customer_unique_id = mr.customer_unique_id
        WHERE mca.min_deal >= 100
          AND mr.sign_in_status = '已签到'
          AND mca.region IS NOT NULL
        GROUP BY mca.region
        """,
    )
    arrivals = {r["region"]: int(r["arrive_count"]) for r in arrive_rows}

    return [
        TargetArrival(region=region, target_count=count, arrive_count=arrivals.get(region, 0))
        for region, count in targets.items()
    ]


async def get_target_customer_detail(pool: aiomysql.Pool, region: str | None = None) -> list[TargetCustomerDetail]:
    conditions = ["mca.min_deal >= 100", "mca.region IS NOT NULL"]
    params: dict[str, str] = {}
    if region:
        conditions.append("mca.region = :region")
        params["region"] = region

    where = " AND ".join(conditions)
    rows = await _fetch_all(
        pool,
        f"""
        SELECT
          mca.customer_name,
          mca.region,
          mca.customer_level,
          mca.new_or_old_customer,
          mca.min_deal,
          mca.max_deal,
          mca.prep_maturity,
          CASE WHEN mr.sign_in_status = '已签到' THEN 1 ELSE 0 END AS is_arrived
        FROM meeting_customer_analysis AS mca
        LEFT JOIN meeting_registration AS mr ON mca.customer_unique_id = mr.customer_unique_id
        WHERE {where}
        ORDER BY mca.min_deal DESC
        """,
        params,
    )
    return [
        TargetCustomerDetail(
            customer_name=r["customer_name"],
            region=r["region"],
            customer_level=r["customer_level"],
            new_or_old_customer=r["new_or_old_customer"],
            min_deal=float(r["min_deal"]) if r["min_deal"] is not None else None,
            max_deal=float(r["max_deal"]) if r["max_deal"] is not None else None,
            prep_maturity=r["prep_maturity"],
            is_arrived=bool(r["is_arrived"]),
        )
        for r in rows
    ]
