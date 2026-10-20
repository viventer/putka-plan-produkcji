import { useEffect, useState } from "react";
import { z } from "zod";

import { fetchJson } from "./api";
import { ProductSchema, type Product } from "./schemas/product";

function formatPrice(value: string): string {
  const [whole, fraction = ""] = value.split(".");
  const cents = fraction.length >= 2 ? fraction : fraction.padEnd(2, "0");
  return `${whole}.${cents} zł`;
}

export default function ProductList() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchJson("/products", z.array(ProductSchema), { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        setProducts(data);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : "Nieznany błąd");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, []);

  if (loading) return <p>Ładowanie…</p>;
  if (error) return <p className="error">Nie udało się pobrać produktów: {error}</p>;
  if (products.length === 0) return <p className="empty">Brak aktywnych produktów.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Produkt</th>
          <th>Kategoria</th>
          <th className="num">Cena</th>
        </tr>
      </thead>
      <tbody>
        {products.map((p) => (
          <tr key={p.id}>
            <td>{p.name}</td>
            <td>{p.category}</td>
            <td className="num">{formatPrice(p.unit_price)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
