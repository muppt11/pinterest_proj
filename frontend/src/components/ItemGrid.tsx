import { useContext } from "react";
import { altText, imageSrc, repostLabel, type Item } from "../api/client";
import { SavesContextOptional } from "../saves";
import { ItemCard } from "./ItemCard";
import { MasonryGrid } from "./MasonryGrid";

interface ItemGridProps {
  items: Item[];
  label: string;
  onOpen: (item: Item) => void;
  columnsFor?: (width: number) => number;
}

/** Catalog items as masonry cards. Titles are the dataset's category; there are no product names. */
export function ItemGrid({ items, label, onOpen, columnsFor }: ItemGridProps) {
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
              title={item.category}
              aspectRatio={ratio}
              boardLabel={saves?.lastBoard?.name}
              badge={item.repost ? <span className="mb-badge" title={item.repost.reason}>{repostLabel(item)}</span> : undefined}
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
