import ProductList from "./ProductList";

export default function App() {
  return (
    <main>
      <header>
        <h1>Putka</h1>
        <p className="subtitle">Plan produkcji</p>
      </header>

      <section>
        <h2>Aktywne produkty</h2>
        <ProductList />
      </section>
    </main>
  );
}
