from pydantic import BaseModel


class ProgressItem(BaseModel):
    region: str
    deal_amount: float
    high_limit: float
    completion_rate: float | None


class ProgressSummary(BaseModel):
    items: list[ProgressItem]
    avg_completion_rate: float | None
