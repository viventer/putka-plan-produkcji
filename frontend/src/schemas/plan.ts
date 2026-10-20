import { z } from "zod";

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

export type PlanItem = z.infer<typeof PlanItemSchema>;
export type PlanCategory = z.infer<typeof PlanCategorySchema>;
export type ProductionPlan = z.infer<typeof ProductionPlanSchema>;
