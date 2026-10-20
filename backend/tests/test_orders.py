from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.clock import get_now
from app.db.models.order import Order, OrderItem
from app.db.models.product import Product, Store
from app.main import app

WAW = ZoneInfo("Europe/Warsaw")
DATE_ERROR = "Delivery date must be tomorrow or later"
CUTOFF_ERROR = "Order deadline passed (14:00 Europe/Warsaw on the previous day)"


@pytest.fixture(autouse=True)
def _reset_clock():
    yield
    app.dependency_overrides.pop(get_now, None)


def _at(moment: datetime) -> None:
    app.dependency_overrides[get_now] = lambda: moment


def _store(db) -> Store:
    store = db.scalar(select(Store).where(Store.name == "Putka Mokotów"))
    assert store is not None
    return store


def _product(db, name: str) -> Product:
    product = db.scalar(select(Product).where(Product.name == name))
    assert product is not None
    return product


def _payload(store_id: int, delivery: date, items: list[tuple[int, int]]) -> dict:
    return {
        "store_id": store_id,
        "delivery_date": delivery.isoformat(),
        "items": [
            {"product_id": product_id, "quantity": quantity}
            for product_id, quantity in items
        ],
    }


def _counts(db) -> tuple[int, int]:
    db.expire_all()
    orders = db.scalar(select(func.count()).select_from(Order))
    items = db.scalar(select(func.count()).select_from(OrderItem))
    assert orders is not None
    assert items is not None
    return orders, items


def test_valid_order_is_created(client, db):
    moment = datetime(2026, 10, 19, 11, 44, tzinfo=WAW)
    _at(moment)
    store = _store(db)
    bread = _product(db, "Chleb orkiszowy")
    roll = _product(db, "Kajzerka")

    response = client.post(
        "/orders",
        json=_payload(
            store.id,
            date(2026, 10, 21),
            [(bread.id, 20), (roll.id, 5)],
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["store_id"] == store.id
    assert body["delivery_date"] == "2026-10-21"
    assert body["created_at"] == "2026-10-19T11:44:00+02:00"
    assert body["items"] == [
        {"product_id": bread.id, "quantity": 20, "unit_price": "11.50"},
        {"product_id": roll.id, "quantity": 5, "unit_price": "0.90"},
    ]

    db.expire_all()
    stored = db.scalars(select(Order)).one()
    assert stored.store_id == store.id
    assert stored.delivery_date == date(2026, 10, 21)
    assert len(stored.items) == 2
    assert stored.items[0].unit_price == bread.unit_price
    assert stored.items[1].unit_price == roll.unit_price


def test_same_store_can_order_twice_for_one_day(client, db):
    _at(datetime(2026, 10, 19, 11, 0, tzinfo=WAW))
    store = _store(db)
    product = _product(db, "Kajzerka")
    payload = _payload(store.id, date(2026, 10, 21), [(product.id, 1)])

    first = client.post("/orders", json=payload)
    second = client.post("/orders", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert _counts(db) == (2, 2)


def test_delivery_today_and_yesterday_are_rejected(client, db):
    _at(datetime(2026, 10, 19, 10, 0, tzinfo=WAW))
    store = _store(db)
    product = _product(db, "Kajzerka")

    today = client.post(
        "/orders",
        json=_payload(store.id, date(2026, 10, 19), [(product.id, 1)]),
    )
    yesterday = client.post(
        "/orders",
        json=_payload(store.id, date(2026, 10, 18), [(product.id, 1)]),
    )

    assert today.status_code == 422
    assert today.json()["detail"] == DATE_ERROR
    assert yesterday.status_code == 422
    assert yesterday.json()["detail"] == DATE_ERROR
    assert _counts(db) == (0, 0)


def test_cutoff_before_at_and_after_in_winter_and_summer(client, db):
    store = _store(db)
    product = _product(db, "Kajzerka")
    cases = [
        (datetime(2027, 1, 14, 13, 59, tzinfo=WAW), date(2027, 1, 15), 201, None),
        (datetime(2027, 1, 14, 14, 0, tzinfo=WAW), date(2027, 1, 15), 422, CUTOFF_ERROR),
        (datetime(2027, 1, 14, 14, 1, tzinfo=WAW), date(2027, 1, 15), 422, CUTOFF_ERROR),
        (datetime(2027, 7, 14, 13, 59, tzinfo=WAW), date(2027, 7, 15), 201, None),
        (datetime(2027, 7, 14, 14, 0, tzinfo=WAW), date(2027, 7, 15), 422, CUTOFF_ERROR),
        (datetime(2027, 7, 14, 16, 30, tzinfo=WAW), date(2027, 7, 15), 422, CUTOFF_ERROR),
        (datetime(2027, 1, 14, 18, 0, tzinfo=WAW), date(2027, 1, 16), 201, None),
    ]

    for moment, delivery, status, detail in cases:
        _at(moment)
        response = client.post(
            "/orders",
            json=_payload(store.id, delivery, [(product.id, 1)]),
        )
        assert response.status_code == status
        if detail is not None:
            assert response.json()["detail"] == detail

    assert _counts(db) == (3, 3)


def test_inactive_product_leaves_no_rows(client, db):
    _at(datetime(2026, 10, 19, 11, 0, tzinfo=WAW))
    store = _store(db)
    active = _product(db, "Kajzerka")
    inactive = _product(db, "Chleb razowy")

    response = client.post(
        "/orders",
        json=_payload(
            store.id,
            date(2026, 10, 21),
            [(active.id, 2), (inactive.id, 1)],
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Inactive products: Chleb razowy"
    assert _counts(db) == (0, 0)


def test_missing_store_or_product_leaves_no_rows(client, db):
    _at(datetime(2026, 10, 19, 11, 0, tzinfo=WAW))
    store = _store(db)
    product = _product(db, "Kajzerka")

    missing_store = client.post(
        "/orders",
        json=_payload(999_999, date(2026, 10, 21), [(product.id, 1)]),
    )
    missing_product = client.post(
        "/orders",
        json=_payload(store.id, date(2026, 10, 21), [(999_999, 1)]),
    )

    assert missing_store.status_code == 404
    assert missing_store.json()["detail"] == "Store 999999 does not exist"
    assert missing_product.status_code == 404
    assert missing_product.json()["detail"] == "Products not found: 999999"
    assert _counts(db) == (0, 0)


def test_duplicate_product_is_rejected(client, db):
    _at(datetime(2026, 10, 19, 11, 0, tzinfo=WAW))
    store = _store(db)
    product = _product(db, "Kajzerka")

    response = client.post(
        "/orders",
        json=_payload(
            store.id,
            date(2026, 10, 21),
            [(product.id, 1), (product.id, 2)],
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == f"Product {product.id} is duplicated"
    assert _counts(db) == (0, 0)


def test_invalid_payload_is_validation_error(client, db):
    _at(datetime(2026, 10, 19, 11, 0, tzinfo=WAW))
    store = _store(db)
    product = _product(db, "Kajzerka")
    base = _payload(store.id, date(2026, 10, 21), [(product.id, 1)])
    payloads = [
        {**base, "items": [{"product_id": product.id, "quantity": 0}]},
        {**base, "items": [{"product_id": product.id, "quantity": -1}]},
        {**base, "items": []},
        {**base, "delivery_date": "21-10-2026"},
    ]

    for payload in payloads:
        response = client.post("/orders", json=payload)
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)

    assert _counts(db) == (0, 0)
