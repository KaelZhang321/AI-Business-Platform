from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bi.meeting_bi.schemas.proposal import ProposalDetail, ProposalRow


def get_proposal_overview(db: Session) -> list[ProposalRow]:
    rows = db.execute(
        text(
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
            """
        )
    ).mappings().all()
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


def get_proposal_detail(db: Session, region: str | None = None, proposal_type: str | None = None) -> list[ProposalDetail]:
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
    rows = db.execute(
        text(
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
            """
        ),
        params,
    ).mappings().all()
    return [ProposalDetail(**{k: (str(v) if k == "record_date" and v else v) for k, v in r.items()}) for r in rows]
