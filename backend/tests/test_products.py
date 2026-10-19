def test_products_returns_only_active(client):
    response = client.get("/products")

    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert "Kajzerka" in names
    assert "Chleb razowy" not in names  # nieaktywny
    assert "Rogal z makiem" not in names  # nieaktywny
    assert len(names) == 13


def test_stores(client):
    response = client.get("/stores")

    assert response.status_code == 200
    assert len(response.json()) == 5


def test_seed_is_idempotent(db, client):
    from app.seed import seed

    seed(db)
    seed(db)

    assert len(client.get("/stores").json()) == 5
    assert len(client.get("/products").json()) == 13
