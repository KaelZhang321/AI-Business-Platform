from pydantic import BaseModel


class ProposalRow(BaseModel):
    proposal_type: str
    target_count: int
    target_amount: float
    actual_count: int
    actual_amount: float


class ProposalCrossRow(BaseModel):
    region: str
    proposals: dict[str, int]


class ProposalDetail(BaseModel):
    customer_name: str | None
    region: str | None
    deal_content: str | None
    new_deal_amount: float
    received_amount: float
    record_date: str | None
