import { z } from "zod";

import { decimalString } from "./product";

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
  unit_price: decimalString,
});

export const OrderSchema = z.object({
  id: z.number().int(),
  store_id: z.number().int(),
  delivery_date: z.iso.date(),
  created_at: z.iso.datetime({ offset: true }),
  items: z.array(OrderItemSchema),
});

export const PlanItemSchema = z.object({
  product_id: z.number().int(),
  name: z.string(),
  quantity: z.number().int().nonnegative(),
});

export const PlanCategorySchema = z.object({
  category: z.string(),
  total: z.number().int().nonnegative(),
  items: z.array(PlanItemSchema),
});

export const ProductionPlanSchema = z.object({
  date: z.iso.date(),
  categories: z.array(PlanCategorySchema),
});

export type OrderIn = z.infer<typeof OrderInSchema>;
export type Order = z.infer<typeof OrderSchema>;
export type PlanItem = z.infer<typeof PlanItemSchema>;
export type PlanCategory = z.infer<typeof PlanCategorySchema>;
export type ProductionPlan = z.infer<typeof ProductionPlanSchema>;
