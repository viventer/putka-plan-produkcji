import logging
from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import WARSAW, is_before_cutoff
from app.errors import BusinessRuleError, NotFoundError
from app.models import Order, OrderItem, Product, Store
from app.schemas import OrderIn

logger = logging.getLogger(__name__)


def create_order(db: Session, payload: OrderIn, now: datetime) -> Order:
    """Validate one order and insert it. Raises before any write on failure."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    today = now.astimezone(WARSAW).date()
    if payload.delivery_date <= today:
        raise BusinessRuleError("Delivery date must be tomorrow or later")

    if not is_before_cutoff(payload.delivery_date, now):
        raise BusinessRuleError(
            "Order deadline passed (14:00 Europe/Warsaw on the previous day)"
        )

    store = db.get(Store, payload.store_id)
    if store is None:
        raise NotFoundError(f"Store {payload.store_id} does not exist")

    product_ids = [item.product_id for item in payload.items]
    duplicated = sorted(
        product_id for product_id, count in Counter(product_ids).items() if count > 1
    )
    if duplicated:
        listed = ", ".join(str(product_id) for product_id in duplicated)
        if len(duplicated) == 1:
            raise BusinessRuleError(f"Product {listed} is duplicated")
        raise BusinessRuleError(f"Products {listed} are duplicated")

    products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    by_id = {product.id: product for product in products}
    missing = sorted(set(product_ids) - set(by_id))
    if missing:
        listed = ", ".join(str(product_id) for product_id in missing)
        raise NotFoundError(f"Products not found: {listed}")

    inactive = sorted(
        product.name for product in by_id.values() if not product.active
    )
    if inactive:
        raise BusinessRuleError(f"Inactive products: {', '.join(inactive)}")

    order = Order(
        store_id=payload.store_id,
        delivery_date=payload.delivery_date,
        created_at=now,
        items=[
            OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=by_id[item.product_id].unit_price,
            )
            for item in payload.items
        ],
    )
    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.exception("Order insert rejected by the database")
        raise
    db.refresh(order)
    return order
