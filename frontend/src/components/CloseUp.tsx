import { useEffect, useRef, useState } from "react";
import { altText, api, imageSrc, type BoardContext, type Item, type ScoredItem } from "../api/client";
import { CompleteTheLook } from "./CompleteTheLook";
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
  const backButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let cancelled = false;
    setItem(null);
    setSimilar([]);
    setError(null);
    Promise.all([api.getItem(itemId), api.similar(itemId)])
      .then(([it, sim]) => {
        if (cancelled) return;
        setItem(it);
        setSimilar(sim.results);
        backButton.current?.focus();
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [itemId]);

  if (error) return <p role="alert">Couldn't load this item: {error}</p>;
  if (!item) return <p aria-live="polite">Loading…</p>;

  return (
    <div className="mb-closeup-layout">
      <section className="mb-closeup" aria-label={`${item.category} close-up`}>
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
            <button type="button" className="mb-closeup-save">
              Save
            </button>
          </div>
          <h1 className="mb-closeup-title">{item.category}</h1>
          <dl className="mb-closeup-facts">
            <div>
              <dt>Category</dt>
              <dd>{item.category}</dd>
            </div>
            <div>
              <dt>Kids' clothing</dt>
              <dd>{item.kids ? "Yes" : "No"}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>clothing-dataset (CC0)</dd>
            </div>
          </dl>
          <CompleteTheLook itemId={item.id} board={board} onOpen={onOpen} />
        </div>
      </section>
      <section className="mb-closeup-more" aria-labelledby="more-like-this">
        <FeatureTip tipId="more-like-this">
          <h2 id="more-like-this">More like this</h2>
        </FeatureTip>
        {similar.length === 0 ? (
          <p>No similar items found.</p>
        ) : (
          <ItemGrid items={similar} label="More like this" onOpen={onOpen} columnsFor={sideColumns} />
        )}
      </section>
    </div>
  );
}
