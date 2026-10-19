export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type Product = {
  id: number;
  name: string;
  category: string;
  unit_price: string;
};

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}
