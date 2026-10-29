/** Typed client for the MoodBoards API. In dev, Vite proxies /api to FastAPI on :8000. */
import { getFocus } from "../focus";

const BASE = "/api";

export interface Item {
  id: string;
  category: string;
  image_url: string;
  kids: boolean;
  width: number;
  height: number;
  /** dominant colors (hex), heaviest first */
  colors?: string[];
  /** set when near-duplicate copies of this image exist (feature 6) */
  repost?: RepostInfo | null;
}

export interface RepostInfo {
  status: "original" | "unclear";
  original_id: string | null;
  first_seen: string | null;
  date_source: string | null;
  reason: string;
  hidden: number;
  member_ids: string[];
}

/** One-line credit for a collapsed duplicate group. */
export function repostLabel(item: Item): string | null {
  const r = item.repost;
  if (!r) return null;
  const hidden = `${r.hidden} ${r.hidden === 1 ? "copy" : "copies"} hidden`;
  if (r.status === "unclear") return `Original unclear · ${hidden}`;
  const date = r.first_seen ? new Date(r.first_seen).toLocaleDateString() : "unknown date";
  const lead = r.original_id === item.id ? "Original" : "Repost of original";
  return `${lead} · first seen ${date} (${r.date_source}) · ${hidden}`;
}

export interface ColorMatchItem extends Item {
  score: number;
  color_score: number;
  delta_e: number;
  matched_color: string;
  text_score: number | null;
}

export interface ColorResults {
  color: string;
  query: string | null;
  color_weight: number;
  results: ColorMatchItem[];
}

export interface CharacterInfo {
  id: string;
  name: string;
  source: string;
  summary: string;
  phrases: string[];
}

export type CharacterItem = ScoredItem & { matched_phrase: string };

export interface CharacterBoard extends CharacterInfo {
  disclaimer: string;
  looks: { name: string; phrases: string[]; results: CharacterItem[] }[];
  results: CharacterItem[];
}

export interface Prefs {
  aesthetics: string[];
  colors: string[];
  eras: string[];
  focus: "all" | "women" | "men";
}

export interface Me {
  display_name: string;
  prefs: Prefs;
}

export interface QuizOptions {
  aesthetics: string[];
  colors: Record<string, string[]>;
  eras: string[];
  focus: string[];
  max_picks: number;
}

export interface ForYouItem extends Item {
  score: number;
  style_match: number | null;
  color_match: number | null;
}

export const profileApi = {
  me: async (): Promise<Me | null> => {
    const r = await fetch(`${BASE}/me`);
    if (r.status === 404) return null;
    if (!r.ok) throw new ApiError(r.status, r.statusText);
    return r.json();
  },
  signUp: (displayName: string) => request<Me>("/me", json({ display_name: displayName })),
  savePrefs: (prefs: Prefs) =>
    request<Me>("/me/prefs", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(prefs) }),
  signOut: () => fetch(`${BASE}/me`, { method: "DELETE" }),
  quiz: () => request<QuizOptions>("/quiz"),
  forYou: (offset = 0, limit = 50) => request<{ personalized: boolean; items: ForYouItem[] }>(`/for-you?offset=${offset}&limit=${limit}`),
};

export interface ShopLinks {
  query: string;
  query_source: "vision model" | "color + category";
  color_name: string | null;
  google_shopping: string;
  google_lens: string;
  google_images: string;
}

export interface ScoredItem extends Item {
  score: number;
}

export interface ItemPage {
  items: Item[];
  total: number;
  offset: number;
}

export interface SearchResults {
  query: string | null;
  results: ScoredItem[];
  /** True when even the best matches are weak (e.g. a non-clothing query). */
  low_relevance?: boolean;
  /** What a text query was understood as: categories and colors. */
  understood?: string[];
  /** Photo search: your upload is a repost of this catalog image. */
  repost_of?: { original: Item; reason: string; first_seen: string | null; date_source: string | null } | null;
}

export interface Aesthetic {
  index: number;
  image_indices: number[];
  style_tags: { word: string; score: number }[];
  results: ScoredItem[];
  centroid: number[];
}

/** A board aesthetic carried into the close-up so Complete the look can match it. */
export interface BoardContext {
  label: string;
  centroid: number[];
}

export interface CompleteLook {
  item_id: string;
  anchor_group: string | null;
  used_board: boolean;
  groups: { group: string; results: ScoredItem[] }[];
}

export interface BoardAnalysis {
  k: number;
  silhouette: number | null;
  silhouette_by_k: Record<string, number>;
  aesthetics: Aesthetic[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** Adds the viewer's style focus to a URL (endpoints that don't filter simply ignore it). */
export function withFocus(path: string): string {
  const focus = getFocus();
  if (focus === "all") return path;
  return `${path}${path.includes("?") ? "&" : "?"}focus=${focus}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${withFocus(path)}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export interface Board {
  id: number;
  name: string;
  parent_id: number | null;
  item_count: number;
  cover: Item | null;
}

export interface BoardDetail extends Board {
  breadcrumb: Board[];
  children: Board[];
  items: Item[];
}

export interface SaveResult {
  item_id: string;
  added_to: number[];
  already_in: number[];
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const boardsApi = {
  list: () => request<Board[]>("/boards"),
  get: (id: number) => request<BoardDetail>(`/boards/${id}`),
  create: (name: string, parentId: number | null = null) => request<Board>("/boards", json({ name, parent_id: parentId })),
  remove: (id: number) => fetch(`${BASE}/boards/${id}`, { method: "DELETE" }),
  save: (itemId: string, boardIds: number[]) => request<SaveResult>("/saves", json({ item_id: itemId, board_ids: boardIds })),
  unsave: (itemId: string, boardIds: number[]) =>
    request<SaveResult>("/saves/remove", json({ item_id: itemId, board_ids: boardIds })),
  savedIn: (itemId: string) => request<number[]>(`/items/${encodeURIComponent(itemId)}/saved-in`),
};

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantRequest {
  message: string;
  history: ChatTurn[];
  context_item_ids: string[];
  board: { label: string; style_tags: string[]; centroid: number[] }[] | null;
}

export async function startAssistantChat(body: AssistantRequest, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(`${BASE}/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new ApiError(response.status, response.statusText);
  return response;
}

export const imageSrc = (item: Item) => `${BASE}${item.image_url}`;

export const altText = (item: Item) => `Photo of ${item.kids ? "kids' " : ""}${item.category.toLowerCase()}`;

export const api = {
  listItems: (offset = 0, limit = 50) => request<ItemPage>(`/items?offset=${offset}&limit=${limit}`),
  getItem: (id: string) => request<Item>(`/items/${encodeURIComponent(id)}`),
  similar: (id: string, k = 30) => request<SearchResults>(`/items/${encodeURIComponent(id)}/similar?k=${k}`),
  searchText: (q: string, k = 50) => request<SearchResults>(`/search/text?q=${encodeURIComponent(q)}&k=${k}`),
  searchImage: (file: File, k = 50) => {
    const body = new FormData();
    body.append("image", file);
    return request<SearchResults>(`/search/image?k=${k}`, { method: "POST", body });
  },
  searchColor: (hex: string, q?: string, k = 50) =>
    request<ColorResults>(`/search/color?hex=${encodeURIComponent(hex)}&k=${k}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  styles: () => request<string[]>("/styles"),
  characters: () => request<(CharacterInfo & { covers: Item[] })[]>("/characters"),
  characterBoard: (id: string, k = 30) => request<CharacterBoard>(`/characters/${encodeURIComponent(id)}?k=${k}`),
  mood: (hex: string, style: string, colorWeight = 0.5, k = 40) =>
    request<ColorResults>(
      `/mood?hex=${encodeURIComponent(hex)}&style=${encodeURIComponent(style)}&color_weight=${colorWeight}&k=${k}`,
    ),
  shopLinks: (itemId: string, detailed = true) =>
    request<ShopLinks>(`/items/${encodeURIComponent(itemId)}/shop-links?detailed=${detailed}`),
  completeLook: (itemId: string, board?: BoardContext | null, perGroup = 6) =>
    request<CompleteLook>("/complete-look", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_id: itemId, centroid: board?.centroid ?? null, per_group: perGroup }),
    }),
  analyzeBoard: (files: File[], k = 12) => {
    const body = new FormData();
    files.forEach((f) => body.append("images", f));
    return request<BoardAnalysis>(`/board/analyze?k=${k}`, { method: "POST", body });
  },
};
