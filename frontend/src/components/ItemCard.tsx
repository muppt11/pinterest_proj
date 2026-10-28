import type { ReactNode } from "react";
import "./ItemCard.css";

export interface ItemCardProps {
  imageUrl: string;
  alt: string;
  title?: string;
  aspectRatio: number;
  /** Always-visible badge slot (bottom-left), e.g. the AI provenance label in feature 5. */
  badge?: ReactNode;
  onOpen?: () => void;
  onSave?: () => void;
}

/**
 * Rounded image card with its title underneath. Hovering or focusing shows the
 * board picker, Save pill, and quick actions over a dark tint.
 */
export function ItemCard({ imageUrl, alt, title, aspectRatio, badge, onOpen, onSave }: ItemCardProps) {
  return (
    <article className="mb-card">
      <div className="mb-card-media" style={{ aspectRatio: `1 / ${aspectRatio}` }}>
        <img src={imageUrl} alt={alt} loading="lazy" />
        <button type="button" className="mb-card-open" onClick={onOpen} aria-label={`Open ${title ?? alt}`} />
        <div className="mb-card-overlay">
          <button type="button" className="mb-card-board">
            Select <span aria-hidden="true">⌄</span>
          </button>
          <button type="button" className="mb-card-save" onClick={onSave}>
            Save
          </button>
        </div>
        {badge && <div className="mb-card-badge">{badge}</div>}
      </div>
      {title && <p className="mb-card-title">{title}</p>}
    </article>
  );
}

/** Grey placeholder tile shown while the catalog loads. */
export function SkeletonCard({ aspectRatio }: { aspectRatio: number }) {
  return <div className="mb-card-skeleton" style={{ aspectRatio: `1 / ${aspectRatio}` }} aria-hidden="true" />;
}
