import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { api, type ColorMatchItem, type Item } from "../api/client";
import { FeatureTip } from "./FeatureTip";
import { ItemGrid } from "./ItemGrid";
import { PageTitle } from "./PageTitle";
import "./MoodPage.css";
import { DEFAULT_FILTERS, type CatalogFilters } from "../categories";
import { useFocus } from "../focus";
import { FilterBar } from "./FilterBar";

/** HSL (h 0-360, s/l 0-100) -> #rrggbb */
export function hslToHex(h: number, s: number, l: number): string {
  const a = (s / 100) * Math.min(l / 100, 1 - l / 100);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const c = l / 100 - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return Math.round(255 * c)
      .toString(16)
      .padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

/** Hue/saturation from a point on the wheel (center = grey, edge = full color). */
export function wheelPoint(x: number, y: number, size: number): { h: number; s: number } {
  const dx = x - size / 2;
  const dy = y - size / 2;
  const r = Math.min(Math.hypot(dx, dy) / (size / 2), 1);
  const h = ((Math.atan2(dy, dx) * 180) / Math.PI + 450) % 360; // 0° at top, clockwise
  return { h: Math.round(h), s: Math.round(r * 100) };
}

/** Mood picker: a color wheel + an aesthetic chip -> curated items that match both. */
export function MoodPage({ onOpen }: { onOpen: (item: Item) => void }) {
  const [hue, setHue] = useState(95);
  const [sat, setSat] = useState(25);
  const [light, setLight] = useState(61);
  const [styles, setStyles] = useState<string[]>([]);
  const [style, setStyle] = useState<string | null>(null);
  const [weight, setWeight] = useState(0.5);
  const [results, setResults] = useState<ColorMatchItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<CatalogFilters>({ ...DEFAULT_FILTERS });
  const focus = useFocus();
  const dragging = useRef(false);
  const hex = hslToHex(hue, sat, light);

  useEffect(() => {
    api.styles().then(setStyles).catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!style) return;
    let cancelled = false;
    setLoading(true);
    setResults(null);
    setError(null);
    const t = window.setTimeout(() => {
      api
        .mood(hex, style, weight, 40, filters)
        .then((r) => {
          if (cancelled) return;
          setResults(r.results);
          setError(null);
        })
        .catch((e: Error) => !cancelled && setError(e.message))
        .finally(() => !cancelled && setLoading(false));
    }, 250);
    return () => { cancelled = true; window.clearTimeout(t); };
  }, [hex, style, weight, filters, focus]);

  function pick(e: PointerEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const { h, s } = wheelPoint(e.clientX - rect.left, e.clientY - rect.top, rect.width);
    setHue(h);
    setSat(s);
  }

  function keys(e: KeyboardEvent) {
    const step = e.shiftKey ? 15 : 5;
    if (e.key === "ArrowRight") setHue((h) => (h + step) % 360);
    else if (e.key === "ArrowLeft") setHue((h) => (h - step + 360) % 360);
    else if (e.key === "ArrowUp") setSat((s) => Math.min(100, s + step));
    else if (e.key === "ArrowDown") setSat((s) => Math.max(0, s - step));
    else return;
    e.preventDefault();
  }

  const angle = ((hue - 90) * Math.PI) / 180;
  const dot = { left: `${50 + Math.cos(angle) * sat / 2}%`, top: `${50 + Math.sin(angle) * sat / 2}%` };

  return (
    <div className="mb-mood">
      <PageTitle>Mood picker</PageTitle>
      <FeatureTip tipId="mood">
        <div className="mb-mood-controls">
          <div className="mb-mood-wheel-wrap">
            <div
              className="mb-mood-wheel"
              role="slider"
              tabIndex={0}
              aria-label="Color wheel: left and right change hue, up and down change intensity"
              aria-valuetext={`${hex}, hue ${hue} degrees, intensity ${sat} percent`}
              aria-valuenow={hue}
              aria-valuemin={0}
              aria-valuemax={360}
              style={{ filter: `brightness(${0.4 + light / 100})` }}
              onPointerDown={(e) => {
                dragging.current = true;
                e.currentTarget.setPointerCapture(e.pointerId);
                pick(e);
              }}
              onPointerMove={(e) => dragging.current && pick(e)}
              onPointerUp={() => (dragging.current = false)}
              onPointerCancel={() => (dragging.current = false)}
              onKeyDown={keys}
            >
              <span className="mb-mood-dot" style={{ ...dot, background: hex }} aria-hidden="true" />
            </div>
            <label className="mb-mood-light">
              Lightness
              <input type="range" min={10} max={92} value={light} onChange={(e) => setLight(Number(e.target.value))} />
            </label>
            <div className="mb-mood-swatch">
              <span style={{ background: hex }} aria-hidden="true" />
              <code>{hex}</code>
            </div>
          </div>

          <div className="mb-mood-styles">
            <h2>Pick an aesthetic</h2>
            <div role="radiogroup" aria-label="Aesthetic" className="mb-mood-chips">
              {styles.map((s) => (
                <button key={s} type="button" role="radio" aria-checked={style === s} className={style === s ? "is-on" : undefined} onClick={() => setStyle(s)}>
                  {s}
                </button>
              ))}
            </div>
            <label className="mb-mood-weight">
              <span>Color</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={1 - weight}
                aria-label="Balance between color and style"
                onChange={(e) => setWeight(1 - Number(e.target.value))}
              />
              <span>Style</span>
            </label>
          </div>
        </div>
      </FeatureTip>

      <FilterBar value={filters} onChange={setFilters} showStyle={false} />

      {error && <p role="alert" className="mb-notice">{error}</p>}
      {!style && <p className="mb-notice">Pick a color on the wheel, then an aesthetic, to see your curated items.</p>}
      {loading && <p role="status" className="mb-notice">Finding items for these choices…</p>}
      {!loading && results?.length === 0 && <p className="mb-notice">No matches for this combination. Try a broader category or palette.</p>}
      {style && results && (
        <section className="mb-mood-results" aria-label="Curated items">
          <p className="mb-mood-summary">
            <span className="mb-color-dot" style={{ background: hex }} aria-hidden="true" />
            <span className="mb-mood-summary-text">{style} · {results.length} items ranked by color match (Delta E 2000) and style match</span>
          </p>
          <ItemGrid items={results} label={`${style} in ${hex}`} onOpen={onOpen} />
        </section>
      )}
    </div>
  );
}
