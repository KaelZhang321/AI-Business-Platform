from pydantic import BaseModel


class KpiItem(BaseModel):
    label: str
    value: float
    unit: str = ""
    prefix: str = ""


class KpiOverview(BaseModel):
    registered_customers: KpiItem
    arrived_customers: KpiItem
    deal_amount: KpiItem
    consumed_budget: KpiItem
    received_amount: KpiItem
    roi: KpiItem
