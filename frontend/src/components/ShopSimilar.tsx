import { useEffect, useState } from "react";
import { api, type ShopLinks } from "../api/client";
import { FeatureTip } from "./FeatureTip";

/** Outbound links to find something similar to buy. MoodBoards shows no prices or stores itself. */
export function ShopSimilar({ itemId }: { itemId: string }) {
  const [links, setLinks] = useState<ShopLinks | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .shopLinks(itemId)
      .then((l) => !cancelled && setLinks(l))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [itemId]);

  if (!links) return null;
  return (
    <div className="mb-shop">
      <FeatureTip tipId="shop">
        <a className="mb-shop-primary" href={links.google_shopping} target="_blank" rel="noopener noreferrer">
          Shop similar: “{links.query}”
          <span className="visually-hidden"> (opens Google Shopping in a new tab)</span>
        </a>
      </FeatureTip>
      <p className="mb-shop-note">
        Opens Google Shopping in a new tab. Results there aren't checked by MoodBoards. Or{" "}
        <a href={links.google_lens} target="_blank" rel="noopener noreferrer">
          search with Google Lens
        </a>{" "}
        by dropping in a screenshot of this item.
      </p>
    </div>
  );
}
