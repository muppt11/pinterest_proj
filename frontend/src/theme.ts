export type Theme = "light" | "dark";

const STORAGE_KEY = "mb-theme";

/** The user's saved choice, else light. Storage can be unavailable, so fall back quietly. */
export function initialTheme(): Theme {
  try {
    if (localStorage.getItem(STORAGE_KEY) === "dark") return "dark";
  } catch {
    // ignore
  }
  return "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // ignore
  }
}
