# Specyfikacja zmian – Putka, plan produkcji

Lista funkcjonalności i zmian potrzebnych do realizacji zadań 1–7 z `README.md`.
Bonus (eksport CSV w tle albo cache w Redisie) jest poza zakresem.

## 0. Stan wyjściowy (sprawdzony w kodzie)

- `backend/app/models.py`: tylko `Store` i `Product` (`active`, `unit_price: Numeric(10, 2)`, `category` z indeksem). Brak tabel zamówień.
- `backend/app/main.py`: `/health`, `/stores`, `/products`. Endpointy są synchroniczne (`def`), sesja przez `db: Session = Depends(get_db)` (bez `Annotated`).
- `backend/app/cutoff.py`: `CUTOFF_TIME_UTC = time(12, 0)`, czyli stała godzina w UTC.
- `backend/tests/`: `conftest.py` (SQLite w pamięci, fixture'y `db` i `client`), `test_cutoff.py`, `test_products.py`.
- Frontend: `App.tsx` + `ProductList.tsx`. `fetchJson<T>` rzutuje odpowiedź bez walidacji, Zod nie jest zainstalowany.
- `docker-compose.yml`: jest serwis `redis` i `REDIS_URL` w kontenerze backendu. Kod z niego nie korzysta i w tym zakresie go nie ruszamy.

## Decyzje do podjęcia przed implementacją

- [x] Nowa zależność frontendu: `zod` (wymagana przez `AGENTS.md`).
- [x] Zmiany w szkielecie: podział `backend/app/` na `api/`, `services/` i moduły wspólne (sekcja „Układ pakietu”).
- [ ] Kontrakt `POST /orders` (sekcja 2).
- [ ] Kody błędów: 404 dla brakującego sklepu lub produktu, 422 dla naruszenia reguły biznesowej i dla złego payloadu (alternatywa: 409 dla reguł biznesowych).
- [ ] Czy dopuszczamy kilka zamówień jednego sklepu na ten sam dzień (domyślnie tak, bez `UNIQUE(store_id, delivery_date)`).
- [ ] Które produkty pokazuje plan: wszystkie aktywne oraz nieaktywne, ale tylko jeśli mają zamówienia na daną datę (rekomendacja), czy po prostu wszystkie.
- [x] Formularz zamówienia w React: pomijamy.

## Układ pakietu `backend/app`

Dziś w katalogu leży wszystko obok siebie: trasy, modele, schematy, seed i cutoff. Dopisanie `orders.py`, `plan.py`, `errors.py` i `clock.py` obok nich miesza trasy z logiką. Docelowy układ rozdziela trzy rzeczy i nie idzie głębiej.

```text
backend/app/
  main.py            # aplikacja, lifespan, CORS, handlery błędów, include_router
  db.py              # engine, SessionLocal, Base, get_db
  models.py          # Store, Product, Order, OrderItem
  schemas.py         # wszystkie *In i *Out
  seed.py
  errors.py          # DomainError, NotFoundError, BusinessRuleError
  clock.py           # Europe/Warsaw, get_now, cutoff_for, is_before_cutoff
  api/
    deps.py          # DbSession i Now: aliasy Annotated[..., Depends(...)]
    catalog.py       # GET /stores, GET /products (wyniesione z main.py)
    orders.py        # POST /orders
    plan.py          # GET /production-plan
  services/
    orders.py        # create_order
    plan.py          # build_plan
```

- **Trasy są cienkie.** `APIRouter` bez prefiksu, więc adresy zostają `/orders` i `/production-plan`. Router tylko przyjmuje schemat, woła funkcję z `services/` i zwraca `*Out`.
- **Logika nie importuje FastAPI.** `services/` dostaje `Session`, payload i `now`. Testy mogą wołać `create_order` i `build_plan` bez HTTP, a testy endpointów dalej idą przez `client`.
- **Modele i schematy zostają w jednym pliku każdy.** Jest ich mało, a plan i zamówienia korzystają z tych samych klas. Rozbicie na pakiet per domena dawałoby te same pliki plus importy w kółko.
- **Czas jest w `clock.py`.** `cutoff.py` przechodzi tam w całości (poprawka z sekcji 3 plus `get_now`). Testy zmieniają import z `app.cutoff` na `app.clock`. Osobny `clock.py` obok `cutoff.py` dublowałby strefę czasową.
- **`create_all` widzi nowe tabele.** `main.py` importuje routery przy starcie modułu, routery importują serwisy, serwisy importują modele. `Order` i `OrderItem` są wtedy zarejestrowane na `Base` zanim `lifespan` wywoła `create_all`.
- **Czego nie robimy:** warstwy repozytoriów, pakietu per tabela, Alembica.

`deps.py`:

```python
DbSession = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]
```

`app.dependency_overrides[get_now]` dalej działa, bo alias wskazuje na tę samą funkcję.

---

## 1. Model zamówień (zadanie 1)

**Pliki:** `backend/app/models.py`, `backend/app/db.py`

### 1.1 Tabela `orders` (`Order`)

- `id: Mapped[int]`, klucz główny.
- `store_id: Mapped[int]`, `ForeignKey("stores.id")`, `nullable=False`.
- `delivery_date: Mapped[date]`, `index=True`. Plan produkcji filtruje po tej kolumnie.
- `created_at: Mapped[datetime]`, `DateTime(timezone=True)`. Wartość pochodzi ze wstrzykniętego "now", a nie z `server_default`, żeby dało się ją ustawić w testach.
- Relacja `items: Mapped[list["OrderItem"]]` z `cascade="all, delete-orphan"`, dzięki czemu zamówienie i pozycje zapisuje jeden `db.add(order)`.

### 1.2 Tabela `order_items` (`OrderItem`)

- `id`, `order_id` (`ForeignKey("orders.id", ondelete="CASCADE")`), `product_id` (`ForeignKey("products.id")`). Wszystkie `nullable=False`.
- `quantity: Mapped[int]`.
- `unit_price: Mapped[Decimal]`, `Numeric(10, 2)`. Cena jest kopiowana z `Product.unit_price` w chwili zamówienia, więc późniejsza zmiana cennika nie zmienia historii.
- `__table_args__`:
  - `CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive")`,
  - `UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product")`, czyli jeden produkt raz na zamówienie.
- Indeks na `product_id` (wiersze są złączane po nim w planie). `order_id` jest pierwszą kolumną unikalnego indeksu, więc nie potrzebuje osobnego.

### 1.3 Klucze obce w SQLite (testy)

- SQLite domyślnie nie wymusza FK. W `db.py`, dla silnika SQLite, dodać listener `event.listens_for(engine, "connect")`, który wykonuje `PRAGMA foreign_keys=ON`.
- CHECK i UNIQUE SQLite wymusza bez dodatkowej konfiguracji.

### 1.4 Migracja

- Bez Alembica: tabele tworzy `create_all`. `create_all` nie zmienia istniejących tabel, ale te są nowe, więc powstaną od razu. Czysty start bazy: `docker compose down -v`.

---

## 2. `POST /orders` (zadanie 2)

**Pliki:** `backend/app/schemas.py`, `backend/app/services/orders.py`, `backend/app/errors.py`, `backend/app/api/orders.py`, `backend/app/api/deps.py`, `backend/app/clock.py` (`get_now`), `backend/app/main.py` (handler błędów i `include_router`).

### 2.1 Kontrakt

Żądanie:

```json
{
  "store_id": 1,
  "delivery_date": "2026-10-21",
  "items": [{ "product_id": 3, "quantity": 20 }]
}
```

Odpowiedź `201 Created`: `OrderOut`:

```json
{
  "id": 7,
  "store_id": 1,
  "delivery_date": "2026-10-21",
  "created_at": "2026-10-19T11:44:00+02:00",
  "items": [{ "product_id": 3, "quantity": 20, "unit_price": "11.50" }]
}
```

### 2.2 Schematy (Pydantic v2)

- `OrderItemIn`: `product_id: int`, `quantity: int = Field(gt=0)`.
- `OrderIn`: `store_id: int`, `delivery_date: date`, `items: list[OrderItemIn] = Field(min_length=1)`.
- `OrderItemOut`, `OrderOut`: `ConfigDict(from_attributes=True)`, tak jak istniejące `*Out`.
- Zły format JSON, daty lub liczby, `quantity <= 0` i pusta lista `items` dają automatycznie 422 z walidacji FastAPI.

### 2.3 Czas jako zależność

- `get_now() -> datetime` zwraca `datetime.now(ZoneInfo("Europe/Warsaw"))`.
- Route przyjmuje `now: Annotated[datetime, Depends(get_now)]`. Testy podmieniają czas przez `app.dependency_overrides[get_now] = lambda: ...`.

### 2.4 Logika `create_order(db: Session, payload: OrderIn, now: datetime) -> Order`

Kolejność walidacji. Każda reguła rzuca wyjątek domenowy przed jakimkolwiek zapisem.

1. **Data dostawy:** `today = now.astimezone(WAW).date()`. Jeśli `delivery_date <= today`, błąd biznesowy "Delivery date must be tomorrow or later". Liczy się data kalendarzowa w Warszawie, a nie data serwera ani UTC.
2. **Cutoff:** `if not is_before_cutoff(delivery_date, now)` daje błąd "Order deadline passed (14:00 Europe/Warsaw on the previous day)". Wymaga poprawki z sekcji 3.
3. **Sklep:** `db.get(Store, store_id)`. Jeśli go brak, `NotFoundError`.
4. **Duplikaty w payloadzie:** jeśli `product_id` powtarza się w `items`, błąd 422 (bez cichego scalania ilości). Odpowiada to ograniczeniu `UNIQUE(order_id, product_id)` w bazie.
5. **Produkty:** jedno zapytanie `select(Product).where(Product.id.in_(ids))`, bez N+1.
   - brakujące ID dają `NotFoundError` z listą ID,
   - nieaktywne produkty dają błąd biznesowy z listą nazw.
6. **Zapis:** `Order(..., created_at=now, items=[OrderItem(product_id, quantity, unit_price=product.unit_price)])`, potem `db.add`, `db.commit`, `db.refresh`.

**Transakcyjność:** walidacja i zapis odbywają się w jednej sesji i jednym `commit()`. Każdy wyjątek przed commitem oznacza, że w bazie nic nie zostaje. `try/except` z `db.rollback()` zabezpiecza też przed `IntegrityError` z bazy (np. wyścig z dezaktywacją produktu albo naruszenie FK), który mapujemy na 409.

### 2.5 Błędy domenowe i ich mapowanie

- `errors.py`: `class DomainError(Exception)`, a z niego `NotFoundError` i `BusinessRuleError`. Każdy ma czytelny komunikat.
- `main.py`: `@app.exception_handler(NotFoundError)` zwraca 404, `BusinessRuleError` zwraca 422 (lub 409, zależnie od decyzji).
- Ciało błędu ma ten sam format co domyślne błędy FastAPI: `{"detail": "..."}`. Bez stack trace'ów, a nieoczekiwane wyjątki logujemy przez `logging`.

### 2.6 Route

W `api/orders.py`. `main.py` robi tylko `app.include_router(orders.router)`.

```python
router = APIRouter()

@router.post("/orders", response_model=OrderOut, status_code=201)
def post_order(payload: OrderIn, db: DbSession, now: Now) -> OrderOut:
    return OrderOut.model_validate(create_order(db, payload, now))
```

---

## 3. Czerwony test (zadanie 3)

**Plik dziś:** `backend/app/cutoff.py`. Poprawka ląduje w `backend/app/clock.py` (patrz układ pakietu), dopiero po Twojej akceptacji. Do czasu przeniesienia diagnoza dotyczy obecnego `cutoff.py`.

- **Diagnoza (z analizy kodu, jeszcze niepotwierdzona uruchomieniem** `pytest`**):** `cutoff_for` łączy datę z `time(12, 0)` w UTC.
  - Lato, CEST (UTC+2): 12:00 UTC to 14:00 w Warszawie, więc testy letnie przechodzą.
  - Zima, CET (UTC+1): 12:00 UTC to 13:00 w Warszawie. Zamówienie z 13:30 jest odrzucane, więc `test_winter_order_before_cutoff_is_accepted` nie przechodzi.
- **Dlaczego test to wyłapał:** to jedyny test zimowy z godziną między 13:00 a 14:00, czyli w oknie, w którym stały offset UTC daje zły wynik.
- **Poprawka:** cutoff definiowany w czasie lokalnym:
  - `WARSAW = ZoneInfo("Europe/Warsaw")`, `CUTOFF_TIME = time(14, 0)`,
  - `datetime.combine(order_day, CUTOFF_TIME, tzinfo=WARSAW)`,
  - porównanie `now < cutoff` (oba datetime'y ze strefą, Python porównuje je jako chwile w czasie).
- Kontrola `now.tzinfo is None` (`ValueError`) zostaje.

---

## 4. `GET /production-plan?date=YYYY-MM-DD` (zadanie 4)

**Pliki:** `backend/app/services/plan.py`, `backend/app/api/plan.py`, `backend/app/schemas.py`.

### 4.1 Odpowiedź

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

Schematy: `PlanItemOut`, `PlanCategoryOut`, `ProductionPlanOut`.

### 4.2 Zapytanie: jedno, agregacja w SQL

Docelowy SQL:

```sql
SELECT p.id, p.name, p.category, COALESCE(SUM(oi.quantity), 0) AS quantity
FROM products p
LEFT JOIN (order_items oi
           JOIN orders o ON o.id = oi.order_id AND o.delivery_date = :date)
       ON oi.product_id = p.id
GROUP BY p.id, p.name, p.category
ORDER BY p.category, p.name;
```

- Filtr daty jest w `ON`, a nie w `WHERE`. Warunek w `WHERE` zamieniłby `LEFT JOIN` w `INNER JOIN` i usunął produkty bez zamówień.
- Pozycje zamówień są złączane z zamówieniami **wewnątrz** `LEFT JOIN`, więc każda pozycja pojawia się raz i suma się nie mnoży. Bezpośrednie `products LEFT JOIN orders` bez związku z pozycją mnożyłoby wiersze.
- W SQLAlchemy: podzapytanie `select(OrderItem.product_id, func.sum(OrderItem.quantity)).join(Order).where(Order.delivery_date == day).group_by(OrderItem.product_id).subquery()`, a potem `select(Product..., func.coalesce(sq.c.qty, 0)).outerjoin(sq, sq.c.product_id == Product.id)`. Agregacja przed złączeniem też wyklucza mnożenie i jest czytelniejsza od zagnieżdżonego `JOIN`.
- Wybór produktów zależy od decyzji. Rekomendacja: `WHERE p.active OR qty > 0`.

### 4.3 Grupowanie i API

- `build_plan(db: Session, day: date) -> ProductionPlanOut` grupuje w Pythonie wiersze już posortowane przez SQL (`itertools.groupby` po `category`) i liczy `total` kategorii. Woła ją tylko route planu.
- Route w `api/plan.py`: `@router.get("/production-plan", response_model=ProductionPlanOut)` z parametrem `date: Annotated[date, Query()]` i `db: DbSession`. Brak parametru lub zły format daje 422.

---

## 5. Widok "Plan produkcji" w React (zadanie 5)

**Pliki:** `frontend/src/api.ts`, nowy `frontend/src/ProductionPlan.tsx`, ewentualnie `frontend/src/PlanCategoryRows.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/package.json` (`zod`).

### 5.1 Warstwa API

- `fetchJson<T>(path, schema: z.ZodType<T>, init?)`: `schema.parse(await response.json())`. Niezgodna odpowiedź API kończy się czytelnym błędem, a nie cichym `undefined`.
- Schematy Zod: `ProductSchema`, `ProductionPlanSchema`, a typy przez `z.infer`. Ręczny typ `Product` zastępuje typ z Zod, a `ProductList` przechodzi na nową sygnaturę.
- Błąd HTTP: odczyt pola `detail` z ciała odpowiedzi, żeby komunikat był czytelny.

### 5.2 Komponent `ProductionPlan`

- `<input type="date">`, domyślnie "jutro" według kalendarza w Warszawie (`Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Warsaw" })` daje `YYYY-MM-DD`).
- `useEffect` zależny od daty. `AbortController` w cleanupie zapobiega nadpisaniu nowej daty przez spóźnioną starą odpowiedź.
- Stany:
  - **ładowanie:** "Ładowanie…",
  - **błąd:** `<p className="error">` z komunikatem,
  - **pusty:** wszystkie ilości równe 0 dają komunikat "Brak zamówień na ten dzień" (tabela z zerami może zostać pod spodem).
- Tabela: wiersz nagłówka kategorii, wiersze produktów (`.num` dla ilości) i wiersz sumy kategorii.
- Jeden komponent na plik, bez `useMemo`/`useCallback`, bez bibliotek UI.

### 5.3 `App.tsx`

- Nowa sekcja "Plan produkcji" (np. nad "Aktywne produkty").

---

## 6. Testy (zadanie 6)

**Pliki:** `backend/tests/test_cutoff.py` (rozszerzenie), nowe `test_orders.py` i `test_production_plan.py`, ewentualnie fixture'y lub helpery w `conftest.py`.

### 6.1 Cutoff (funkcja `is_before_cutoff`)

- Zima: 13:59 przyjęte (istniejący test), 14:00 odrzucone, 14:01 odrzucone.
- Lato: istniejące testy (13:59, 14:00, 16:30).
- `now` podane w UTC (np. 12:59 UTC zimą to 13:59 w Warszawie, więc przyjęte).
- Dni zmiany czasu: dostawa 2027-03-29 (zamówienie 28.03, dzień przejścia na CEST) i 2027-11-01 (zamówienie 31.10, dzień przejścia na CET).

### 6.2 `POST /orders` (przez `client`, z podmienionym `get_now`)

- Poprawne zamówienie: 201, `unit_price` równe cenie produktu, wiersze w bazie.
- `delivery_date` dziś i wczoraj: 422.
- Po cutoffie (14:00 dnia poprzedniego): 422.
- Nieaktywny produkt (np. "Chleb razowy"): 422 i **zero** wierszy w `orders` i `order_items` (brak częściowego zapisu).
- Nieistniejący sklep lub produkt: 404 i brak zapisu.
- `quantity = 0`, wartość ujemna, puste `items`, zły format daty: 422.
- Zduplikowany `product_id` w payloadzie: 422.
- Opcjonalnie test modelu: bezpośredni `OrderItem(quantity=0)` przez `db` rzuca `IntegrityError`, co potwierdza CHECK.

### 6.3 Plan produkcji

- Kilka sklepów zamawia ten sam produkt: ilości się sumują.
- Kilka produktów w kilku kategoriach: poprawne grupowanie, kolejność i `total`.
- Produkty bez zamówień mają `quantity == 0`.
- Zamówienia na inną datę nie są wliczane.
- Brak lub zły parametr `date`: 422.
- Zamówienia wstawiane bezpośrednio przez fixture `db`, żeby testy planu nie zależały od zegara i cutoffu.

### 6.4 Ograniczenia

- Testy działają na SQLite i nie dowodzą zgodności z PostgreSQL. Zapytanie planu i ograniczenia trzeba sprawdzić ręcznie na Postgresie (`docker compose up --build`, `/docs` lub `curl`).

---

## 7. `NOTES.md` (zadanie 7): propozycje treści

Plik uzupełniasz sam. Poniżej tylko propozycje, co może się w nim znaleźć.

- **Jak uruchomić:** `docker compose down -v` po zmianie modelu, nowa zależność frontendu (`zod`). Redis zostaje w compose, ale aplikacja z niego nie korzysta.
- **Przyczyna czerwonego testu:** stała godzina 12:00 UTC zamiast 14:00 Europe/Warsaw, błąd tylko w CET. Test zimowy z 13:30 trafia w okno 13:00–14:00. Poprawka: `datetime.combine(..., tzinfo=ZoneInfo("Europe/Warsaw"))`.
- **Jak korzystałem z AI:** narzędzie (Cursor, tryb plan i agent), `AGENTS.md` jako zestaw reguł, przykładowe prompty (np. o tę specyfikację).
- **Co zweryfikowałem ręcznie:** wynik `pytest` przed poprawką i po niej, zapytanie planu na PostgreSQL, odpowiedzi błędów w `/docs`, widok w przeglądarce (ładowanie, błąd i stan pusty).
- **Gdzie AI się pomyliło:** np. pierwsza wersja planu miała szkic złączenia `products LEFT JOIN orders` bez związku z pozycją zamówienia, który mnożyłby ilości. Tu wpisujesz własne obserwacje.
- **Zmiany w szkielecie:** podział na `api/` i `services/`, przeniesienie `cutoff.py` do `clock.py` (import w testach), wyniesienie `/stores` i `/products` z `main.py` do `api/catalog.py`, listener `PRAGMA foreign_keys` dla SQLite, zależność `zod`.
- **Co dalej:** bonus (eksport planu do CSV jako zadanie w tle na Redis + RQ ze statusem, albo cache planu w Redisie), Alembic, testy na prawdziwym Postgresie (testcontainers), decyzja o unikalności zamówienia na sklep i dzień, edycja i anulowanie zamówień przed cutoffem, autoryzacja sklepów, formularz zamówienia w React.

---

## Kolejność prac

Każdy krok to osobny, mały commit po Twojej akceptacji. Po każdym kroku `docker compose exec backend pytest`, a po zmianach frontendu `npm run build`.

1. Potwierdzenie czerwonego testu (`pytest`), potem poprawka cutoffu w `cutoff.py` i testy brzegowe. Przeniesienie do `clock.py` dopiero w kroku 2, żeby diff poprawki był czytelny.
2. Układ pakietu: `errors.py`, `clock.py` (zawartość `cutoff.py` + `get_now`), `api/deps.py`, `api/catalog.py`. Modele `Order` i `OrderItem` oraz `PRAGMA foreign_keys` dla SQLite.
3. `POST /orders`: schematy, `services/orders.py`, `api/orders.py`, błędy domenowe i testy.
4. `GET /production-plan`: `build_plan` i testy agregacji.
5. Frontend: Zod, `ProductionPlan` i stany widoku.
6. Ręczna weryfikacja na Postgresie i w przeglądarce; materiał do `NOTES.md` uzupełniasz Ty.
