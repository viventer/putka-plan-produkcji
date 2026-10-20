from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.db.models.order import Order, OrderItem
from app.db.models.product import Product, Store

DAY = date(2026, 10, 21)
OTHER_DAY = date(2026, 10, 22)
CREATED = datetime(2026, 10, 19, 11, 0, tzinfo=ZoneInfo("Europe/Warsaw"))

ACTIVE_BY_CATEGORY = {
    "Bułki": ["Bagietka", "Bułka maślana", "Grahamka", "Kajzerka"],
    "Cukiernia": [
        "Croissant",
        "Drożdżówka z serem",
        "Pączek z różą",
        "Sernik (porcja)",
        "Szarlotka (porcja)",
    ],
    "Pieczywo": [
        "Chleb orkiszowy",
        "Chleb pszenny",
        "Chleb z ziarnami",
        "Chleb żytni na zakwasie",
    ],
}


def _store(db, name: str) -> Store:
    store = db.scalar(select(Store).where(Store.name == name))
    assert store is not None
    return store


def _product(db, name: str) -> Product:
    product = db.scalar(select(Product).where(Product.name == name))
    assert product is not None
    return product


def _order(db, store_name: str, day: date, lines: list[tuple[str, int]]) -> None:
    store = _store(db, store_name)
    db.add(
        Order(
            store_id=store.id,
            delivery_date=day,
            created_at=CREATED,
            items=[
                OrderItem(
                    product_id=_product(db, name).id,
                    quantity=quantity,
                    unit_price=_product(db, name).unit_price,
                )
                for name, quantity in lines
            ],
        )
    )
    db.commit()


def _plan(client, day: date = DAY) -> dict:
    response = client.get("/production-plan", params={"date": day.isoformat()})
    assert response.status_code == 200
    return response.json()


def _quantities(body: dict) -> dict[str, int]:
    return {
        item["name"]: item["quantity"]
        for category in body["categories"]
        for item in category["items"]
    }


def test_quantities_sum_across_orders(client, db):
    _order(db, "Putka Mokotów", DAY, [("Kajzerka", 100), ("Grahamka", 3)])
    _order(db, "Putka Mokotów", DAY, [("Kajzerka", 5)])
    _order(db, "Putka Śródmieście", DAY, [("Kajzerka", 20)])

    quantities = _quantities(_plan(client))

    assert quantities["Kajzerka"] == 125
    assert quantities["Grahamka"] == 3


def test_categories_are_grouped_ordered_and_totalled(client, db):
    _order(
        db,
        "Putka Wola",
        DAY,
        [("Kajzerka", 100), ("Chleb orkiszowy", 10), ("Croissant", 2)],
    )
    _order(db, "Putka Praga", DAY, [("Kajzerka", 20), ("Pączek z różą", 4)])

    body = _plan(client)
    categories = {category["category"]: category for category in body["categories"]}

    assert [category["category"] for category in body["categories"]] == [
        "Bułki",
        "Cukiernia",
        "Pieczywo",
    ]
    assert categories["Bułki"]["total"] == 120
    assert categories["Cukiernia"]["total"] == 6
    assert categories["Pieczywo"]["total"] == 10
    assert [item["name"] for item in categories["Bułki"]["items"]] == ACTIVE_BY_CATEGORY[
        "Bułki"
    ]


def test_day_without_orders_lists_active_products_at_zero(client):
    body = _plan(client)

    assert body["date"] == DAY.isoformat()
    assert [category["category"] for category in body["categories"]] == list(
        ACTIVE_BY_CATEGORY
    )
    for category in body["categories"]:
        assert category["total"] == 0
        assert [item["name"] for item in category["items"]] == ACTIVE_BY_CATEGORY[
            category["category"]
        ]
        assert [item["quantity"] for item in category["items"]] == [0] * len(
            category["items"]
        )


def test_inactive_products_without_orders_are_omitted(client):
    names = set(_quantities(_plan(client)))

    assert "Chleb razowy" not in names
    assert "Rogal z makiem" not in names


def test_inactive_product_with_orders_is_included(client, db):
    _order(db, "Putka Mokotów", DAY, [("Chleb razowy", 4), ("Rogal z makiem", 7)])

    body = _plan(client)
    categories = {category["category"]: category for category in body["categories"]}

    assert [item["name"] for item in categories["Pieczywo"]["items"]] == [
        "Chleb orkiszowy",
        "Chleb pszenny",
        "Chleb razowy",
        "Chleb z ziarnami",
        "Chleb żytni na zakwasie",
    ]
    assert categories["Pieczywo"]["total"] == 4
    assert [item["name"] for item in categories["Bułki"]["items"]] == [
        *ACTIVE_BY_CATEGORY["Bułki"],
        "Rogal z makiem",
    ]
    assert categories["Bułki"]["total"] == 7


def test_orders_for_another_date_are_excluded(client, db):
    _order(db, "Putka Mokotów", DAY, [("Kajzerka", 10)])
    _order(db, "Putka Mokotów", OTHER_DAY, [("Kajzerka", 50), ("Chleb razowy", 9)])

    quantities = _quantities(_plan(client))

    assert quantities["Kajzerka"] == 10
    assert "Chleb razowy" not in quantities


@pytest.mark.parametrize(
    "params",
    [{}, {"date": "21-10-2026"}, {"date": "2026-10-21T00:00:00"}],
)
def test_missing_or_invalid_date_is_rejected(client, params):
    response = client.get("/production-plan", params=params)

    assert response.status_code == 422
