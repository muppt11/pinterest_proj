import { FOCUS_LABELS, setFocus, useFocus, type Focus } from "../focus";

/** Compact "Show: All styles / Womenswear / Menswear" control. The split is estimated per item. */
export function FocusSelect() {
  const focus = useFocus();
  return (
    <label className="mb-focus-select" title="Estimated from each image; items in between count as unisex and always show">
      <span className="visually-hidden">Show</span>
      <select value={focus} onChange={(e) => setFocus(e.target.value as Focus)}>
        {(Object.keys(FOCUS_LABELS) as Focus[]).map((f) => (
          <option key={f} value={f}>
            {FOCUS_LABELS[f]}
          </option>
        ))}
      </select>
    </label>
  );
}

