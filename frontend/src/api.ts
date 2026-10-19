import { z } from "zod";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type Product = {
  id: number;
  name: string;
  category: string;
  unit_price: string;
};

const DecimalString = z.string().regex(/^\d+(\.\d+)?$/);

export const OrderItemInSchema = z.object({
  product_id: z.number().int().positive(),
  quantity: z.number().int().positive(),
});

export const OrderInSchema = z.object({
  store_id: z.number().int().positive(),
  delivery_date: z.iso.date(),
  items: z.array(OrderItemInSchema).min(1),
});

export const OrderItemSchema = z.object({
  product_id: z.number().int(),
  quantity: z.number().int().positive(),
  unit_price: DecimalString,
});

export const OrderSchema = z.object({
  id: z.number().int(),
  store_id: z.number().int(),
  delivery_date: z.iso.date(),
  created_at: z.iso.datetime({ offset: true }),
  items: z.array(OrderItemSchema),
});

export type OrderIn = z.infer<typeof OrderInSchema>;
export type Order = z.infer<typeof OrderSchema>;

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}
