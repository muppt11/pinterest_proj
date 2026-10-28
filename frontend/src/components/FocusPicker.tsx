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

/** Button group used in the welcome card. */
export function FocusButtons({ onPick }: { onPick?: () => void }) {
  const focus = useFocus();
  return (
    <div role="radiogroup" aria-label="Show me" className="mb-focus-buttons">
      {(Object.keys(FOCUS_LABELS) as Focus[]).map((f) => (
        <button
          key={f}
          type="button"
          role="radio"
          aria-checked={focus === f}
          className={focus === f ? "is-on" : undefined}
          onClick={() => {
            setFocus(f);
            onPick?.();
          }}
        >
          {FOCUS_LABELS[f]}
        </button>
      ))}
    </div>
  );
}
