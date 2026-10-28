/**
 * One entry per user-facing feature: how to use it and why it exists.
 * Each feature adds its tip here when it ships; the help menu lists them all.
 */
export interface FeatureTipContent {
  id: string;
  title: string;
  how: string;
  why: string;
}

export const FEATURE_TIPS: FeatureTipContent[] = [
  {
    id: "search",
    title: "Search outfits",
    how: "Type a description like \"sage green linen\", or tap the camera to search with a photo of an outfit.",
    why: "Describing a look in words or showing an example is faster than browsing categories.",
  },
  {
    id: "more-like-this",
    title: "More like this",
    how: "Open any item to see the closest matches in the catalog. Tap one to keep exploring.",
    why: "Browsing from an item you already like is the quickest way to narrow down a look.",
  },
  {
    id: "theme",
    title: "Light or dark mode",
    how: "Use the moon / sun button in the top-right corner to switch. Your choice is remembered.",
    why: "Dark mode is easier on the eyes at night and makes bright outfit photos stand out.",
  },
];

const STORAGE_KEY = "mb-dismissed-tips";

/** Read dismissed tip ids. Storage can be unavailable (private mode), so failures mean "none dismissed". */
export function getDismissedTips(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

export function dismissTip(id: string): void {
  try {
    const dismissed = getDismissedTips();
    dismissed.add(id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...dismissed]));
  } catch {
    // Non-critical: the tip will just show again next visit.
  }
}

export function getTip(id: string): FeatureTipContent {
  const tip = FEATURE_TIPS.find((t) => t.id === id);
  if (!tip) throw new Error(`Unknown feature tip: ${id}`);
  return tip;
}
