import { useCallback, useEffect, useRef, useState } from "react";
import { api, profileApi, type BoardAnalysis, type BoardContext, type Item, type Me } from "./api/client";
import { AssistantPanel } from "./components/AssistantPanel";
import { BoardsPage } from "./components/BoardsPage";
import { CharactersPage } from "./components/CharactersPage";
import { MoodPage } from "./components/MoodPage";
import { setFocus, useFocus } from "./focus";
import { onboardingSkipped, StyleQuiz } from "./components/StyleQuiz";
import { SavesProvider } from "./saves";
import { BoardAnalyzer } from "./components/BoardAnalyzer";
import { CloseUp } from "./components/CloseUp";
import { Header } from "./components/Header";
import { HelpMenu } from "./components/HelpMenu";
import { SkeletonCard } from "./components/ItemCard";
import { ItemGrid } from "./components/ItemGrid";
import { MasonryGrid } from "./components/MasonryGrid";
import { PageTitle } from "./components/PageTitle";

type Feed =
  | { kind: "browse" }
  | { kind: "text"; query: string }
  | { kind: "image"; fileName: string }
  | { kind: "color"; hex: string; query: string };

type FeedPage = { items: Item[]; total: number; lowRelevance?: boolean };

const PAGE_SIZE = 50;
const SKELETON_RATIOS = [1.3, 1.5, 1.7, 1.25, 1.33, 1.4, 1.0, 1.6, 1.45, 1.2, 1.75, 1.3];

/** Item id from a /item/<id> path, so close-ups survive reloads and the back button works. */
const itemIdFromPath = (path: string) => decodeURIComponent(path.match(/^\/item\/(.+)$/)?.[1] ?? "") || null;
const boardIdFromPath = (path: string) => {
  const id = Number(path.match(/^\/boards\/(\d+)$/)?.[1]);
  return Number.isInteger(id) && id > 0 ? id : null;
};

/** Root layout: header, then the feed (browse or search results), an item close-up, or the board analyzer. */
export default function App() {
  const [feed, setFeed] = useState<Feed>({ kind: "browse" });
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [path, setPath] = useState(window.location.pathname);
  const [board, setBoard] = useState<BoardContext | null>(null);
  // Weak text matches (e.g. "birthday cake" against a clothing catalog) are hidden behind an explanation.
  const [lowRelevance, setLowRelevance] = useState(false);
  const [showWeak, setShowWeak] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [lastAnalysis, setLastAnalysis] = useState<BoardAnalysis | null>(null);
  const focus = useFocus();
  // Signed-up profile (null = not signed up). With quiz answers, Discover shows "For you" by default.
  const [me, setMe] = useState<Me | null>(null);
  const [everything, setEverything] = useState(false);
  const hasPrefs = (me?.prefs?.aesthetics?.length ?? 0) + (me?.prefs?.colors?.length ?? 0) + (me?.prefs?.eras?.length ?? 0) > 0;
  const personalized = hasPrefs && !everything;
  const personalizedRef = useRef(personalized);
  personalizedRef.current = personalized;
  // Re-runs whatever the feed last showed (browse or a search) when the style focus changes.
  const rerun = useRef<() => void>(() => {});
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

  const run = useCallback(async (next: Feed, load: () => Promise<FeedPage>, goHome = true) => {
    setFeed(next);
    if (goHome) navigate("/");
    setItems([]);
    setLowRelevance(false);
    setShowWeak(false);
    setLoading(true);
    setError(null);
    try {
      const page = await load();
      setItems(page.items);
      setTotal(page.total);
      setLowRelevance(page.lowRelevance ?? false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  const loadPage = useCallback(async (offset: number): Promise<FeedPage> => {
    if (personalizedRef.current) {
      const r = await profileApi.forYou(offset, PAGE_SIZE);
      // The For you feed doesn't report a total; assume more while pages come back full.
      return { items: r.items, total: offset + r.items.length + (r.items.length === PAGE_SIZE ? 1 : 0) };
    }
    return api.listItems(offset, PAGE_SIZE);
  }, []);

  const browse = useCallback((goHome = true) => run({ kind: "browse" }, () => loadPage(0), goHome), [run, loadPage]);

  // Load the home feed once in the background, without leaving a deep-linked page.
  useEffect(() => {
    browse(false);
    rerun.current = () => browse(false);
  }, [browse]);

  useEffect(() => {
    profileApi
      .me()
      .then((m) => {
        setMe(m);
        if (m) setFocus(m.prefs.focus);
        else if (!onboardingSkipped() && window.location.pathname === "/") navigate("/welcome");
      })
      .catch(() => {});
  }, [navigate]);

  const firstPersonalized = useRef(true);
  useEffect(() => {
    if (firstPersonalized.current) {
      firstPersonalized.current = false;
      return;
    }
    if (window.location.pathname === "/" && feed.kind === "browse") browse(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personalized]);

  const firstFocus = useRef(true);
  useEffect(() => {
    if (firstFocus.current) {
      firstFocus.current = false;
      return;
    }
    // Other pages remount via <main key>; only the home feed re-runs its last query here.
    if (window.location.pathname === "/") rerun.current();
  }, [focus]);

  const loadMore = useCallback(async () => {
    if (feed.kind !== "browse" || loading || items.length >= total) return;
    setLoading(true);
    try {
      const page = await loadPage(items.length);
      setItems((prev) => [...prev, ...page.items]);
      setTotal(page.total);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [feed.kind, loading, items.length, total, loadPage]);

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

  // Opening from a board aesthetic carries its taste into the close-up; opening from the feed clears it;
  // browsing within a close-up (More like this, Complete the look) keeps whatever is set.
  const open = (item: Item) => navigate(`/item/${encodeURIComponent(item.id)}`);
  const openFromFeed = (item: Item) => {
    setBoard(null);
    open(item);
  };
  const openFromBoard = (item: Item, context: BoardContext) => {
    setBoard(context);
    open(item);
  };

  function back() {
    if (window.history.length > 1) window.history.back();
    else navigate("/");
  }

  const searchText = (query: string) => {
    rerun.current = () => searchText(query);
    return run({ kind: "text", query }, async () => {
      const r = await api.searchText(query);
      return { items: r.results, total: r.results.length, lowRelevance: r.low_relevance };
    });
  };

  const searchColor = (hex: string, query: string) => {
    rerun.current = () => searchColor(hex, query);
    return run({ kind: "color", hex, query }, async () => {
      const r = await api.searchColor(hex, query || undefined);
      return { items: r.results, total: r.results.length };
    });
  };

  const searchImage = (file: File) => {
    rerun.current = () => searchImage(file);
    return run({ kind: "image", fileName: file.name }, async () => {
      const r = await api.searchImage(file);
      return { items: r.results, total: r.results.length };
    });
  };

  const title =
    feed.kind === "text"
      ? `Results for “${feed.query}”`
      : feed.kind === "image"
        ? "Similar to your photo"
        : feed.kind === "color"
          ? `Color ${feed.hex}${feed.query ? ` + “${feed.query}”` : ""}`
          : personalized
            ? `For you, ${me!.display_name}`
            : "Discover";

  return (
    <SavesProvider>
      <Header
        onAsk={() => setAssistantOpen(true)}
        displayName={me?.display_name ?? null}
        path={path}
        onNavigate={navigate}
        onSearchText={searchText}
        onSearchImage={searchImage}
        onSearchColor={searchColor}
        onHome={() => {
          rerun.current = () => browse(false);
          browse();
        }}
      />
      <main key={path === "/" ? "feed" : `${path}:${focus}`} style={{ padding: "8px var(--mb-gutter) 96px" }}>
        {openId ? (
          <CloseUp itemId={openId} board={board} onBack={back} onOpen={open} />
        ) : path === "/characters" || path.startsWith("/characters/") ? (
          <CharactersPage characterId={path.match(/^\/characters\/([a-z0-9-]+)$/)?.[1] ?? null} onNavigate={navigate} onOpen={openFromFeed} />
        ) : path === "/welcome" ? (
          <StyleQuiz
            mode="onboarding"
            me={me}
            onDone={(m) => {
              setMe(m);
              setEverything(false);
              navigate("/");
            }}
          />
        ) : path === "/me" ? (
          <div className="mb-yourstyle">
            <PageTitle
              actions={
                me && (
                  <button
                    type="button"
                    className="mb-link-button"
                    onClick={async () => {
                      await profileApi.signOut();
                      setMe(null);
                      navigate("/");
                    }}
                  >
                    Sign out
                  </button>
                )
              }
            >
              Your style
            </PageTitle>
            <StyleQuiz
              mode="edit"
              me={me}
              onDone={(m) => {
                setMe(m);
                setEverything(false);
                navigate("/");
              }}
            />
          </div>
        ) : path === "/mood" ? (
          <MoodPage onOpen={openFromFeed} />
        ) : path === "/board" ? (
          <BoardAnalyzer onOpen={openFromBoard} onAnalyzed={setLastAnalysis} />
        ) : path === "/boards" || path.startsWith("/boards/") ? (
          <BoardsPage boardId={boardIdFromPath(path)} onNavigate={navigate} onOpen={openFromFeed} />
        ) : (
          <>
            <PageTitle
              actions={
                feed.kind === "browse" &&
                hasPrefs && (
                  <div role="radiogroup" aria-label="Feed" className="mb-feed-toggle">
                    <button type="button" role="radio" aria-checked={!everything} onClick={() => setEverything(false)}>
                      For you
                    </button>
                    <button type="button" role="radio" aria-checked={everything} onClick={() => setEverything(true)}>
                      Everything
                    </button>
                  </div>
                )
              }
            >
              {title}
            </PageTitle>
            {error && (
              <p role="alert" className="mb-notice">
                {error}
              </p>
            )}
            {!error && !loading && items.length === 0 && (
              <p className="mb-notice">No matches. Try different words or another photo.</p>
            )}
            {lowRelevance && !showWeak && feed.kind === "text" ? (
              <div className="mb-notice mb-weak" role="status">
                <p>
                  MoodBoards' catalog is clothing only, and nothing matched “{feed.query}” closely. Try describing
                  an outfit, like “cozy oversized knit” or “white sneakers”.
                </p>
                <button type="button" onClick={() => setShowWeak(true)}>
                  Show closest items anyway
                </button>
              </div>
            ) : items.length > 0 ? (
              <ItemGrid items={items} label={title} onOpen={openFromFeed} />
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
      <AssistantPanel
        open={assistantOpen}
        onClose={() => setAssistantOpen(false)}
        onOpenItem={open}
        contextItemIds={openId ? [openId] : []}
        board={
          lastAnalysis
            ? lastAnalysis.aesthetics.map((a) => ({
                label: `Aesthetic ${a.index + 1}`,
                style_tags: a.style_tags.map((t) => t.word),
                centroid: a.centroid,
              }))
            : null
        }
      />
      <HelpMenu suppressWelcome={path === "/welcome"} />
    </SavesProvider>
  );
}
