import { useRef, useState, type FormEvent } from "react";
import { FeatureTip } from "./FeatureTip";
import { ThemeToggle } from "./ThemeToggle";
import "./Header.css";

interface HeaderProps {
  onAsk: () => void;
  path: string;
  onNavigate: (to: string) => void;
  onSearchText: (query: string) => void;
  onSearchImage: (file: File) => void;
  onHome: () => void;
}

const NAV = [
  { to: "/", label: "Discover" },
  { to: "/board", label: "Analyze board" },
  { to: "/boards", label: "Boards" },
];

/** Top bar: logo + wordmark, nav tabs, pill search field with photo search, and the theme toggle. */
export function Header({ onAsk, path, onNavigate, onSearchText, onSearchImage, onHome }: HeaderProps) {
  const [query, setQuery] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (query.trim()) onSearchText(query.trim());
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
      <FeatureTip tipId="theme" align="end">
        <ThemeToggle />
      </FeatureTip>
    </header>
  );
}
