import { useEffect, useState } from "react";
import { api } from "../api/client";
import { GARMENT_GROUPS, type GarmentGroup } from "../categories";

interface Props {
  group: GarmentGroup | null;
  style: string | null;
  showStyle: boolean;
  onChange: (next: { group: GarmentGroup | null; style: string | null }) => void;
}

/** Garment-type chips and an aesthetic picker for Discover and search results. */
export function FilterBar({ group, style, showStyle, onChange }: Props) {
  const [styles, setStyles] = useState<string[]>([]);

  useEffect(() => {
    if (showStyle) api.styles().then(setStyles).catch(() => {});
  }, [showStyle]);

  return (
    <div className="mb-filterbar" role="group" aria-label="Filters">
      <div className="mb-filter-chips" role="radiogroup" aria-label="Garment type">
        <button type="button" role="radio" aria-checked={group === null} onClick={() => onChange({ group: null, style })}>
          All
        </button>
        {GARMENT_GROUPS.map((g) => (
          <button key={g.id} type="button" role="radio" aria-checked={group === g.id} onClick={() => onChange({ group: g.id, style })}>
            {g.label}
          </button>
        ))}
      </div>
      {showStyle && (
        <label className="mb-filter-style">
          <span className="visually-hidden">Aesthetic</span>
          <select value={style ?? ""} onChange={(e) => onChange({ group, style: e.target.value || null })}>
            <option value="">Any aesthetic</option>
            {styles.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
