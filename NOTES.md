# NOTES

> Uzupełnij krótko – wystarczą punkty. To dla nas punkt wyjścia do rozmowy.

## Jak uruchomić (jeśli coś zmieniłeś/aś)

- Bez zmian, uruchomienie przebiega tak samo.

## Przyczyna czerwonego testu

- Co było źle: cutoff był ustawiony na 12:00 UTC. Latem to wypada o 14:00 w Warszawie, więc testy letnie przechodziły. Zimą Polska jest UTC+1, więc 12:00 UTC to 13:00 w Warszawie i zamówienie o 13:30 było po terminie.
- Dlaczego test to wyłapał: zimowy test składa zamówienie 14 stycznia o 13:30 na dostawę następnego dnia. To jedyny przypadek między 13:00 a 14:00, czyli tam, gdzie stała godzina UTC daje zły wynik.
- Jak to naprawiłeś/aś: termin liczę jako 14:00 czasu warszawskiego dnia przed dostawą (`ZoneInfo("Europe/Warsaw")`). Przyjmuję tylko to, co jest wcześniejsze niż ta godzina, więc równo 14:00 też odpada. Działa tak samo zimą i latem. Kod jest w `clock.py`.

## Jak korzystałem/am z AI

- Narzędzia: Cursor (Grok 4.7, Sonnet 5.5, Opus 5.5)
- Przykładowe prompty:

1. Zweryfikuj zgodność całej aplikacji z poleceniem zawartym w README.md, specyfikacją z specification.md i api.md oraz praktykami określonymi w AGENTS.md.
   Oceń czy udało mi się wykonać wszystkie zadania, czy też brakuje jakichś funkcjonalności.

Rozważ też czy w kodzie znajdują się jakieś nieoptymalne rozwiązania, nieokreślone w @specification.md ani w @api.md , które mogą powodować problemy z działaniem aplikacji lub utrzymaniem kodu w przyszłości.

2. Zweryfikuj czy projekt posiada wszystkie niezbędne testy w tym te, które są opisane jako wymagane w README.md. Oceń czy istnieją przypadki brzegowe, które nie zostały jeszcze obsłużone.

3. Dodaj regułę CORS dla zapytań pochodzących z portu :5174. Obecnie w odpowiedzi brakuje nagłówka Access-Control-Allow-Origin przez co dane nie są wyświetlane w przeglądarce.
   Dodatkowo dodaj możliwość dodania niestandardowego adresu url do reguły przy starcie dockera (docker compose up).

4. Zaplanuj utworzenie api route /production-plan zgodnie z poleceniem w README.md oraz api.md i specification.md.

W przypadku konieczności wprowadzenia zmian w istniejącym kodzie i innych wpływających na pozostałe funkcjonalności - poinformuj mnie o tym przed implementacją.
Podobnie w przypadku konieczności zmiany planów określonych we wcześniej wspomnianych plikach .md.

5. Rozdziel schematy i modele zarówno na backendzie jak i na frontendzie na dwa osobne pliki. (jeden dla order, drugi dla product)
   Na frontendzie wydziel je całkiem do src/schemas

6. Utwórz schematy Zod odpowiadające modelom danych zdefiniowanym na backendzie.

## Co zweryfikowałem/am ręcznie

- Implementację funkcjonalności rozpocząłem od utworzenia plików api.md i specification.md. Te pliki dokładnie zweryfikowałem ręcznie, posłużyły jako podstawa do praktycznie wszystkich następnych promptów. Wyznaczały dla AI ścieżkę działania - jakich narzędzi ma użyć, jaka ma być struktura projektu, itd...
- Przed każdą dużą zmianą wymagałem od AI jej dokładnego zaplanowania. Następnie weryfikowałem utworzony plan, podejmowałem decyzje, gdy można było podejść do tematu na różne sposoby i dopiero po tym zezwalałem na jego implementacje.
- Dzięki dobremu zaplanowaniu implementacji szeroka ingerencja w kod zwykle nie była wymagana. Zazwyczaj konieczne były jedynie drobne poprawki związane ze strukturą plików, czy zbyt złożonymi, przekombinowanymi funkcjami.

## Gdzie AI się pomyliło / co poprawiłem/am

- Brakowało polityki CORS zezwalającej na wysyłanie zapytań z frontendu porcie 5174.
- AI zaproponowało płaską strukturę plików na backendzie, określiłem lepszy podział.
- Schematy planu produkcji znalazły sie w pliku order.py, wydzieliłem je do osobnego plan.py.
- Rozdzielenie funkcji create_order i build_plan na mniejsze, wykonujące jedno zadanie.

## Co dalej przy większej ilości czasu

**Backend i dane**

- Alembic zamiast `create_all` – wersjonowane migracje; dziś zmiana modelu wymaga `docker compose down -v`.
- Testy na prawdziwym PostgreSQL (testcontainers) – SQLite inaczej obsługuje strefy czasowe i klucze obce, więc zielone testy nie dowodzą zgodności z Postgresem.
- Edycja i anulowanie zamówienia do 14:00 dnia przed dostawą.

**Frontend**

- TanStack Query do pobierania danych – cache, ponawianie i anulowanie zapytań.
- Lepsze stany ładowania i błędów – skeleton zamiast tekstu, przycisk „Spróbuj ponownie”, rozróżnienie błędu sieci od błędu API.
- Wartości filtrów w URL – gdy filtrów będzie więcej albo zechcemy udostępniać link do planu na konkretny dzień.
- TanStack Table – sortowanie, filtrowanie i kolejne tabele bez pisania tego od zera.
- Biblioteka UI (np. shadcn/ui) – w zadaniu świadomie czysty CSS; przy większym panelu przyspieszyłaby pracę i ujednoliciła wygląd.
- Generowanie typów i schematów Zod z OpenAPI FastAPI – dziś schematy Pydantic i Zod są przepisywane ręcznie i mogą się rozjechać.

**Jakość**

- CI (np. GitHub Actions): `pytest` i `npm run build` przy każdym pushu.
- Testy frontendu (Vitest + React Testing Library) dla stanów ładowania, błędu i pustego planu.
