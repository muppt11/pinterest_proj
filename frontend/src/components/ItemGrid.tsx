import { altText, imageSrc, type Item } from "../api/client";
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
              onOpen={() => onOpen(item)}
            />
          ),
        };
      })}
    />
  );
}
