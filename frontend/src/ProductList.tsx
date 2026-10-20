import { useEffect, useState } from "react";
import { z } from "zod";

import { fetchJson } from "./api";
import { ProductSchema, type Product } from "./schemas/product";

export default function ProductList() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson("/products", z.array(ProductSchema))
      .then(setProducts)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Nieznany błąd");
      })
      .finally(() => setLoading(false));
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
            <td className="num">{Number(p.unit_price).toFixed(2)} zł</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
