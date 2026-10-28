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
    id: "color",
    title: "Search by color",
    how: "Tap the rainbow dot in the search bar and pick a color. Add words like “linen” to blend color with a description.",
    why: "People remember outfits by color more than by name, and a picked color is more precise than typing “sage”.",
  },
  {
    id: "mood",
    title: "Mood picker",
    how: "Drag on the color wheel, pick an aesthetic chip, and use the slider to lean toward color or style.",
    why: "For when you know the feeling you want but not the words for it. Two taps turn a mood into a starting board.",
  },
  {
    id: "characters",
    title: "Character style boards",
    how: "Pick a film or TV character to get catalog pieces in their signature style. The chips show which parts of their look were matched.",
    why: "Characters are some of the most-saved style inspiration, and “dress like Wednesday” is easier than describing the look.",
  },
  {
    id: "shop",
    title: "Shop similar",
    how: "On any item, tap Shop similar to search Google Shopping for that color and type of piece.",
    why: "The catalog isn't a store, so this hands you off to real shopping results without MoodBoards inventing prices.",
  },
  {
    id: "more-like-this",
    title: "More like this",
    how: "Open any item to see the closest matches in the catalog. Tap one to keep exploring.",
    why: "Browsing from an item you already like is the quickest way to narrow down a look.",
  },
  {
    id: "complete-look",
    title: "Complete the look",
    how: "Open any item to see bottoms, shoes, outerwear, and more that share its style. Opened from a board? The picks also match that board's aesthetic.",
    why: "Finding the one piece you love is half the job. Building a whole outfit around it is where people get stuck.",
  },
  {
    id: "board",
    title: "Analyze a board",
    how: "Drop in 3–20 outfit photos you love. MoodBoards finds the distinct looks in them and matching items for each.",
    why: "Most boards mix more than one style. Averaging them gives bland picks, so each look gets its own recommendations.",
  },
  {
    id: "boards",
    title: "Boards and saving",
    how: "Hover any item and tap Save to add it to your last board, or tap the board name to tick several boards at once. Boards can hold sub-boards, as deep as you like. Every save shows Undo for 5 seconds.",
    why: "People asked to save one Pin to several boards in one go and to nest boards inside boards, without pop-ups interrupting them.",
  },
  {
    id: "assistant",
    title: "Style assistant",
    how: "Tap Ask and chat: “what shoes would finish this look?” or “compare these two jackets”. It sees the item you have open and your analyzed board.",
    why: "Some questions are easier to ask than to search. Every item it shows comes from a live catalog search, so it can't make products up.",
  },
  {
    id: "theme",
    title: "Light or dark mode",
    how: "Use the moon / sun button in the top-right corner to switch. Your choice is remembered.",
    why: "Dark mode is easier on the eyes at night and makes bright outfit photos stand out.",
  },
];

/** Short intro shown once on first visit and at the top of the help menu. */
export const INTRO = {
  sentence:
    "MoodBoards is a concept for what Pinterest could add for fashion. It works like the Pinterest you know, plus these new features:",
  bullets: [
    "Search by color: tap the rainbow dot and pick an exact shade, optionally with words like “linen”",
    "Mood picker: a color wheel plus an aesthetic gives you a curated grid when you can't put a look into words",
    "Analyze board: finds the distinct aesthetics inside a mixed board instead of averaging them into one",
    "Character style boards: dress like film and TV characters, matched to real catalog pieces",
    "Complete the look, tuned to your board: outfit pieces that match the item and your board's taste",
    "Save to several boards in one go, nest boards inside boards, and Undo any save, with no pop-ups",
    "Ask: a style assistant that can only show items it actually found, never made-up products",
    "Shop similar: one tap from any item to shopping results for its exact color and type",
    "Honest search: tells you when nothing truly matches instead of padding results",
  ],
};

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
  sessionDismissed.add(id);
  try {
    const dismissed = getDismissedTips();
    dismissed.add(id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...dismissed]));
  } catch {
    // Non-critical: the tip will just show again next visit.
  }
  notify();
}

// --- One tip at a time -------------------------------------------------------------------------
// Tips register while their feature is on screen. Only one shows at once: the first undismissed,
// on-screen tip in FEATURE_TIPS order, and only after the welcome card has been dismissed.

export const WELCOME_ID = "welcome";
const mounted = new Set<string>();
const sessionDismissed = new Set<string>(); // keeps working when localStorage is unavailable
const listeners = new Set<() => void>();
let version = 0;

function notify() {
  version += 1;
  listeners.forEach((l) => l());
}

export const tipStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  getVersion: () => version,
  register(id: string) {
    mounted.add(id);
    notify();
    return () => {
      mounted.delete(id);
      notify();
    };
  },
  /** Test helper: forget this session's dismissals (localStorage is cleared separately). */
  resetSession() {
    sessionDismissed.clear();
    notify();
  },
  /** Which tip (if any) should be showing right now. */
  active(): string | null {
    const dismissed = getDismissedTips();
    const isDismissed = (id: string) => dismissed.has(id) || sessionDismissed.has(id);
    if (!isDismissed(WELCOME_ID)) return null;
    return FEATURE_TIPS.find((t) => mounted.has(t.id) && !isDismissed(t.id))?.id ?? null;
  },
};

export function getTip(id: string): FeatureTipContent {
  const tip = FEATURE_TIPS.find((t) => t.id === id);
  if (!tip) throw new Error(`Unknown feature tip: ${id}`);
  return tip;
}
