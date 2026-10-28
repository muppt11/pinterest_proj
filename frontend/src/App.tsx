import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Item } from "./api/client";
import { BoardAnalyzer } from "./components/BoardAnalyzer";
import { CloseUp } from "./components/CloseUp";
import { Header } from "./components/Header";
import { HelpMenu } from "./components/HelpMenu";
import { SkeletonCard } from "./components/ItemCard";
import { ItemGrid } from "./components/ItemGrid";
import { MasonryGrid } from "./components/MasonryGrid";
import { PageTitle } from "./components/PageTitle";

type Feed = { kind: "browse" } | { kind: "text"; query: string } | { kind: "image"; fileName: string };

const PAGE_SIZE = 50;
const SKELETON_RATIOS = [1.3, 1.5, 1.7, 1.25, 1.33, 1.4, 1.0, 1.6, 1.45, 1.2, 1.75, 1.3];

/** Item id from a /item/<id> path, so close-ups survive reloads and the back button works. */
const itemIdFromPath = (path: string) => decodeURIComponent(path.match(/^\/item\/(.+)$/)?.[1] ?? "") || null;

/** Root layout: header, then the feed (browse or search results), an item close-up, or the board analyzer. */
export default function App() {
  const [feed, setFeed] = useState<Feed>({ kind: "browse" });
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [path, setPath] = useState(window.location.pathname);
  const sentinel = useRef<HTMLDivElement>(null);
  const openId = itemIdFromPath(path);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to: string) => {
    if (window.location.pathname !== to) window.history.pushState(null, "", to);
    setPath(to);
    window.scrollTo({ top: 0 });
  }, []);

  const run = useCallback(async (next: Feed, load: () => Promise<{ items: Item[]; total: number }>, goHome = true) => {
    setFeed(next);
    if (goHome) navigate("/");
    setItems([]);
    setLoading(true);
    setError(null);
    try {
      const page = await load();
      setItems(page.items);
      setTotal(page.total);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  const browse = useCallback(
    (goHome = true) => run({ kind: "browse" }, () => api.listItems(0, PAGE_SIZE), goHome),
    [run],
  );

  // Load the home feed once in the background, without leaving a deep-linked page.
  useEffect(() => {
    browse(false);
  }, [browse]);

  const loadMore = useCallback(async () => {
    if (feed.kind !== "browse" || loading || items.length >= total) return;
    setLoading(true);
    try {
      const page = await api.listItems(items.length, PAGE_SIZE);
      setItems((prev) => [...prev, ...page.items]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [feed.kind, loading, items.length, total]);

  // Infinite scroll on the browse feed; the "Load more" button is the keyboard/no-JS-observer fallback.
  useEffect(() => {
    const el = sentinel.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => entries[0].isIntersecting && loadMore(), {
      rootMargin: "800px",
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  const open = (item: Item) => navigate(`/item/${encodeURIComponent(item.id)}`);

  function back() {
    if (window.history.length > 1) window.history.back();
    else navigate("/");
  }

  const searchText = (query: string) =>
    run({ kind: "text", query }, async () => {
      const r = await api.searchText(query);
      return { items: r.results, total: r.results.length };
    });

  const searchImage = (file: File) =>
    run({ kind: "image", fileName: file.name }, async () => {
      const r = await api.searchImage(file);
      return { items: r.results, total: r.results.length };
    });

  const title =
    feed.kind === "text" ? `Results for “${feed.query}”` : feed.kind === "image" ? "Similar to your photo" : "Discover";

  return (
    <>
      <Header
        path={path}
        onNavigate={navigate}
        onSearchText={searchText}
        onSearchImage={searchImage}
        onHome={() => browse()}
      />
      <main style={{ padding: "8px var(--mb-gutter) 96px" }}>
        {openId ? (
          <CloseUp itemId={openId} onBack={back} onOpen={open} />
        ) : path === "/board" ? (
          <BoardAnalyzer onOpen={open} />
        ) : (
          <>
            <PageTitle>{title}</PageTitle>
            {error && (
              <p role="alert" className="mb-notice">
                {error}
              </p>
            )}
            {!error && !loading && items.length === 0 && (
              <p className="mb-notice">No matches. Try different words or another photo.</p>
            )}
            {items.length > 0 ? (
              <ItemGrid items={items} label={title} onOpen={open} />
            ) : (
              loading && (
                <MasonryGrid
                  label="Loading"
                  items={SKELETON_RATIOS.map((ratio, i) => ({
                    key: `skeleton-${i}`,
                    aspectRatio: ratio,
                    node: <SkeletonCard aspectRatio={ratio} />,
                  }))}
                />
              )
            )}
            {feed.kind === "browse" && items.length > 0 && items.length < total && (
              <div ref={sentinel} className="mb-load-more">
                <button type="button" onClick={loadMore} disabled={loading}>
                  {loading ? "Loading…" : "Load more"}
                </button>
              </div>
            )}
          </>
        )}
      </main>
      <HelpMenu />
    </>
  );
}
