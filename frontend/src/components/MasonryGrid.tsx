import { useEffect, useState, type ReactNode } from "react";
import "./MasonryGrid.css";

export interface MasonryItem {
  key: string;
  /** height / width, used to balance columns before images load */
  aspectRatio: number;
  node: ReactNode;
}

/** Column count for a viewport width; mirrors the breakpoints in MasonryGrid.css. */
export function columnsForWidth(width: number): number {
  if (width >= 1600) return 6;
  if (width >= 1280) return 5;
  if (width >= 960) return 4;
  if (width >= 640) return 3;
  return 2;
}

/**
 * Greedy shortest-column placement. Unlike CSS `columns`, this keeps items in reading
 * order left-to-right, so keyboard Tab order follows what the eye sees.
 */
export function distribute(items: MasonryItem[], columnCount: number): MasonryItem[][] {
  const columns: MasonryItem[][] = Array.from({ length: columnCount }, () => []);
  const heights = new Array<number>(columnCount).fill(0);
  for (const item of items) {
    const shortest = heights.indexOf(Math.min(...heights));
    columns[shortest].push(item);
    heights[shortest] += item.aspectRatio;
  }
  return columns;
}

function useColumnCount(): number {
  const [count, setCount] = useState(() => columnsForWidth(window.innerWidth));
  useEffect(() => {
    const onResize = () => setCount(columnsForWidth(window.innerWidth));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return count;
}

/** Responsive masonry layout of variable-height cards. */
export function MasonryGrid({ items, label }: { items: MasonryItem[]; label: string }) {
  const columns = distribute(items, useColumnCount());
  return (
    <div className="mb-masonry" role="list" aria-label={label}>
      {columns.map((column, i) => (
        <div className="mb-masonry-col" key={i}>
          {column.map((item) => (
            <div role="listitem" key={item.key}>
              {item.node}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
