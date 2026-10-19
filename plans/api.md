# Backend API – Putka, production plan

HTTP contract for the endpoints required by [specification.md](specification.md) (tasks 1–7). Paths have no prefix. The bonus (CSV export or a Redis cache) is not part of this API.

`OrderIn` and `OrderOut` already exist in `backend/app/db/schemas.py`. `PlanItemOut`, `PlanCategoryOut`, and `ProductionPlanOut` are still to be added. The routes themselves are not implemented yet.

## 1. Shared rules

- JSON request and response bodies. Dates are `YYYY-MM-DD`. Money is a decimal string (`Decimal` / `Numeric(10, 2)`), for example `"11.50"`, never a float.
- Local time rules use `Europe/Warsaw`. "Now" is injected by `get_now` (the `Now` alias in `api/deps.py`), which returns `datetime.now(ZoneInfo("Europe/Warsaw"))`. Tests replace it with `app.dependency_overrides[get_now]`. The server timezone is not used, and naive datetimes are rejected.
- Routes are thin: validate input, call a function in `services/`, return a schema. Every route sets `response_model`. ORM objects are not returned directly.
- Domain errors are raised in `services/` and mapped to HTTP in `main.py`. The body is `{"detail": "<message>"}` with `detail` as a string. No stack traces. Unexpected exceptions are logged with `logging` and returned as `500`.

| Source | Status | When |
| --- | --- | --- |
| `NotFoundError` | 404 | The store or a product id does not exist. |
| `BusinessRuleError` | 422 | A business rule fails (delivery date, cutoff, inactive product, duplicate `product_id` in the payload). |
| Pydantic / FastAPI validation | 422 | The payload or a query parameter is malformed. |
| `IntegrityError` after `rollback` | 409 | The database rejects the write (a race, a foreign key, or `UNIQUE`). |

Validation errors do not use a string `detail`. FastAPI returns a list:

```json
{
  "detail": [
    {
      "type": "greater_than",
      "loc": ["body", "items", 0, "quantity"],
      "msg": "Input should be greater than 0",
      "input": 0
    }
  ]
}
```

The frontend has to read both shapes: a string `detail` for domain errors, and a list for validation errors.

## 2. Existing catalog

These routes already exist in `backend/app/main.py`. The contract does not change. They move to `api/catalog.py`.

### `GET /health`

Response `200`:

```json
{ "status": "ok" }
```

### `GET /stores`

Response `200`: `list[StoreOut]`, ordered by `name`.

```json
[{ "id": 1, "name": "Putka Mokotów", "address": "ul. Puławska 45, 02-508 Warszawa" }]
```

`StoreOut`: `id: int`, `name: str`, `address: str`.

### `GET /products`

Response `200`: `list[ProductOut]`, only `active` products, ordered by `category`, then `name`.

```json
[{ "id": 3, "name": "Chleb orkiszowy", "category": "Pieczywo", "unit_price": "11.50" }]
```

`ProductOut`: `id: int`, `name: str`, `category: str`, `unit_price: Decimal`. `active` is not part of the response. Inactive products are omitted here; the production plan is the only place an inactive product can appear, and only when that date already has orders for it.

## 3. `POST /orders`

Creates one order for one store and one delivery date. A store may place several orders for the same day: there is no `UNIQUE(store_id, delivery_date)`. There is no edit or cancel endpoint.

**Files:** `services/orders.py` (`create_order`), `api/orders.py`, schemas in `db/schemas.py`.

### Request

`OrderIn`:

| Field | Type | Rules |
| --- | --- | --- |
| `store_id` | int | Required. Must match a row in `stores`. |
| `delivery_date` | date (`YYYY-MM-DD`) | Required. Must be tomorrow or later in Warsaw. |
| `items` | array, min length 1 | Each element is `OrderItemIn`. |
| `items[].product_id` | int | Required. Must match an active product. Unique inside this array. |
| `items[].quantity` | int | Required. `> 0`. |

```json
{
  "store_id": 1,
  "delivery_date": "2026-10-21",
  "items": [{ "product_id": 3, "quantity": 20 }]
}
```

### Response `201 Created`

`OrderOut`. `unit_price` is copied from `Product.unit_price` at order time, so a later price change does not rewrite this order. `created_at` is the injected `now`, as an ISO 8601 datetime with the Warsaw offset.

```json
{
  "id": 7,
  "store_id": 1,
  "delivery_date": "2026-10-21",
  "created_at": "2026-10-19T11:44:00+02:00",
  "items": [{ "product_id": 3, "quantity": 20, "unit_price": "11.50" }]
}
```

| Field | Type |
| --- | --- |
| `id` | int |
| `store_id` | int |
| `delivery_date` | date |
| `created_at` | datetime with offset |
| `items[].product_id` | int |
| `items[].quantity` | int |
| `items[].unit_price` | decimal string |

### Business logic

`create_order(db, payload, now)` checks the rules in this order. Each failure raises before any write.

1. **Delivery date.** `today = now.astimezone(WAW).date()`. If `delivery_date <= today`, `BusinessRuleError` with `"Delivery date must be tomorrow or later"`. The Warsaw calendar date counts, not the server date and not UTC. Today and yesterday are both rejected. Exactly tomorrow is allowed only if the cutoff below still holds.
2. **Cutoff.** If `not is_before_cutoff(delivery_date, now)`, `BusinessRuleError` with `"Order deadline passed (14:00 Europe/Warsaw on the previous day)"`. The deadline is 14:00 Europe/Warsaw on the calendar day before `delivery_date`. `now < cutoff` is accepted; `now == cutoff` and anything later are rejected. The cutoff is built with `datetime.combine(order_day, time(14, 0), tzinfo=ZoneInfo("Europe/Warsaw"))`, so the same rule holds in CET (UTC+1) and CEST (UTC+2). This depends on the section 3 fix in the specification: the current `cutoff.py` uses a fixed 12:00 UTC, which is 14:00 in summer and 13:00 in winter.
3. **Store.** `db.get(Store, store_id)`. A missing store is `NotFoundError` (404).
4. **Duplicate products in the payload.** A repeated `product_id` is `BusinessRuleError` (422). Quantities are not merged. This matches `UNIQUE(order_id, product_id)` on `order_items`.
5. **Products.** One query, `select(Product).where(Product.id.in_(ids))`, not one query per line. Missing ids are `NotFoundError` and the message lists those ids (404). Inactive products are `BusinessRuleError` and the message lists their names (422).
6. **Write.** One `Order` with `created_at=now` and `items` built as `OrderItem(product_id, quantity, unit_price=product.unit_price)`, then `db.add`, `db.commit`, `db.refresh`. The `items` relationship uses `cascade="all, delete-orphan"`, so one `add` inserts the order and its lines.

Validation and the insert share one session and one `commit()`. An exception before the commit leaves no rows. An `IntegrityError` from the database (a product deactivated between the check and the insert, or a foreign-key or unique violation) is rolled back and returned as 409, so a failed order still leaves no rows.

### Error examples

| Case | Status | `detail` |
| --- | --- | --- |
| `delivery_date` today or earlier | 422 | `"Delivery date must be tomorrow or later"` |
| `now` at or after 14:00 Warsaw on the day before delivery | 422 | `"Order deadline passed (14:00 Europe/Warsaw on the previous day)"` |
| Unknown `store_id` | 404 | Message names the missing store. |
| Unknown `product_id` | 404 | Message lists the missing ids. |
| Inactive product | 422 | Message lists the product names. |
| Same `product_id` twice in `items` | 422 | Message says the product is duplicated. |
| `quantity` of 0 or less, empty `items`, bad date or JSON | 422 | FastAPI validation list, not a string. |
| Database rejects the insert | 409 | String message, after `rollback`. |

## 4. `GET /production-plan?date=YYYY-MM-DD`

Returns how many pieces to bake for one delivery date, grouped by category.

**Files:** `services/plan.py` (`build_plan`), `api/plan.py`, schemas in `db/schemas.py`.

### Query

`date` is required. A missing value or a value that is not `YYYY-MM-DD` is a validation 422.

In the route, name the Python parameter `day` and expose it as `date`:

```python
day: Annotated[date, Query(alias="date")]
```

The response schema keeps the JSON key `date`, but the annotation must not reuse the imported name `date` as both the field and the type. With postponed annotations the string `"date"` is resolved later, in a namespace where that name can already mean the field, so the type is no longer reliably `datetime.date`. Annotate the field as `datetime.date`:

```python
import datetime as dt

class ProductionPlanOut(BaseModel):
    date: dt.date
```

The HTTP contract is unchanged: `?date=2026-10-21` in the query string and `"date"` in the JSON body. The specification's route sketch uses a parameter named `date`; this name is the one that avoids the collision.

### Response `200`

`ProductionPlanOut`:

| Field | Type |
| --- | --- |
| `date` | the requested delivery date |
| `categories` | array of `PlanCategoryOut`, ordered by category name |
| `categories[].category` | string |
| `categories[].total` | int, sum of `items[].quantity` in that category |
| `categories[].items` | array of `PlanItemOut`, ordered by product name |
| `items[].product_id` | int |
| `items[].name` | string |
| `items[].quantity` | int, `0` when the product is active and nobody ordered it |

```json
{
  "date": "2026-10-21",
  "categories": [
    {
      "category": "Bułki",
      "total": 120,
      "items": [{ "product_id": 6, "name": "Kajzerka", "quantity": 100 }]
    }
  ]
}
```

A date with no orders is still `200`. Every active product is listed with `quantity: 0`. The empty-state copy ("Brak zamówień na ten dzień") is a frontend decision, not a different HTTP status.

### Business logic

`build_plan(db, day)` runs one SQL query. Aggregation happens in the database. Python only groups the already sorted rows and sums each category.

Who is included:

- Every active product, including those with no orders for `date` (`quantity` 0).
- An inactive product only when `quantity` for that date is greater than 0. It may have been deactivated after the order was accepted, and it still has to be baked.
- An inactive product with no orders for that date is omitted. In the seed those are "Chleb razowy" and "Rogal z makiem" on a day nobody ordered them.

```sql
SELECT p.id, p.name, p.category, COALESCE(sq.qty, 0) AS quantity
FROM products p
LEFT JOIN (
    SELECT oi.product_id, SUM(oi.quantity) AS qty
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.delivery_date = :date
    GROUP BY oi.product_id
) sq ON sq.product_id = p.id
WHERE p.active OR COALESCE(sq.qty, 0) > 0
ORDER BY p.category, p.name;
```

The date filter sits in the subquery, on the join of `order_items` and `orders`. It is not an outer `WHERE` on the product join. An outer filter on the date would turn the `LEFT JOIN` into an inner join and drop products that have no orders. The outer `WHERE p.active OR qty > 0` still keeps an active product whose `sq.qty` is `NULL`, because `p.active` stays true.

`SUM` runs inside the subquery, before products are joined, so the join cannot multiply quantities (one product row matches at most one aggregated row). `COALESCE(sq.qty, 0)` turns a missing aggregate into zero. Orders for any other `delivery_date` are excluded by the subquery `WHERE`. Several orders, including several from the same store, add together through `SUM`.

The query uses the index on `orders.delivery_date` and the index on `order_items.product_id`.

`build_plan` then walks the rows with `itertools.groupby` on `category` and sets `total` to the sum of quantities in the group. Only the plan route calls it.

## 5. Mapping to code

| Endpoint | Route | Logic | Schemas |
| --- | --- | --- | --- |
| `GET /health` | `main.py` | none | inline `dict[str, str]` |
| `GET /stores`, `GET /products` | `api/catalog.py` (moved from `main.py`) | query in the route, as today | `StoreOut`, `ProductOut` (present) |
| `POST /orders` | `api/orders.py` | `services/orders.py` `create_order` | `OrderIn`, `OrderItemIn`, `OrderOut`, `OrderItemOut` (present) |
| `GET /production-plan` | `api/plan.py` | `services/plan.py` `build_plan` | `ProductionPlanOut`, `PlanCategoryOut`, `PlanItemOut` (missing) |

Shared pieces: `errors.py` (`DomainError`, `NotFoundError`, `BusinessRuleError`), exception handlers in `main.py`, and `clock.py` (`get_now`, `cutoff_for`, `is_before_cutoff`). `api/deps.py` defines `DbSession` and `Now`.

## 6. Not verified

These points are not confirmed by a run. Green SQLite tests would not settle them either.

- `created_at` is `DateTime(timezone=True)`. SQLite often returns that value without an offset, so `OrderOut.created_at` in the test client may not look like `2026-10-19T11:44:00+02:00`. Check the same response on PostgreSQL.
- The plan query and the `CHECK` / `UNIQUE` / foreign-key constraints need a manual check on PostgreSQL (`docker compose up --build`, then `/docs` or `curl`). The specification's tests run on in-memory SQLite.
