import { Header } from "./components/Header";
import { HelpMenu } from "./components/HelpMenu";

/** Root layout. Feature screens (grid, close-up, boards, assistant, trips) plug in here. */
export default function App() {
  return (
    <>
      <Header />
      <main style={{ padding: "24px var(--mb-gutter)" }}>
        <p style={{ color: "var(--mb-ink-muted)" }}>
          The catalog grid appears here once the index is built (feature 1).
        </p>
      </main>
      <HelpMenu />
    </>
  );
}
