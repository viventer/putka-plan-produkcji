import datetime as dt

from pydantic import BaseModel


class PlanItemOut(BaseModel):
    product_id: int
    name: str
    quantity: int


class PlanCategoryOut(BaseModel):
    category: str
    total: int
    items: list[PlanItemOut]


class ProductionPlanOut(BaseModel):
    date: dt.date
    categories: list[PlanCategoryOut]
