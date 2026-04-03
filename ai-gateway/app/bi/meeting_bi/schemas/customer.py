from pydantic import BaseModel


class PieSlice(BaseModel):
    name: str
    value: int
    percentage: float


class CustomerProfile(BaseModel):
    level_distribution: list[PieSlice]
    role_distribution: list[PieSlice]
    new_old_distribution: list[PieSlice]
