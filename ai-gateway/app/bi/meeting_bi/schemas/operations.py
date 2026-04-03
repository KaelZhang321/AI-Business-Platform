from pydantic import BaseModel


class OperationsKpi(BaseModel):
    checkin_count: int
    pickup_count: int
    leave_count: int
    hospital_count: int


class TrendPoint(BaseModel):
    schedule_date: str
    day_time_period: str
    scene_label: str
    people_count: int
