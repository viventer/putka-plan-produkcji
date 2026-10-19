# Change specification – Putka, production plan

List of features and changes needed to complete tasks 1–7 from `README.md`.
The bonus (background CSV export or a Redis cache) is out of scope.

## 0. Starting point (checked in the code)

- `backend/app/models.py`: only `Store` and `Product` (`active`, `unit_price: Numeric(10, 2)`, `category` with an index). No order tables.
- `backend/app/main.py`: `/health`, `/stores`, `/products`. Endpoints are synchronous (`def`), session via `db: Session = Depends(get_db)` (no `Annotated`).
- `backend/app/cutoff.py`: `CUTOFF_TIME_UTC = time(12, 0)`, a fixed hour in UTC.
- `backend/tests/`: `conftest.py` (in-memory SQLite, `db` and `client` fixtures), `test_cutoff.py`, `test_products.py`.
- Frontend: `App.tsx` + `ProductList.tsx`. `fetchJson<T>` casts the response without validation. Zod is not installed.
- `docker-compose.yml`: a `redis` service and `REDIS_URL` in the backend container. The code does not use it, and we do not touch that part.

## Decisions to make before implementation

- [x] New frontend dependency: `zod` (required by `AGENTS.md`).
- [x] Skeleton changes: split `backend/app/` into `api/`, `services/`, and shared modules (section "Package layout").
- [x] `POST /orders` contract (section 2).
- [x] Error codes: 404 for a missing store or product, 422 for a business-rule violation and for a bad payload (alternative: 409 for business rules).
- [x] Whether one store may place several orders for the same day (default: yes, no `UNIQUE(store_id, delivery_date)`).
- [x] Which products the plan shows: every active product (including quantity 0), and an inactive product only when it has orders for that date. An inactive product with no orders for that date is left out of the plan.
- [x] Order form in React: skip it.

## Package layout `backend/app`

Today everything sits side by side in the directory: routes, models, schemas, seed, and cutoff. Adding `orders.py`, `plan.py`, `errors.py`, and `clock.py` next to them mixes routes with logic. The target layout separates three things and does not go deeper.

```text
backend/app/
  main.py            # app, lifespan, CORS, error handlers, include_router
  db/
    db.py            # engine, SessionLocal, Base, get_db
    models.py        # Store, Product, Order, OrderItem
    schemas.py       # all *In and *Out
    seed.py
  errors.py          # DomainError, NotFoundError, BusinessRuleError
  clock.py           # Europe/Warsaw, get_now, cutoff_for, is_before_cutoff
  api/
    deps.py          # DbSession and Now: Annotated[..., Depends(...)] aliases
    catalog.py       # GET /stores, GET /products (moved out of main.py)
    orders.py        # POST /orders
    plan.py          # GET /production-plan
  services/
    orders.py        # create_order
    plan.py          # build_plan
```

- **Routes stay thin.** `APIRouter` has no prefix, so the paths remain `/orders` and `/production-plan`. A router only accepts a schema, calls a function from `services/`, and returns `*Out`.
- **Logic does not import FastAPI.** `services/` receives a `Session`, the payload, and `now`. Tests can call `create_order` and `build_plan` without HTTP, and endpoint tests still go through `client`.
- **Models and schemas each stay in one file.** There are few of them, and the plan and orders use the same classes. A package per domain would be the same files plus imports in a circle.
- **Database modules live in** `db/`. Imports use the full path: `app.db.db`, `app.db.models`, `app.db.schemas`, `app.db.seed`.
- **Time lives in** `clock.py`. `cutoff.py` moves there in full (the section 3 fix plus `get_now`). Tests change the import from `app.cutoff` to `app.clock`. A separate `clock.py` next to `cutoff.py` would duplicate the time zone.
- `create_all` **sees the new tables.** `main.py` imports the routers when the module loads, routers import services, services import models. `Order` and `OrderItem` are then registered on `Base` before `lifespan` calls `create_all`.
- **What we do not do:** a repository layer, a package per table, Alembic.

`deps.py`:

```python
DbSession = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]
```

`app.dependency_overrides[get_now]` still works, because the alias points at the same function.

---

## 1. Order model (task 1)

**Files:** `backend/app/db/models.py`, `backend/app/db/db.py`

### 1.1 Table `orders` (`Order`)

- `id: Mapped[int]`, primary key.
- `store_id: Mapped[int]`, `ForeignKey("stores.id")`, `nullable=False`.
- `delivery_date: Mapped[date]`, `index=True`. The production plan filters on this column.
- `created_at: Mapped[datetime]`, `DateTime(timezone=True)`. The value comes from the injected "now", not from `server_default`, so tests can set it.
- Relationship `items: Mapped[list["OrderItem"]]` with `cascade="all, delete-orphan"`, so one `db.add(order)` saves the order and its lines.

### 1.2 Table `order_items` (`OrderItem`)

- `id`, `order_id` (`ForeignKey("orders.id", ondelete="CASCADE")`), `product_id` (`ForeignKey("products.id")`). All `nullable=False`.
- `quantity: Mapped[int]`.
- `unit_price: Mapped[Decimal]`, `Numeric(10, 2)`. The price is copied from `Product.unit_price` at order time, so a later price-list change does not rewrite history.
- `__table_args__`:
  - `CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive")`,
  - `UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product")`, so each product appears once per order.
- Index on `product_id` (plan rows are joined on it). `order_id` is the first column of the unique index, so it does not need its own.

### 1.3 Foreign keys in SQLite (tests)

- SQLite does not enforce foreign keys by default. In `db.py`, for the SQLite engine, add an `event.listens_for(engine, "connect")` listener that runs `PRAGMA foreign_keys=ON`.
- SQLite enforces CHECK and UNIQUE with no extra configuration.

### 1.4 Migration

- No Alembic: `create_all` creates the tables. `create_all` does not alter existing tables, but these are new, so they appear immediately. Clean database start: `docker compose down -v`.

---

## 2. `POST /orders` (task 2)

**Files:** `backend/app/db/schemas.py`, `backend/app/services/orders.py`, `backend/app/errors.py`, `backend/app/api/orders.py`, `backend/app/api/deps.py`, `backend/app/clock.py` (`get_now`), `backend/app/main.py` (error handler and `include_router`).

### 2.1 Contract

Request:

```json
{
  "store_id": 1,
  "delivery_date": "2026-10-21",
  "items": [{ "product_id": 3, "quantity": 20 }]
}
```

Response `201 Created`: `OrderOut`:

```json
{
  "id": 7,
  "store_id": 1,
  "delivery_date": "2026-10-21",
  "created_at": "2026-10-19T11:44:00+02:00",
  "items": [{ "product_id": 3, "quantity": 20, "unit_price": "11.50" }]
}
```

### 2.2 Schemas (Pydantic v2)

- `OrderItemIn`: `product_id: int`, `quantity: int = Field(gt=0)`.
- `OrderIn`: `store_id: int`, `delivery_date: date`, `items: list[OrderItemIn] = Field(min_length=1)`.
- `OrderItemOut`, `OrderOut`: `ConfigDict(from_attributes=True)`, same as the existing `*Out`.
- Bad JSON, date, or number format, `quantity <= 0`, and an empty `items` list automatically return 422 from FastAPI validation.

### 2.3 Time as a dependency

- `get_now() -> datetime` returns `datetime.now(ZoneInfo("Europe/Warsaw"))`.
- The route takes `now: Annotated[datetime, Depends(get_now)]`. Tests replace the clock with `app.dependency_overrides[get_now] = lambda: ...`.

### 2.4 Logic of `create_order(db: Session, payload: OrderIn, now: datetime) -> Order`

Validation order. Each rule raises a domain exception before any write.

1. **Delivery date:** `today = now.astimezone(WAW).date()`. If `delivery_date <= today`, business error "Delivery date must be tomorrow or later". The Warsaw calendar date counts, not the server date and not UTC.
2. **Cutoff:** `if not is_before_cutoff(delivery_date, now)` raises "Order deadline passed (14:00 Europe/Warsaw on the previous day)". Requires the fix from section 3.
3. **Store:** `db.get(Store, store_id)`. If it is missing, `NotFoundError`.
4. **Duplicates in the payload:** if `product_id` repeats in `items`, 422 (no silent merging of quantities). This matches the `UNIQUE(order_id, product_id)` constraint in the database.
5. **Products:** one query `select(Product).where(Product.id.in_(ids))`, no N+1.
   - missing IDs raise `NotFoundError` with the list of IDs,
   - inactive products raise a business error with the list of names.
6. **Write:** `Order(..., created_at=now, items=[OrderItem(product_id, quantity, unit_price=product.unit_price)])`, then `db.add`, `db.commit`, `db.refresh`.

**Transactions:** validation and the write happen in one session and one `commit()`. Any exception before the commit means nothing is left in the database. `try/except` with `db.rollback()` also covers an `IntegrityError` from the database (for example a race with product deactivation, or a foreign-key violation), which we map to 409.

### 2.5 Domain errors and their mapping

- `errors.py`: `class DomainError(Exception)`, and from it `NotFoundError` and `BusinessRuleError`. Each has a clear message.
- `main.py`: `@app.exception_handler(NotFoundError)` returns 404, `BusinessRuleError` returns 422 (or 409, depending on the decision).
- The error body has the same shape as FastAPI's default errors: `{"detail": "..."}`. No stack traces, and unexpected exceptions are logged with `logging`.

### 2.6 Route

In `api/orders.py`. `main.py` only does `app.include_router(orders.router)`.

```python
router = APIRouter()

@router.post("/orders", response_model=OrderOut, status_code=201)
def post_order(payload: OrderIn, db: DbSession, now: Now) -> OrderOut:
    return OrderOut.model_validate(create_order(db, payload, now))
```

---

## 3. Red test (task 3)

**File today:** `backend/app/cutoff.py`. The fix lands in `backend/app/clock.py` (see the package layout), and only after your approval. Until the move, the diagnosis is about the current `cutoff.py`.

- **Diagnosis (from reading the code, not yet confirmed by running** `pytest`**):** `cutoff_for` combines the date with `time(12, 0)` in UTC.
  - Summer, CEST (UTC+2): 12:00 UTC is 14:00 in Warsaw, so the summer tests pass.
  - Winter, CET (UTC+1): 12:00 UTC is 13:00 in Warsaw. An order at 13:30 is rejected, so `test_winter_order_before_cutoff_is_accepted` fails.
- **Why the test caught it:** it is the only winter test with an hour between 13:00 and 14:00, the window where a fixed UTC offset gives the wrong result.
- **Fix:** define the cutoff in local time:
  - `WARSAW = ZoneInfo("Europe/Warsaw")`, `CUTOFF_TIME = time(14, 0)`,
  - `datetime.combine(order_day, CUTOFF_TIME, tzinfo=WARSAW)`,
  - comparison `now < cutoff` (both datetimes are timezone-aware; Python compares them as instants).
- The `now.tzinfo is None` check (`ValueError`) stays.

---

## 4. `GET /production-plan?date=YYYY-MM-DD` (task 4)

**Files:** `backend/app/services/plan.py`, `backend/app/api/plan.py`, `backend/app/db/schemas.py`.

### 4.1 Response

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

Schemas: `PlanItemOut`, `PlanCategoryOut`, `ProductionPlanOut`.

### 4.2 Query: one query, aggregation in SQL

Target SQL:

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

- **Who appears in the plan.** An active product is always there, with `0` when nobody ordered it that day. An inactive product is there only when it already has lines for that date (`qty > 0`): the product may have been turned off after the order was accepted, and it still has to be baked. An inactive product with no orders for that date is dropped. The seed has two such products on a normal day: "Chleb razowy" and "Rogal z makiem".
- The date filter is in the subquery (`WHERE` already applies to the join of orders and lines), not in the outer `WHERE` on the join with products. The outer `WHERE p.active OR qty > 0` does not drop active products with zero, because `p.active` stays true when `sq.qty` is `NULL`.
- The sum is computed in the subquery before products are joined, so the join does not multiply quantities. `COALESCE(sq.qty, 0)` turns a missing row into zero.
- In SQLAlchemy: subquery `select(OrderItem.product_id, func.sum(OrderItem.quantity).label("qty")).join(Order).where(Order.delivery_date == day).group_by(OrderItem.product_id).subquery()`, then `select(...).outerjoin(...).where(or_(Product.active.is_(True), func.coalesce(sq.c.qty, 0) > 0))`.

### 4.3 Grouping and the API

- `build_plan(db: Session, day: date) -> ProductionPlanOut` groups in Python the rows already sorted by SQL (`itertools.groupby` on `category`) and computes each category `total`. Only the plan route calls it.
- Route in `api/plan.py`: `@router.get("/production-plan", response_model=ProductionPlanOut)` with parameter `date: Annotated[date, Query()]` and `db: DbSession`. A missing parameter or a bad format returns 422.

---

## 5. "Plan produkcji" view in React (task 5)

**Files:** `frontend/src/api.ts`, new `frontend/src/ProductionPlan.tsx`, possibly `frontend/src/PlanCategoryRows.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/package.json` (`zod`).

### 5.1 API layer

- `fetchJson<T>(path, schema: z.ZodType<T>, init?)`: `schema.parse(await response.json())`. A response that does not match the API ends in a clear error, not a silent `undefined`.
- Zod schemas: `ProductSchema`, `ProductionPlanSchema`, and types via `z.infer`. The hand-written `Product` type is replaced by the Zod type, and `ProductList` moves to the new signature.
- HTTP error: read the `detail` field from the response body so the message is readable.

### 5.2 `ProductionPlan` component

- `<input type="date">`, default "tomorrow" on the Warsaw calendar (`Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Warsaw" })` yields `YYYY-MM-DD`).
- `useEffect` depends on the date. An `AbortController` in the cleanup stops a late response for the old date from overwriting the new one.
- States:
  - **loading:** "Ładowanie…",
  - **error:** `<p className="error">` with the message,
  - **empty:** every quantity equal to 0 shows "Brak zamówień na ten dzień" (the table of zeros may stay underneath).
- Table: a category header row, product rows (`.num` for quantities), and a category total row.
- One component per file, no `useMemo`/`useCallback`, no UI libraries.

### 5.3 `App.tsx`

- A new "Plan produkcji" section (for example above "Aktywne produkty").

---

## 6. Tests (task 6)

**Files:** `backend/tests/test_cutoff.py` (extended), new `test_orders.py` and `test_production_plan.py`, possibly fixtures or helpers in `conftest.py`.

### 6.1 Cutoff (`is_before_cutoff`)

- Winter: 13:59 accepted (existing test), 14:00 rejected, 14:01 rejected.
- Summer: existing tests (13:59, 14:00, 16:30).
- `now` given in UTC (for example 12:59 UTC in winter is 13:59 in Warsaw, so accepted).
- DST change days: delivery 2027-03-29 (order on 28 March, the switch to CEST) and 2027-11-01 (order on 31 October, the switch to CET).

### 6.2 `POST /orders` (through `client`, with `get_now` overridden)

- A valid order: 201, `unit_price` equal to the product price, rows in the database.
- `delivery_date` today and yesterday: 422.
- After the cutoff (14:00 on the previous day): 422.
- An inactive product (for example "Chleb razowy"): 422 and **zero** rows in `orders` and `order_items` (no partial write).
- A missing store or product: 404 and no write.
- `quantity = 0`, a negative value, empty `items`, a bad date format: 422.
- A duplicated `product_id` in the payload: 422.
- Optional model test: a direct `OrderItem(quantity=0)` through `db` raises `IntegrityError`, which confirms CHECK.

### 6.3 Production plan

- Several stores order the same product: quantities are summed.
- Several products in several categories: correct grouping, order, and `total`.
- An active product with no orders for that date is on the list with `quantity == 0`.
- An inactive product with no orders for that date (in the seed, "Chleb razowy" and "Rogal z makiem") is absent from the response.
- An inactive product with an order for that date is on the list with the summed quantity. Rows are inserted directly through `db`, because `POST /orders` will not accept that product.
- Orders for a different date are not included.
- A missing or invalid `date` parameter: 422.
- Orders are inserted directly through the `db` fixture, so plan tests do not depend on the clock or the cutoff.

### 6.4 Limits

- Tests run on SQLite and do not prove PostgreSQL compatibility. The plan query and the constraints have to be checked by hand on Postgres (`docker compose up --build`, `/docs`, or `curl`).

---

## 7. `NOTES.md` (task 7): suggested contents

You fill in the file yourself. Below is only a suggestion of what can go in it.

- **How to run:** `docker compose down -v` after a model change, new frontend dependency (`zod`). Redis stays in compose, but the application does not use it.
- **Cause of the red test:** a fixed 12:00 UTC instead of 14:00 Europe/Warsaw, wrong only in CET. The winter test at 13:30 falls in the 13:00–14:00 window. Fix: `datetime.combine(..., tzinfo=ZoneInfo("Europe/Warsaw"))`.
- **How I used AI:** the tool (Cursor, plan mode and agent mode), `AGENTS.md` as the rule set, example prompts (for example the one for this specification).
- **What I checked by hand:** `pytest` before the fix and after it, the plan query on PostgreSQL, error responses in `/docs`, the view in the browser (loading, error, and empty state).
- **Where AI was wrong:** for example the first version of the plan sketched `products LEFT JOIN orders` with no link to the order line, which would have multiplied quantities. Write your own observations here.
- **Skeleton changes:** split into `api/` and `services/`, move of `cutoff.py` into `clock.py` (import in tests), move of `/stores` and `/products` from `main.py` to `api/catalog.py`, `PRAGMA foreign_keys` listener for SQLite, `zod` dependency.
- **What next:** the bonus (plan export to CSV as a background job on Redis + RQ with a status, or a plan cache in Redis), Alembic, tests on real Postgres (testcontainers), the decision about uniqueness of an order per store and day, editing and cancelling orders before the cutoff, store authorization, an order form in React.

---

## Work order

Each step is its own small commit after your approval. After each step, `docker compose exec backend pytest`, and after frontend changes, `npm run build`.

1. Confirm the red test (`pytest`), then the cutoff fix in `cutoff.py` and the boundary tests. The move to `clock.py` waits until step 2, so the fix diff stays readable.
2. Package layout: `errors.py`, `clock.py` (contents of `cutoff.py` plus `get_now`), `api/deps.py`, `api/catalog.py`. `Order` and `OrderItem` models and `PRAGMA foreign_keys` for SQLite.
3. `POST /orders`: schemas, `services/orders.py`, `api/orders.py`, domain errors, and tests.
4. `GET /production-plan`: `build_plan` and aggregation tests.
5. Frontend: Zod, `ProductionPlan`, and view states.
6. Manual check on Postgres and in the browser; you fill in the material for `NOTES.md`.
