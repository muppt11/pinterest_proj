import { useContext, useEffect, useRef, useState } from "react";
import { categoryLabel } from "../categories";
import { SavesContextOptional } from "../saves";
import { altText, api, imageSrc, repostLabel, type BoardContext, type Item, type ScoredItem } from "../api/client";
import { CompleteTheLook } from "./CompleteTheLook";
import { LabelBadge } from "./LabelBadge";
import { ShopSimilar } from "./ShopSimilar";
import { FeatureTip } from "./FeatureTip";
import { ItemGrid } from "./ItemGrid";
import "./CloseUp.css";

interface CloseUpProps {
  itemId: string;
  board: BoardContext | null;
  onBack: () => void;
  onOpen: (item: Item) => void;
}

// Side grid beside the panel on wide screens, full width below it otherwise.
const sideColumns = (width: number) => (width >= 1200 ? 3 : width >= 640 ? 3 : 2);

/** Item close-up: large image panel with details, and "More like this" next to it. */
export function CloseUp({ itemId, board, onBack, onOpen }: CloseUpProps) {
  const [item, setItem] = useState<Item | null>(null);
  const [similar, setSimilar] = useState<ScoredItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sameCategory, setSameCategory] = useState(true);
  const [similarLoading, setSimilarLoading] = useState(true);
  const [similarError, setSimilarError] = useState<string | null>(null);
  const backButton = useRef<HTMLButtonElement>(null);
  const saves = useContext(SavesContextOptional);

  useEffect(() => {
    let cancelled = false;
    setItem(null);
    setError(null);
    setSameCategory(true);
    api.getItem(itemId)
      .then((it) => {
        if (cancelled) return;
        setItem(it);
        backButton.current?.focus();
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [itemId]);

  useEffect(() => {
    let cancelled = false;
    setSimilar([]);
    setSimilarLoading(true);
    setSimilarError(null);
    api.similar(itemId, 30, sameCategory).then((r) => {
      if (!cancelled) setSimilar(r.results);
    }).catch((e: Error) => !cancelled && setSimilarError(e.message))
      .finally(() => !cancelled && setSimilarLoading(false));
    return () => { cancelled = true; };
  }, [itemId, sameCategory]);

  if (error) return <p role="alert">Couldn't load this item: {error}</p>;
  if (!item) return <p aria-live="polite">Loading…</p>;

  return (
    <div className="mb-closeup-layout">
      <section className="mb-closeup" aria-label={`${categoryLabel(item.category)} close-up`}>
        <div className="mb-closeup-media">
          <img src={imageSrc(item)} alt={altText(item)} />
          <button ref={backButton} type="button" className="mb-closeup-back" onClick={onBack} aria-label="Back">
            <svg aria-hidden="true" viewBox="0 0 24 24" width="22" height="22">
              <path d="M20 12H5m6-7-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
        <div className="mb-closeup-body">
          <div className="mb-closeup-actions">
            {saves && (
              <>
                <button
                  type="button"
                  className="mb-closeup-board"
                  aria-label="Choose boards"
                  onClick={(e) => saves.openPicker(item, e.currentTarget)}
                >
                  <span className="mb-closeup-board-name">{saves.lastBoard?.name ?? "Select board"}</span>
                  <span aria-hidden="true">⌄</span>
                </button>
                <button type="button" className="mb-closeup-save" onClick={(e) => saves.quickSave(item, e.currentTarget)}>
                  Save
                </button>
              </>
            )}
          </div>
          <h1 className="mb-closeup-title">{categoryLabel(item.category)}</h1>
          {item.provenance && <LabelBadge provenance={item.provenance} />}
          {item.repost && (
            <p className="mb-closeup-repost">
              <strong>{repostLabel(item)}</strong>
              <br />
              {item.repost.reason}
            </p>
          )}
          <dl className="mb-closeup-facts">
            <div>
              <dt>Category</dt>
              <dd>{categoryLabel(item.category)}</dd>
            </div>
            <div>
              <dt>Kids' clothing</dt>
              <dd>{item.kids ? "Yes" : "No"}</dd>
            </div>
            {item.colors && item.colors.length > 0 && (
              <div>
                <dt>Main colors</dt>
                <dd className="mb-swatches">
                  {item.colors.map((c) => (
                    <span key={c} className="mb-color-dot" style={{ background: c }} title={c} aria-label={c} role="img" />
                  ))}
                </dd>
              </div>
            )}
            <div>
              <dt>Source</dt>
              <dd>clothing-dataset (CC0)</dd>
            </div>
          </dl>
          <ShopSimilar itemId={item.id} imageUrl={imageSrc(item)} />
          <CompleteTheLook itemId={item.id} board={board} onOpen={onOpen} />
        </div>
      </section>
      <section className="mb-closeup-more" aria-labelledby="more-like-this">
        <FeatureTip tipId="more-like-this">
          <h2 id="more-like-this">More like this</h2>
        </FeatureTip>
        <div className="mb-filter-chips" role="radiogroup" aria-label="Similar item scope">
          <button type="button" role="radio" aria-checked={sameCategory} onClick={() => setSameCategory(true)}>Same category</button>
          <button type="button" role="radio" aria-checked={!sameCategory} onClick={() => setSameCategory(false)}>Similar styles</button>
        </div>
        {similarError ? <p role="alert">Couldn't load similar items: {similarError}</p> : similarLoading ? <p role="status">Finding similar items…</p> : similar.length === 0 ? (
          <p>{sameCategory ? "No more items in this category. Try Similar styles to explore other garments." : "No similar items found."}</p>
        ) : (
          <ItemGrid items={similar} label="More like this" onOpen={onOpen} columnsFor={sideColumns} />
        )}
      </section>
    </div>
  );
}
