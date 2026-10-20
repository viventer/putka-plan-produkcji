import { Fragment } from "react";

import type { ProductionPlan } from "./schemas/plan";

export default function PlanTable({ plan }: { plan: ProductionPlan }) {
  const grandTotal = plan.categories.reduce((sum, category) => sum + category.total, 0);

  return (
    <table>
      <thead>
        <tr>
          <th>Produkt</th>
          <th className="num">Ilość (szt.)</th>
        </tr>
      </thead>
      <tbody>
        {plan.categories.map((category) => (
          <Fragment key={category.category}>
            <tr className="category-row">
              <th colSpan={2}>{category.category}</th>
            </tr>
            {category.items.map((item) => (
              <tr key={item.product_id} className={item.quantity === 0 ? "zero" : undefined}>
                <td>{item.name}</td>
                <td className="num">{item.quantity}</td>
              </tr>
            ))}
            <tr className="total-row">
              <td>Razem: {category.category}</td>
              <td className="num">{category.total}</td>
            </tr>
          </Fragment>
        ))}
      </tbody>
      <tfoot>
        <tr className="total-row">
          <td>Razem wszystkie</td>
          <td className="num">{grandTotal}</td>
        </tr>
      </tfoot>
    </table>
  );
}
