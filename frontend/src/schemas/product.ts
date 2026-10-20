import { z } from "zod";

const decimalString = z.string().regex(/^\d+(\.\d+)?$/);

export const ProductSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  category: z.string(),
  unit_price: decimalString,
});

export type Product = z.infer<typeof ProductSchema>;
