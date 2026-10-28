import { useEffect, useState } from "react";
import { altText, api, imageSrc, type BoardContext, type CompleteLook, type Item } from "../api/client";
import { FeatureTip } from "./FeatureTip";

const GROUP_LABELS: Record<string, string> = {
  tops: "Tops",
  bottoms: "Bottoms",
  "one-piece": "Dresses",
  outerwear: "Outerwear",
  shoes: "Shoes",
  hats: "Hats",
};

interface Props {
  itemId: string;
  board: BoardContext | null;
  onOpen: (item: Item) => void;
}

/** Rows of complementary items (bottoms, shoes, …) for the open item, tuned to a board aesthetic if present. */
export function CompleteTheLook({ itemId, board, onOpen }: Props) {
  const [look, setLook] = useState<CompleteLook | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLook(null);
    setError(null);
    api
      .completeLook(itemId, board)
      .then((r) => !cancelled && setLook(r))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [itemId, board]);

  if (error) return <p role="alert">Couldn't load outfit ideas: {error}</p>;
  if (!look) return <p aria-live="polite">Finding pieces that go with this…</p>;
  if (look.anchor_group === null) return null;

  const groups = look.groups.filter((g) => g.results.length > 0);
  return (
    <section className="mb-ctl" aria-labelledby="ctl-heading">
      <FeatureTip tipId="complete-look">
        <h2 id="ctl-heading">Complete the look</h2>
      </FeatureTip>
      {look.used_board && board && <p className="mb-ctl-note">Tuned to {board.label} from your board</p>}
      {groups.length === 0 && <p className="mb-ctl-note">No matching pieces in the catalog for this item.</p>}
      {groups.map((g) => (
        <div key={g.group} className="mb-ctl-group">
          <h3>{GROUP_LABELS[g.group] ?? g.group}</h3>
          <ul>
            {g.results.map((item) => (
              <li key={item.id}>
                <button type="button" onClick={() => onOpen(item)} aria-label={`Open ${item.category}`}>
                  <img src={imageSrc(item)} alt={altText(item)} loading="lazy" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
