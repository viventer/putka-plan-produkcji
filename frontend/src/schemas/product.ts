import { z } from "zod";

export const decimalString = z.string().regex(/^\d+(\.\d+)?$/);

export const StoreSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  address: z.string(),
});

export const ProductSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  category: z.string(),
  unit_price: decimalString,
});

export type Store = z.infer<typeof StoreSchema>;
export type Product = z.infer<typeof ProductSchema>;
