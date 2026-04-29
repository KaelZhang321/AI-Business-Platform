import aiomysql

from app.bi.meeting_bi.schemas.kpi import KpiItem, KpiOverview

TOTAL_BUDGET = 600  # 单位：万


async def _fetch_one(pool: aiomysql.Pool, sql: str) -> dict:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql)
            return await cur.fetchone() or {}


async def get_kpi_overview(pool: aiomysql.Pool) -> KpiOverview:
    row = await _fetch_one(
        pool,
        """
        SELECT COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration
        WHERE real_identity IS NOT NULL
          AND real_identity NOT LIKE '%市场%'
          AND real_identity NOT LIKE '%陪同%'
        """,
    )
    registered = int(row.get("cnt") or 0)

    row = await _fetch_one(
        pool,
        """
        SELECT COUNT(DISTINCT customer_unique_id) AS cnt
        FROM meeting_registration
        WHERE sign_in_status = '已签到'
          AND real_identity IS NOT NULL
          AND real_identity NOT LIKE '%市场%'
          AND real_identity NOT LIKE '%陪同%'
        """,
    )
    arrived = int(row.get("cnt") or 0)

    row = await _fetch_one(
        pool,
        """
        SELECT
          COALESCE(SUM(new_deal_amount), 0) AS deal,
          COALESCE(SUM(consumed_amount), 0) AS consumed,
          COALESCE(SUM(received_amount), 0) AS received
        FROM meeting_transaction_details
        """,
    )
    deal = float(row.get("deal") or 0) / 10000
    consumed = float(row.get("consumed") or 0) / 10000
    received = float(row.get("received") or 0) / 10000
    roi = round(TOTAL_BUDGET / (deal * 0.4), 4) if deal else 0

    return KpiOverview(
        registered_customers=KpiItem(label="报名客户", value=registered, unit="人"),
        arrived_customers=KpiItem(label="已抵达客户", value=arrived, unit="人"),
        deal_amount=KpiItem(label="已成交金额", value=deal, prefix="¥", unit="万"),
        consumed_budget=KpiItem(label="新规划消耗", value=consumed, prefix="¥", unit="万"),
        received_amount=KpiItem(label="已收款金额", value=received, prefix="¥", unit="万"),
        roi=KpiItem(label="总投资回报率", value=roi * 100, unit="%"),
    )
