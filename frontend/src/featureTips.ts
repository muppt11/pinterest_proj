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
    how: "Type a description like \"sage green linen\" or drop in a photo to find similar items.",
    why: "Describing a look in words or showing an example is faster than browsing categories.",
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
