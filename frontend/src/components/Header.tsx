import { FeatureTip } from "./FeatureTip";
import "./Header.css";

/** Top bar: logo + wordmark on the left, pill search field filling the rest (wired up in feature 1). */
export function Header() {
  return (
    <header className="mb-header">
      <a className="mb-brand" href="/" aria-label="MoodBoards home">
        <img src="/logo.svg" alt="" width={32} height={32} />
        <span className="mb-wordmark">MoodBoards</span>
      </a>
      <form className="mb-search" role="search" onSubmit={(e) => e.preventDefault()}>
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
              disabled
              title="Search arrives in feature 1"
            />
          </div>
        </FeatureTip>
      </form>
    </header>
  );
}
