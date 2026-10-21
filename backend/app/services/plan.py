import itertools
from collections.abc import Sequence
from datetime import date
from typing import NamedTuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models.order import Order, OrderItem
from app.db.models.product import Product
from app.db.schemas.plan import PlanCategoryOut, PlanItemOut, ProductionPlanOut


class _PlanRow(NamedTuple):
    id: int
    name: str
    category: str
    quantity: int


def build_plan(db: Session, day: date) -> ProductionPlanOut:
    """Sum ordered quantities for one delivery date, including active products at zero."""
    return ProductionPlanOut(date=day, categories=_categories_from_rows(_plan_rows(db, day)))


def _plan_rows(db: Session, day: date) -> list[_PlanRow]:
    """Load products with ordered quantities for one delivery date.

    Active products stay in the result at zero. An inactive product stays only
    when it was ordered for this day. Rows are ordered by category, then name.
    """
    ordered = (
        select(OrderItem.product_id, func.sum(OrderItem.quantity).label("qty"))
        .join(Order)
        .where(Order.delivery_date == day)
        .group_by(OrderItem.product_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Product.id,
            Product.name,
            Product.category,
            func.coalesce(ordered.c.qty, 0).label("quantity"),
        )
        .outerjoin(ordered, ordered.c.product_id == Product.id)
        .where(or_(Product.active.is_(True), func.coalesce(ordered.c.qty, 0) > 0))
        .order_by(Product.category, Product.name)
    ).all()
    return [
        _PlanRow(id=row.id, name=row.name, category=row.category, quantity=int(row.quantity))
        for row in rows
    ]


def _categories_from_rows(rows: Sequence[_PlanRow]) -> list[PlanCategoryOut]:
    """Group consecutive rows of one category into plan categories.

    ``rows`` must already be ordered by category. ``groupby`` only merges
    adjacent rows that share a category; ``_plan_rows`` provides that order.
    """
    categories: list[PlanCategoryOut] = []
    for category, group in itertools.groupby(rows, key=lambda row: row.category):
        items = [
            PlanItemOut(product_id=row.id, name=row.name, quantity=row.quantity)
            for row in group
        ]
        categories.append(
            PlanCategoryOut(
                category=category,
                total=sum(item.quantity for item in items),
                items=items,
            )
        )
    return categories
