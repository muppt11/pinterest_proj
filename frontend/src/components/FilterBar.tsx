import { useEffect, useState } from "react";
import { api } from "../api/client";
import { CATEGORY_GROUPS, categoryLabel, DEFAULT_FILTERS, GARMENT_GROUPS, type CatalogFilters } from "../categories";
import { useFocus } from "../focus";

interface Props {
  value: CatalogFilters;
  showStyle: boolean;
  onChange: (next: CatalogFilters) => void;
}

/** Garment-type chips and an aesthetic picker for Discover and search results. */
export function FilterBar({ value, showStyle, onChange }: Props) {
  const { group, category, audience, colorFamily, style } = value;
  const [styles, setStyles] = useState<string[]>([]);
  const [categories, setCategories] = useState<{ value: string; label: string; group: string | null; count?: number }[]>(
    Object.entries(CATEGORY_GROUPS).map(([value, group]) => ({ value, group, label: categoryLabel(value) })),
  );
  const focus = useFocus();

  useEffect(() => {
    if (!showStyle) return;
    let cancelled = false;
    api.styles().then((result) => !cancelled && setStyles(result)).catch(() => {});
    return () => { cancelled = true; };
  }, [showStyle]);

  useEffect(() => {
    let cancelled = false;
    setCategories((previous) => previous.map((c) => ({ ...c, count: undefined })));
    api.filterOptions({ audience, colorFamily }).then((options) => {
      if (!cancelled && Array.isArray(options.categories)) setCategories(options.categories);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [audience, colorFamily, focus]);

  const active = group || category || audience !== "all" || colorFamily || (showStyle && style);

  return (
    <div className="mb-filterbar" role="group" aria-label="Filters">
      <div className="mb-filter-chips" role="radiogroup" aria-label="Garment type">
        <button type="button" role="radio" aria-checked={group === null} onClick={() => onChange({ ...value, group: null, category: null })}>
          All
        </button>
        {GARMENT_GROUPS.map((g) => (
          <button key={g.id} type="button" role="radio" aria-checked={group === g.id} onClick={() => onChange({ ...value, group: g.id, category: null })}>
            {g.label}
          </button>
        ))}
      </div>
      <div className="mb-filter-details">
        <label className="mb-filter-style">
          <span>Category</span>
          <select value={category ?? ""} onChange={(e) => onChange({ ...value, category: e.target.value || null })}>
            <option value="">{group ? "All in this group" : "Any category"}</option>
            {categories.filter((c) => !group || c.group === group).map((c) => (
              <option key={c.value} value={c.value} disabled={c.count === 0 && c.value !== category}>
                {c.label}{c.count === undefined ? "" : ` (${c.count})`}
              </option>
            ))}
          </select>
        </label>
        <label className="mb-filter-style">
          <span>Audience</span>
          <select value={audience} onChange={(e) => onChange({ ...value, audience: e.target.value as CatalogFilters["audience"] })}>
            <option value="all">Adults & kids</option>
            <option value="adults">Adults</option>
            <option value="kids">Kids</option>
          </select>
        </label>
        <label className="mb-filter-style">
          <span>Color family</span>
          <select value={colorFamily ?? ""} onChange={(e) => onChange({ ...value, colorFamily: e.target.value || null })}>
            <option value="">Any palette</option>
            {["neutrals", "brights", "pastels", "darks", "earth tones"].map((family) => <option key={family} value={family}>{family}</option>)}
          </select>
        </label>
        {showStyle && (
          <label className="mb-filter-style">
            <span>Aesthetic</span>
            <select value={style ?? ""} onChange={(e) => onChange({ ...value, style: e.target.value || null })}>
              <option value="">Any aesthetic</option>
              {styles.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        )}
        {active && <button type="button" className="mb-link-button mb-filter-reset" onClick={() => onChange({ ...DEFAULT_FILTERS })}>Clear filters</button>}
      </div>
    </div>
  );
}
