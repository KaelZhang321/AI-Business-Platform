from pydantic import BaseModel


class SourceCount(BaseModel):
    region: str
    source_type: str
    customer_count: int


class TargetArrival(BaseModel):
    region: str
    target_count: int
    arrive_count: int


class TargetCustomerDetail(BaseModel):
    customer_name: str | None
    region: str | None
    customer_level: str | None
    new_or_old_customer: str | None
    min_deal: float | None
    max_deal: float | None
    prep_maturity: str | None
    is_arrived: bool
