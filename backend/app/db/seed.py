from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, Store

STORES = [
    ("Putka Mokotów", "ul. Puławska 45, 02-508 Warszawa"),
    ("Putka Śródmieście", "ul. Marszałkowska 84, 00-514 Warszawa"),
    ("Putka Żoliborz", "pl. Wilsona 2, 01-626 Warszawa"),
    ("Putka Praga", "ul. Ząbkowska 27, 03-736 Warszawa"),
    ("Putka Wola", "ul. Chłodna 15, 00-891 Warszawa"),
]

# (nazwa, kategoria, cena, aktywny)
PRODUCTS = [
    ("Chleb pszenny", "Pieczywo", "6.50", True),
    ("Chleb żytni na zakwasie", "Pieczywo", "9.90", True),
    ("Chleb orkiszowy", "Pieczywo", "11.50", True),
    ("Chleb z ziarnami", "Pieczywo", "10.90", True),
    ("Chleb razowy", "Pieczywo", "8.90", False),
    ("Kajzerka", "Bułki", "0.90", True),
    ("Grahamka", "Bułki", "1.20", True),
    ("Bułka maślana", "Bułki", "1.80", True),
    ("Rogal z makiem", "Bułki", "2.20", False),
    ("Bagietka", "Bułki", "4.50", True),
    ("Drożdżówka z serem", "Cukiernia", "4.20", True),
    ("Pączek z różą", "Cukiernia", "3.90", True),
    ("Sernik (porcja)", "Cukiernia", "9.50", True),
    ("Szarlotka (porcja)", "Cukiernia", "8.50", True),
    ("Croissant", "Cukiernia", "5.50", True),
]


def seed(db: Session) -> None:
    """Uzupełnia dane startowe. Można wywoływać wielokrotnie."""
    existing_stores = set(db.scalars(select(Store.name)))
    for name, address in STORES:
        if name not in existing_stores:
            db.add(Store(name=name, address=address))

    existing_products = set(db.scalars(select(Product.name)))
    for name, category, price, active in PRODUCTS:
        if name not in existing_products:
            db.add(
                Product(
                    name=name,
                    category=category,
                    unit_price=Decimal(price),
                    active=active,
                )
            )
    db.commit()
