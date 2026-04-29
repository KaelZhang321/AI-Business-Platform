import aiomysql

from app.bi.meeting_bi.schemas.achievement import AchievementBar, AchievementDetail, AchievementRow


async def _fetch_all(pool: aiomysql.Pool, sql: str, params: dict[str, str] | None = None) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params or {})
            return await cur.fetchall() or []


async def get_achievement_chart(pool: aiomysql.Pool) -> list[AchievementBar]:
    rows = await _fetch_all(
        pool,
        """
        SELECT
          p.region,
          COALESCE(p.deal_target_low, 0) AS low_limit,
          COALESCE(p.deal_target_high, 0) AS high_limit,
          COALESCE(SUM(t.new_deal_amount), 0) / 10000 AS deal_amount
        FROM meeting_region_proposal_targets AS p
        LEFT JOIN meeting_transaction_details AS t ON p.region = t.region
        WHERE p.region_owner IS NOT NULL
        GROUP BY p.region, low_limit, high_limit
        ORDER BY p.region
        """,
    )
    return [AchievementBar(region=r["region"], low_limit=float(r["low_limit"] or 0), high_limit=float(r["high_limit"] or 0), deal_amount=float(r["deal_amount"] or 0)) for r in rows]


async def get_achievement_table(pool: aiomysql.Pool) -> list[AchievementRow]:
    rows = await _fetch_all(
        pool,
        """
        SELECT
          p.region,
          COALESCE(SUM(t.new_deal_amount), 0) / 10000 AS actual_amount,
          COALESCE(p.deal_target, 0) AS target_amount,
          COALESCE(p.deal_target_low, 0) AS min_limit,
          COALESCE(p.deal_target_high, 0) AS max_limit
        FROM meeting_region_proposal_targets AS p
        LEFT JOIN meeting_transaction_details AS t ON p.region = t.region
        WHERE p.region_owner IS NOT NULL
        GROUP BY p.region, p.deal_target, p.deal_target_low, p.deal_target_high
        ORDER BY actual_amount DESC
        """,
    )
    result: list[AchievementRow] = []
    for i, r in enumerate(rows, 1):
        actual = round(float(r["actual_amount"] or 0), 2)
        target = float(r["target_amount"] or 0)
        rate = round(actual / target * 100, 2) if target else None
        result.append(
            AchievementRow(
                row_num=i,
                region=r["region"],
                actual_amount=actual,
                target_amount=target,
                min_limit=float(r["min_limit"] or 0),
                max_limit=float(r["max_limit"] or 0),
                achievement_rate=rate,
                difference=actual - target,
            )
        )
    return result


async def get_achievement_detail(pool: aiomysql.Pool, region: str | None = None) -> list[AchievementDetail]:
    conditions = ["1 = 1"]
    params: dict[str, str] = {}
    if region:
        conditions.append("region = :region")
        params["region"] = region

    where = " AND ".join(conditions)
    rows = await _fetch_all(
        pool,
        f"""
        SELECT
          customer_name,
          region,
          branch,
          deal_type,
          deal_content,
          COALESCE(new_deal_amount, 0) / 10000 AS new_deal_amount,
          COALESCE(received_amount, 0) / 10000 AS received_amount,
          plan_type,
          record_date
        FROM meeting_transaction_details
        WHERE {where}
        ORDER BY new_deal_amount DESC
        """,
        params,
    )
    return [
        AchievementDetail(
            customer_name=r.get("customer_name"),
            region=r.get("region"),
            branch=r.get("branch"),
            deal_type=r.get("deal_type"),
            deal_content=r.get("deal_content"),
            new_deal_amount=float(r.get("new_deal_amount") or 0),
            received_amount=float(r.get("received_amount") or 0),
            plan_type=r.get("plan_type"),
            record_date=str(r.get("record_date")) if r.get("record_date") else None,
        )
        for r in rows
    ]
