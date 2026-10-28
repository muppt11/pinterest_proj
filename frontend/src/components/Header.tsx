import { useRef, useState, type FormEvent } from "react";
import { FeatureTip } from "./FeatureTip";
import { FocusSelect } from "./FocusPicker";
import { ThemeToggle } from "./ThemeToggle";
import "./Header.css";

interface HeaderProps {
  onAsk: () => void;
  /** Signed-up display name, or null before sign-up. */
  displayName: string | null;
  path: string;
  onNavigate: (to: string) => void;
  onSearchText: (query: string) => void;
  onSearchImage: (file: File) => void;
  /** Color search; `query` (optional) is blended in, e.g. sage + "linen". */
  onSearchColor: (hex: string, query: string) => void;
  onHome: () => void;
}

const NAV = [
  { to: "/", label: "Discover" },
  { to: "/mood", label: "Mood" },
  { to: "/characters", label: "Characters" },
  { to: "/boards", label: "Boards" },
  { to: "/board", label: "Analyze board" },
];

/** Top bar: logo + wordmark, nav tabs, pill search field with photo search, and the theme toggle. */
export function Header({ onAsk, displayName, path, onNavigate, onSearchText, onSearchImage, onSearchColor, onHome }: HeaderProps) {
  const [query, setQuery] = useState("");
  const [color, setColor] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const colorTimer = useRef<number | undefined>(undefined);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (color) onSearchColor(color, query.trim());
    else if (query.trim()) onSearchText(query.trim());
  }

  return (
    <header className="mb-header">
      <a
        className="mb-brand"
        href="/"
        aria-label="MoodBoards home"
        onClick={(e) => {
          e.preventDefault();
          setQuery("");
          setColor(null);
          onHome();
        }}
      >
        <img src="/logo.webp" alt="" width={32} height={32} />
        <span className="mb-wordmark">MoodBoards</span>
      </a>
      <nav aria-label="Main" className="mb-nav">
        {NAV.map(({ to, label }) => {
          const active = path === to || (to !== "/" && path.startsWith(`${to}/`));
          return (
            <a
              key={to}
              href={to}
              className={active ? "is-active" : undefined}
              aria-current={active ? "page" : undefined}
              onClick={(e) => {
                e.preventDefault();
                if (to === "/") {
                  setQuery("");
                  onHome();
                } else onNavigate(to);
              }}
            >
              {label}
            </a>
          );
        })}
      </nav>
      <form className="mb-search" role="search" onSubmit={submit}>
        <label htmlFor="mb-search-input" className="visually-hidden">
          Search outfits and items
        </label>
        <FeatureTip tipId="search">
          <div className="mb-search-field">
            <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18">
              <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" strokeWidth="2.2" />
              <path d="m15.5 15.5 5 5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
            </svg>
            <input
              id="mb-search-input"
              type="search"
              placeholder="Search outfits, e.g. sage green linen"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {color && (
              <span className="mb-color-chip">
                <span className="mb-color-dot" style={{ background: color }} aria-hidden="true" />
                {color}
                <button
                  type="button"
                  aria-label="Clear color"
                  onClick={() => {
                    setColor(null);
                    if (query.trim()) onSearchText(query.trim());
                  }}
                >
                  ×
                </button>
              </span>
            )}
            <FeatureTip tipId="color" align="end">
              <label className="mb-search-camera mb-color-picker" title="Search by color">
                <span className="visually-hidden">Search by color</span>
                <span
                  className="mb-color-wheel-icon"
                  aria-hidden="true"
                  style={color ? { background: color } : undefined}
                />
                <input
                  type="color"
                  value={color ?? "#9caf88"}
                  onChange={(e) => {
                    // The native picker fires on every drag movement; search once the user pauses.
                    const hex = e.target.value;
                    setColor(hex);
                    window.clearTimeout(colorTimer.current);
                    colorTimer.current = window.setTimeout(() => onSearchColor(hex, query.trim()), 300);
                  }}
                />
              </label>
            </FeatureTip>
            <button
              type="button"
              className="mb-search-camera"
              aria-label="Search with a photo"
              title="Search with a photo"
              onClick={() => fileInput.current?.click()}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20">
                <path
                  d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.7l1.3-2h5l1.3 2h1.7A2.5 2.5 0 0 1 20 8.5v8a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16.5z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                />
                <circle cx="12" cy="12.5" r="3.2" fill="none" stroke="currentColor" strokeWidth="2" />
              </svg>
            </button>
            <input
              ref={fileInput}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              data-testid="photo-input"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onSearchImage(file);
                e.target.value = "";
              }}
            />
          </div>
        </FeatureTip>
      </form>
      <FocusSelect />
      <FeatureTip tipId="assistant" align="end">
        <button type="button" className="mb-ask-button" onClick={onAsk}>
          <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18">
            <path
              d="M12 3l1.9 4.6L18.5 9.5 13.9 11.4 12 16l-1.9-4.6L5.5 9.5l4.6-1.9zM18 15l.9 2.1L21 18l-2.1.9L18 21l-.9-2.1L15 18l2.1-.9z"
              fill="currentColor"
            />
          </svg>
          Ask
        </button>
      </FeatureTip>
      <button
        type="button"
        className={displayName ? "mb-avatar" : "mb-link-button"}
        aria-label={displayName ? `Your style (${displayName})` : "Sign up"}
        title={displayName ? "Your style" : "Sign up and take the style quiz"}
        onClick={() => onNavigate(displayName ? "/me" : "/welcome")}
      >
        {displayName ? displayName[0].toUpperCase() : "Sign up"}
      </button>
      <FeatureTip tipId="theme" align="end">
        <ThemeToggle />
      </FeatureTip>
    </header>
  );
}
