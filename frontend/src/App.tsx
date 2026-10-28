import { Header } from "./components/Header";
import { HelpMenu } from "./components/HelpMenu";
import { SkeletonCard } from "./components/ItemCard";
import { MasonryGrid, type MasonryItem } from "./components/MasonryGrid";
import { PageTitle } from "./components/PageTitle";

// Placeholder tile shapes until the catalog index exists (feature 1). No fake items.
const SKELETON_RATIOS = [1.3, 1.5, 1.7, 1.25, 1.33, 1.4, 1.0, 1.6, 1.45, 1.2, 1.75, 1.3];

/** Root layout. Feature screens (close-up, boards, assistant, trips) plug in here. */
export default function App() {
  const skeletons: MasonryItem[] = SKELETON_RATIOS.map((ratio, i) => ({
    key: `skeleton-${i}`,
    aspectRatio: ratio,
    node: <SkeletonCard aspectRatio={ratio} />,
  }));

  return (
    <>
      <Header />
      <main style={{ padding: "8px var(--mb-gutter) 96px" }}>
        <PageTitle>Discover</PageTitle>
        <p className="visually-hidden">The catalog loads here once the index is built.</p>
        <MasonryGrid items={skeletons} label="Catalog" />
      </main>
      <HelpMenu />
    </>
  );
}
