# Putka – Plan produkcji

Cześć! Dzięki, że poświęcasz czas na to zadanie.

Putka to sieć piekarni w Warszawie. Każdego dnia sklepy zamawiają pieczywo na
dzień następny, a produkcja potrzebuje z tego jednego, zsumowanego planu: ile
czego upiec. Twoim zadaniem jest dobudowanie tego kawałka systemu.

W repozytorium jest już działający szkielet: FastAPI + PostgreSQL po stronie
backendu, React + Vite po stronie frontendu, sklepy i produkty w bazie oraz
kilka testów.

## Uruchomienie

Potrzebujesz Dockera z Docker Compose.

```bash
docker compose up --build
```

- API: http://localhost:8000 (dokumentacja: http://localhost:8000/docs)
- Frontend: http://localhost:5173
- PostgreSQL: `localhost:5432`, użytkownik/hasło/baza: `putka`

Tabele tworzą się przy starcie backendu (`Base.metadata.create_all`), a dane
startowe (5 sklepów, 15 produktów) dogrywają się automatycznie. Jeśli zmienisz
model i chcesz zacząć od czystej bazy: `docker compose down -v`.

Jeśli któryś port jest zajęty, możesz go zmienić zmiennymi `DB_PORT`,
`BACKEND_PORT`, `FRONTEND_PORT`, `REDIS_PORT`, np. `BACKEND_PORT=8001 docker compose up`
(wtedy ustaw też `VITE_API_URL=http://localhost:8001`).

### Testy

Testy backendu działają na SQLite w pamięci, więc nie potrzebują Postgresa:

```bash
# w kontenerze
docker compose exec backend pytest

# albo lokalnie (Python 3.12)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Uwaga: na starcie **jeden test jest czerwony** – to część zadania (pkt 3).

## Zadanie

1. **Model zamówień**: tabele zamówień i pozycji z ograniczeniami (FK, quantity > 0, sensowna unikalność, cena z chwili zamówienia).
2. **`POST /orders`**: data dostawy ≥ jutro, zamówienie do 14:00 czasu warszawskiego dnia poprzedniego, tylko aktywne produkty, zapis w jednej transakcji, czytelne błędy 4xx.
3. **Jeden z testów jest czerwony** — znajdź i napraw przyczynę, opisz ją w `NOTES.md`.
4. **`GET /production-plan?date=YYYY-MM-DD`**: suma sztuk na produkt pogrupowana po kategorii, produkty bez zamówień z 0.
5. **Widok „Plan produkcji” w React**: wybór daty, tabela, stany ładowania i błędu (formularz zamówienia opcjonalny).
6. **Testy**: co najmniej reguła cutoff (przypadki brzegowe) i agregacja.
7. **`NOTES.md`** – uzupełnij szablon, który znajdziesz w repo.

### Bonus (nieobowiązkowy)

Nie jest potrzebny do dobrej oceny – rób tylko, jeśli masz ochotę i czas.
Do wyboru jedno z dwóch:

- eksport planu do CSV jako zadanie w tle (Redis + RQ/arq) ze statusem, **albo**
- cache planu w Redisie z unieważnianiem.

Redis jest już w `docker-compose.yml` (`REDIS_URL` jest ustawiony w kontenerze backendu).

## Zasady

- **Narzędzia AI są mile widziane.** Interesuje nas, jak z nimi pracujesz
  i jak sprawdzasz to, co wygenerowały – stąd sekcje w `NOTES.md`.
- **Czas: ok. 2 godziny.** Nie poleruj na siłę – wolimy mniej, ale przemyślane
  i sprawdzone, niż wszystko „na szybko”. Jeśli czegoś nie zdążysz, napisz
  w `NOTES.md`, jak byś to zrobił/a.
- Możesz zmieniać wszystko w szkielecie (strukturę, biblioteki, Alembic itd.),
  jeśli uznasz to za sensowne – opisz to krótko w `NOTES.md`.
- **Oddanie:** link do repozytorium (GitHub/GitLab, może być prywatne
  z dostępem dla nas) z historią commitów – prosimy, bez squasha.
  Termin: 48 h od pobrania projektu (odliczanie widzisz w panelu).
- Potem umówimy się na 20–30 minut rozmowy, podczas której wspólnie przejdziemy
  przez Twój kod.

Powodzenia i smacznego! W razie pytań – pisz śmiało.
