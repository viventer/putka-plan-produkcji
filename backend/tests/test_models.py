from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import Order, OrderItem, Product, Store

WARSAW = ZoneInfo("Europe/Warsaw")


def _new_order(db, items: list[OrderItem]) -> Order:
    store = db.scalars(select(Store)).first()
    assert store is not None
    return Order(
        store_id=store.id,
        delivery_date=date(2026, 10, 21),
        created_at=datetime(2026, 10, 19, 11, 44, tzinfo=WARSAW),
        items=items,
    )


def test_order_with_items_is_persisted(db):
    product = db.scalars(select(Product)).first()
    assert product is not None
    order = _new_order(
        db,
        [OrderItem(product_id=product.id, quantity=2, unit_price=product.unit_price)],
    )
    db.add(order)
    db.commit()

    stored = db.scalars(select(Order)).one()
    assert stored.store_id == order.store_id
    assert len(stored.items) == 1
    assert stored.items[0].quantity == 2
    assert stored.items[0].unit_price == product.unit_price


def test_order_item_quantity_must_be_positive(db):
    product = db.scalars(select(Product)).first()
    assert product is not None
    order = _new_order(
        db,
        [OrderItem(product_id=product.id, quantity=0, unit_price=product.unit_price)],
    )
    db.add(order)

    with pytest.raises(IntegrityError):
        db.commit()


def test_product_is_unique_per_order(db):
    product = db.scalars(select(Product)).first()
    assert product is not None
    order = _new_order(
        db,
        [
            OrderItem(product_id=product.id, quantity=1, unit_price=product.unit_price),
            OrderItem(product_id=product.id, quantity=2, unit_price=product.unit_price),
        ],
    )
    db.add(order)

    with pytest.raises(IntegrityError):
        db.commit()


def test_order_item_product_must_exist(db):
    order = _new_order(
        db,
        [OrderItem(product_id=999_999, quantity=1, unit_price=Decimal("1.00"))],
    )
    db.add(order)

    with pytest.raises(IntegrityError):
        db.commit()
