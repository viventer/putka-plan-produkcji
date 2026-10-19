import { useEffect, useState } from "react";
import { fetchJson, type Product } from "./api";

export default function ProductList() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<Product[]>("/products")
      .then(setProducts)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Ładowanie…</p>;
  if (error) return <p className="error">Nie udało się pobrać produktów: {error}</p>;

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
