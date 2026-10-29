import { useContext, type ReactNode } from "react";
import { categoryLabel } from "../categories";
import { altText, imageSrc, repostLabel, type Item } from "../api/client";
import { SavesContextOptional } from "../saves";
import { ItemCard } from "./ItemCard";
import { LabelBadge } from "./LabelBadge";
import { MasonryGrid } from "./MasonryGrid";

interface ItemGridProps {
  items: Item[];
  label: string;
  onOpen: (item: Item) => void;
  columnsFor?: (width: number) => number;
  /** Extra always-visible badge per item (e.g. "Closest available" on character looks). */
  badgeFor?: (item: Item) => ReactNode;
}

/** Catalog items as masonry cards. Titles are the dataset's category; there are no product names. */
export function ItemGrid({ items, label, onOpen, columnsFor, badgeFor }: ItemGridProps) {
  const saves = useContext(SavesContextOptional);
  return (
    <MasonryGrid
      label={label}
      columnsFor={columnsFor}
      items={items.map((item) => {
        const ratio = item.height / item.width;
        return {
          key: item.id,
          aspectRatio: ratio,
          node: (
            <ItemCard
              imageUrl={imageSrc(item)}
              alt={altText(item)}
              title={categoryLabel(item.category)}
              aspectRatio={ratio}
              boardLabel={saves?.lastBoard?.name}
              badge={
                <span className="mb-card-badges">
                  {badgeFor?.(item)}
                  {item.provenance && <LabelBadge provenance={item.provenance} compact />}
                  {item.repost && (
                    <span className="mb-badge" title={item.repost.reason}>
                      {repostLabel(item)}
                    </span>
                  )}
                </span>
              }
              onOpen={() => onOpen(item)}
              onSave={saves ? (anchor) => saves.quickSave(item, anchor) : undefined}
              onSelectBoards={saves ? (anchor) => saves.openPicker(item, anchor) : undefined}
            />
          ),
        };
      })}
    />
  );
}
