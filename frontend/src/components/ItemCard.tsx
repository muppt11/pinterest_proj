import type { ReactNode } from "react";
import "./ItemCard.css";

export interface ItemCardProps {
  imageUrl: string;
  alt: string;
  title?: string;
  aspectRatio: number;
  /** Always-visible badge slot (bottom-left), e.g. the AI provenance label in feature 5. */
  badge?: ReactNode;
  /** Board the hover Save goes to; shown on the board picker button. */
  boardLabel?: string;
  onOpen?: () => void;
  onSave?: (anchor: HTMLElement) => void;
  onSelectBoards?: (anchor: HTMLElement) => void;
}

/**
 * Rounded image card with its title underneath. Hovering or focusing shows the
 * board picker, Save pill, and quick actions over a dark tint.
 */
export function ItemCard({ imageUrl, alt, title, aspectRatio, badge, boardLabel, onOpen, onSave, onSelectBoards }: ItemCardProps) {
  return (
    <article className="mb-card">
      <div className="mb-card-media" style={{ aspectRatio: `1 / ${aspectRatio}` }}>
        <img src={imageUrl} alt={alt} loading="lazy" />
        <button type="button" className="mb-card-open" onClick={onOpen} aria-label={`Open ${title ?? alt}`} />
        <div className="mb-card-overlay">
          <button
            type="button"
            className="mb-card-board"
            aria-label={`Choose boards for ${title ?? alt}`}
            onClick={(e) => onSelectBoards?.(e.currentTarget)}
          >
            <span className="mb-card-board-name">{boardLabel ?? "Select"}</span> <span aria-hidden="true">⌄</span>
          </button>
          <button
            type="button"
            className="mb-card-save"
            aria-label={boardLabel ? `Save to ${boardLabel}` : "Save"}
            onClick={(e) => onSave?.(e.currentTarget)}
          >
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
