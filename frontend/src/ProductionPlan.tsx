import { useEffect, useState } from "react";

import { fetchJson } from "./api";
import { addDays, tomorrowInWarsaw } from "./dates";
import PlanTable from "./PlanTable";
import {
  ProductionPlanSchema,
  type ProductionPlan as Plan,
} from "./schemas/plan";

export default function ProductionPlan() {
  const [date, setDate] = useState(tomorrowInWarsaw);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (date === "") {
      setPlan(null);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setError(null);

    fetchJson(`/production-plan?date=${date}`, ProductionPlanSchema, {
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) return;
        setPlan(data);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setPlan(null);
        setError(e instanceof Error ? e.message : "Nieznany błąd");
      });

    return () => controller.abort();
  }, [date]);

  function selectDate(next: string) {
    setDate(next);
  }

  const current = plan !== null && plan.date === date ? plan : null;
  const noOrders =
    current !== null &&
    current.categories.length > 0 &&
    current.categories.every((category) =>
      category.items.every((item) => item.quantity === 0),
    );

  return (
    <>
      <div className="toolbar">
        <label>
          Data dostawy{" "}
          <input
            type="date"
            value={date}
            onChange={(event) => selectDate(event.target.value)}
          />
        </label>
        <button
          type="button"
          onClick={() => selectDate(addDays(date, -1))}
          disabled={date === ""}
        >
          Poprzedni dzień
        </button>
        <button type="button" onClick={() => selectDate(tomorrowInWarsaw())}>
          Jutro
        </button>
        <button
          type="button"
          onClick={() => selectDate(addDays(date, 1))}
          disabled={date === ""}
        >
          Następny dzień
        </button>
      </div>

      {date === "" ? (
        <p className="empty">Wybierz datę dostawy</p>
      ) : error !== null ? (
        <p className="error">Nie udało się pobrać planu: {error}</p>
      ) : current === null ? (
        <p>Ładowanie…</p>
      ) : current.categories.length === 0 ? (
        <p className="empty">Brak produktów w planie na {date}.</p>
      ) : (
        <>
          {noOrders ? <p className="empty">Brak zamówień na {date}.</p> : null}
          <PlanTable plan={current} />
        </>
      )}
    </>
  );
}
