## Role

- You assist me with a Putka recruitment assignment (`README.md`). I own key decisions and the final result; do not solve the whole assignment autonomously.
- Workflow: analyze → short plan → my approval → implement in small steps → verify → summarize.
- Ask before: data model changes, API contract changes, new dependencies, changes to the skeleton (structure, tooling). Decide minor details yourself, following existing code.
- When I ask about an approach, explain the problem and options first; do not jump to code.
- Separate verified facts from assumptions. Never claim a check passed unless you ran it; report what was not verified.
- Reply in Polish; keep code, identifiers and comments in English.
- Don't edit anything in NOTES.md

## Project

- Backend: FastAPI (sync), SQLAlchemy 2.0 (`Mapped`, `mapped_column`, sync `Session` via `get_db`), psycopg, PostgreSQL 16, Pydantic v2, pip + `requirements.txt`.
- Tables via `Base.metadata.create_all` at startup, seed in `app/seed.py`. Reset DB: `docker compose down -v`.
- Layout: `backend/app/` (`main.py` routes, `models.py`, `schemas.py`, `db.py`, `cutoff.py`, `seed.py`), `backend/tests/` (in-memory SQLite, fixtures in `conftest.py`).
- Frontend: React 18.3 + Vite + TypeScript, plain CSS (`src/index.css`), API helper `src/api.ts`.
- Commands: `docker compose up --build`; `docker compose exec backend pytest`; `cd frontend && npm run build` (includes `tsc` type check).

## Scope

- Scope = README tasks 1–7. Bonus (Redis) only if I explicitly ask. Time budget ~2h: prefer the simplest correct solution, no unrelated refactors.
- Keep the existing endpoint shape: `POST /orders`, `GET /production-plan?date=YYYY-MM-DD` (no `/api/v1` prefix).
- Red test (task 3): help me diagnose, do not fix it without my approval.
- Never commit without my approval. Commits are small and descriptive; history is not squashed.
- Note skeleton changes, manual checks and AI mistakes for `NOTES.md`.

## Backend

- Full type hints, no `Any`. Dependencies via `Annotated[Session, Depends(get_db)]`.
- Thin routes: validate input, call business logic in a separate module, return a schema. Always set `response_model`; never return ORM objects directly.
- Schemas separate from ORM models; follow existing naming (`*Out`, add `*In` for input).
- Domain errors raised in logic, mapped to HTTP in routes/handlers. Consistent error body, clear messages, no stack traces. Use 404 (missing store/product), 409 or 422 (business rule violation), 422 (invalid payload) — consistently.
- Money as `Decimal` / `Numeric(10, 2)`, never float. Use `logging`, never `print`.
- Avoid N+1 queries; index columns used for filtering (e.g. `delivery_date`).

## Business rules

- Local time rules use `ZoneInfo("Europe/Warsaw")`; never the server timezone or naive datetimes. Pass "now" in as a parameter/dependency so it is testable.
- `delivery_date` >= tomorrow (Warsaw calendar date).
- Order deadline: before 14:00 Warsaw time on the day before delivery; exactly 14:00 is rejected. Must hold in both CET and CEST.
- Only active products; validate on the backend. Validation and all inserts in one transaction — a failed order leaves no rows.
- Order items: FK to order and product, `CHECK quantity > 0`, unique `(order_id, product_id)`, `unit_price` copied from the product at order time.
- Production plan: sum `quantity` per product for the given `delivery_date`, aggregated in SQL, grouped by category. Include every product (0 if no orders): `LEFT JOIN` with the date filter in `ON`, not `WHERE`. Joins must not multiply quantities.

## Frontend

- TypeScript only, no `any`. Parse API responses with Zod.
- Use the existing plain CSS; no UI libraries. One component per file.
- Every data view handles loading, error and empty states.
- No `useMemo` / `useCallback` / `React.memo` without a stated reason.

## Tests

- Cover: cutoff before / exactly at / after 14:00 in winter and summer, invalid delivery dates; inactive product rejected; no partial writes on failure; plan aggregation across many orders, products, categories, and products without orders.
- Use the existing fixtures (`db`, `client`) and in-memory SQLite.
- SQLite ≠ PostgreSQL: FKs are not enforced unless `PRAGMA foreign_keys=ON`; types and SQL behavior differ. Do not treat green SQLite tests as proof of Postgres compatibility.
- Run relevant tests after each change and the full suite before finishing.
