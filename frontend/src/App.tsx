import ProductList from "./ProductList";
import ProductionPlan from "./ProductionPlan";

export default function App() {
  return (
    <main>
      <header>
        <h1>Putka</h1>
        <p className="subtitle">Plan produkcji</p>
      </header>

      <section>
        <h2>Plan produkcji</h2>
        <ProductionPlan />
      </section>

      <section>
        <h2>Aktywne produkty</h2>
        <ProductList />
      </section>
    </main>
  );
}
