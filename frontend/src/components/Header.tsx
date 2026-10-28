import { FeatureTip } from "./FeatureTip";
import "./Header.css";

/** Top bar: logo, wordmark, and the search field (wired up in feature 1). */
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
          <input
            id="mb-search-input"
            type="search"
            placeholder="Search outfits, e.g. sage green linen"
            disabled
            title="Search arrives in feature 1"
          />
        </FeatureTip>
      </form>
    </header>
  );
}
