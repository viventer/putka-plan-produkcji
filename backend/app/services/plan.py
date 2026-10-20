import itertools
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models.order import Order, OrderItem
from app.db.models.product import Product
from app.db.schemas.plan import PlanCategoryOut, PlanItemOut, ProductionPlanOut


def build_plan(db: Session, day: date) -> ProductionPlanOut:
    """Sum ordered quantities for one delivery date, including active products at zero."""
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

    categories = []
    for category, group in itertools.groupby(rows, key=lambda row: row.category):
        items = [
            PlanItemOut(
                product_id=row.id, name=row.name, quantity=int(row.quantity)
            )
            for row in group
        ]
        categories.append(
            PlanCategoryOut(
                category=category,
                total=sum(item.quantity for item in items),
                items=items,
            )
        )
    return ProductionPlanOut(date=day, categories=categories)
