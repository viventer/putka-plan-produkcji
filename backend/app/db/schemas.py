from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.clock import WARSAW


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    unit_price: Decimal


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderIn(BaseModel):
    store_id: int
    delivery_date: date
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    delivery_date: date
    created_at: datetime
    items: list[OrderItemOut]

    @field_serializer("created_at")
    def serialize_created_at(self, created_at: datetime) -> str:
        # Postgres returns timestamptz in UTC. SQLite drops the offset and
        # keeps the Warsaw wall time. The response always uses Warsaw.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=WARSAW)
        else:
            created_at = created_at.astimezone(WARSAW)
        return created_at.isoformat()
