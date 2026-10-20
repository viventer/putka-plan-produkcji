# NOTES

> Uzupełnij krótko – wystarczą punkty. To dla nas punkt wyjścia do rozmowy.

## Jak uruchomić (jeśli coś zmieniłeś/aś)

-

## Przyczyna czerwonego testu

- Co było źle:cutoff był ustawiony na 12:00 UTC. Latem to wypada o 14:00 w Warszawie, więc testy letnie przechodziły. Zimą Polska jest UTC+1, więc 12:00 UTC to 13:00 w Warszawie i zamówienie o 13:30 było po terminie.
- Dlaczego test to wyłapał: zimowy test składa zamówienie 14 stycznia o 13:30 na dostawę następnego dnia. To jedyny przypadek między 13:00 a 14:00, czyli tam, gdzie stała godzina UTC daje zły wynik.
- Jak to naprawiłeś/aś: termin liczę jako 14:00 czasu warszawskiego dnia przed dostawą (`ZoneInfo("Europe/Warsaw")`). Przyjmuję tylko to, co jest wcześniejsze niż ta godzina, więc równo 14:00 też odpada. Działa tak samo zimą i latem. Kod jest w `clock.py`.

## Jak korzystałem/am z AI

- Narzędzia:
- Przykładowe prompty:

## Co zweryfikowałem/am ręcznie

-

## Gdzie AI się pomyliło / co poprawiłem/am

-

## Co dalej przy większej ilości czasu

-
