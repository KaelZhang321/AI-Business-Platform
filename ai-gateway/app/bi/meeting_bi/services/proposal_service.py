import aiomysql

from app.bi.meeting_bi.schemas.proposal import ProposalDetail, ProposalRow


async def _fetch_all(pool: aiomysql.Pool, sql: str, params: dict[str, str] | None = None) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params or {})
            return await cur.fetchall() or []


async def get_proposal_overview(pool: aiomysql.Pool) -> list[ProposalRow]:
    rows = await _fetch_all(
        pool,
        """
        SELECT
          p.proposal_type,
          p.target_count,
          p.target_amount,
          COUNT(t.special_remarks) AS actual_count,
          SUM(t.new_deal_amount) / 10000 AS actual_amount
        FROM meeting_proposal_targets AS p
        LEFT JOIN meeting_transaction_details AS t ON p.proposal_type = TRIM(t.special_remarks)
        GROUP BY p.proposal_type, p.target_count, p.target_amount
        ORDER BY actual_amount DESC
        """,
    )
    return [
        ProposalRow(
            proposal_type=r["proposal_type"],
            target_count=int(r["target_count"] or 0),
            target_amount=float(r["target_amount"] or 0),
            actual_count=int(r["actual_count"] or 0),
            actual_amount=round(float(r["actual_amount"] or 0), 2),
        )
        for r in rows
    ]


async def get_proposal_detail(pool: aiomysql.Pool, region: str | None = None, proposal_type: str | None = None) -> list[ProposalDetail]:
    conditions = ["deal_type LIKE '%新成交%'"]
    params: dict[str, str] = {}
    if region:
        conditions.append("region = :region")
        params["region"] = region
    if proposal_type:
        if "海心卡" in proposal_type or "细胞卡" in proposal_type:
            conditions.append("(deal_content LIKE '%海心卡%' OR deal_content LIKE '%细胞卡%')")
        else:
            conditions.append("deal_content LIKE CONCAT('%', :proposal_type, '%')")
            params["proposal_type"] = proposal_type

    where = " AND ".join(conditions)
    rows = await _fetch_all(
        pool,
        f"""
        SELECT
          customer_name,
          region,
          deal_content,
          COALESCE(new_deal_amount, 0) AS new_deal_amount,
          COALESCE(received_amount, 0) AS received_amount,
          record_date
        FROM meeting_transaction_details
        WHERE {where}
        ORDER BY new_deal_amount DESC
        """,
        params,
    )
    return [
        ProposalDetail(
            customer_name=r.get("customer_name"),
            region=r.get("region"),
            deal_content=r.get("deal_content"),
            new_deal_amount=float(r.get("new_deal_amount") or 0),
            received_amount=float(r.get("received_amount") or 0),
            record_date=str(r.get("record_date")) if r.get("record_date") else None,
        )
        for r in rows
    ]
