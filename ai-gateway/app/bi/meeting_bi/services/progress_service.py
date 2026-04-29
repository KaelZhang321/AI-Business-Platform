import aiomysql

from app.bi.meeting_bi.schemas.progress import ProgressItem, ProgressSummary


async def get_progress(pool: aiomysql.Pool) -> ProgressSummary:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT
                  p.region,
                  COALESCE(p.deal_target_high, 0) AS high_limit,
                  COALESCE(SUM(t.new_deal_amount), 0) / 10000 AS deal_amount
                FROM meeting_region_proposal_targets AS p
                LEFT JOIN meeting_transaction_details AS t ON p.region = t.region
                WHERE p.region_owner IS NOT NULL
                GROUP BY p.region, p.deal_target_high
                ORDER BY deal_amount DESC
                """
            )
            rows = await cur.fetchall() or []

    items: list[ProgressItem] = []
    rates: list[float] = []
    for r in rows:
        deal = round(float(r["deal_amount"] or 0), 2)
        high = float(r["high_limit"] or 0)
        rate = round(deal / high * 100, 2) if high else None
        items.append(
            ProgressItem(
                region=r["region"],
                deal_amount=deal,
                high_limit=high,
                completion_rate=rate,
            )
        )
        if rate is not None:
            rates.append(rate)

    avg_rate = round(sum(rates) / len(rates), 2) if rates else None
    return ProgressSummary(items=items, avg_completion_rate=avg_rate)
