/** Typed client for the MoodBoards API. In dev, Vite proxies /api to FastAPI on :8000. */
import { categoryLabel } from "../categories";
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
  /** evidence-based AI label (feature 5) */
  provenance?: ProvenanceLabel;
}

export interface ProvenanceLabel {
  label: "ai_generated" | "human_verified" | "unknown";
  explanation: string;
  evidence: { source: string; field: string; value: string; note?: string }[];
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

export type CharacterItem = ScoredItem & { matched_phrase: string; approximate?: boolean };

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
  /** Photo search: the label read from your uploaded photo's original bytes. */
  upload_provenance?: ProvenanceLabel | null;
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
  fromItems: (name: string, itemIds: string[]) => request<Board>("/boards/from-items", json({ name, item_ids: itemIds })),
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

export const altText = (item: Item) => `Photo of ${item.kids ? "kids' " : ""}${categoryLabel(item.category).toLowerCase()}`;

export const api = {
  listItems: (offset = 0, limit = 50, filters: { group?: string | null; style?: string | null } = {}) =>
    request<ItemPage>(
      `/items?offset=${offset}&limit=${limit}${filters.group ? `&group=${filters.group}` : ""}${filters.style ? `&style=${encodeURIComponent(filters.style)}` : ""}`,
    ),
  getItem: (id: string) => request<Item>(`/items/${encodeURIComponent(id)}`),
  similar: (id: string, k = 30) => request<SearchResults>(`/items/${encodeURIComponent(id)}/similar?k=${k}`),
  searchText: (q: string, k = 50, group?: string | null) =>
    request<SearchResults>(`/search/text?q=${encodeURIComponent(q)}&k=${k}${group ? `&group=${group}` : ""}`),
  assistantStatus: () => request<{ available: boolean; model: string; reason: string | null }>("/assistant/status"),
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

// --- Trips (feature 9) ---------------------------------------------------------------------------

export interface Place {
  name: string;
  country: string | null;
  admin: string | null;
  latitude: number;
  longitude: number;
}

export interface DayWeather {
  date: string;
  high_c: number | null;
  low_c: number | null;
  rain_chance: number | null;
}

export interface TripWeather {
  source: "forecast" | "historical average" | "unavailable";
  source_detail: string;
  attribution: string;
  days: DayWeather[];
}

export interface TripSummary {
  id: number;
  name: string;
  place_name: string;
  start_date: string;
  end_date: string;
  role: "owner" | "editor" | "viewer";
}

export interface TripDetail {
  id: number;
  name: string;
  place: string;
  start_date: string;
  end_date: string;
  coordinate: boolean;
  public_slug: string | null;
  published: boolean;
  your_role: "owner" | "editor" | "viewer";
  members: { user_id: number; name: string; role: string; is_you: boolean }[];
  slots: { id: number; day: string; label: string }[];
  weather: TripWeather;
  taste: {
    inspiration_count: number;
    group_style: string[];
    members: { user_id: number; name: string; style: string[] }[];
    overlap: { a: string; b: string; similarity: number; reading: string }[];
  };
  palette: { hex: string; weight: number }[];
}

export interface SlotSuggestions {
  slot: { id: number; day: string; label: string };
  weather: Partial<DayWeather>;
  weather_source: string;
  items: { role: string; item: Item; votes: { up: number; down: number; mine: number } }[];
}

export interface TripNote {
  id: number;
  day: string;
  text: string;
  ai_suggestion: number;
  author: string;
}

export interface PublicTrip {
  name: string;
  place: string;
  start_date: string;
  end_date: string;
  travelers: number;
  weather: TripWeather;
  lineup: { day: string; label: string; items: Item[] }[];
  notes: { day: string; text: string; ai_suggestion: number }[];
}

const jsonBody = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const tripsApi = {
  geocode: (q: string) => request<Place[]>(`/geocode?q=${encodeURIComponent(q)}`),
  list: () => request<TripSummary[]>("/trips"),
  create: (body: { name: string; place: Place; start_date: string; end_date: string; slots: { day: string; label: string }[] }) =>
    request<{ id: number }>("/trips", jsonBody("POST", body)),
  get: (id: number) => request<TripDetail>(`/trips/${id}`),
  setCoordinate: (id: number, on: boolean) => request<unknown>(`/trips/${id}?coordinate=${on}`, { method: "PATCH" }),
  addSlot: (id: number, day: string, label: string) => request<{ id: number }>(`/trips/${id}/slots`, jsonBody("POST", { day, label })),
  createInvite: (id: number, role: "editor" | "viewer") =>
    request<{ id: number; token: string; role: string; expires_at: string }>(`/trips/${id}/invites`, jsonBody("POST", { role })),
  invites: (id: number) => request<{ id: number; role: string; expires_at: string; revoked: number }[]>(`/trips/${id}/invites`),
  revokeInvite: (id: number, inviteId: number) => fetch(`${BASE}/trips/${id}/invites/${inviteId}`, { method: "DELETE" }),
  join: (token: string) => request<{ trip_id: number; role: string }>(`/join/${encodeURIComponent(token)}`, { method: "POST" }),
  addInspiration: (id: number, files: File[]) => {
    const body = new FormData();
    files.forEach((f) => body.append("images", f));
    return request<{ added: number }>(`/trips/${id}/inspiration`, { method: "POST", body });
  },
  suggestions: (id: number, slotId: number, sort: "relevance" | "votes") =>
    request<SlotSuggestions>(`/trips/${id}/slots/${slotId}/suggestions?sort=${sort}`),
  vote: (id: number, slotId: number, itemId: string, value: -1 | 0 | 1) =>
    request<unknown>(`/trips/${id}/slots/${slotId}/votes`, jsonBody("POST", { item_id: itemId, value })),
  packing: (id: number) =>
    request<{ items: { kind: string; label: string; item_id?: string; why?: string }[]; weather_source: string }>(`/trips/${id}/packing`),
  notes: (id: number) => request<TripNote[]>(`/trips/${id}/notes`),
  addNote: (id: number, day: string, text: string) => request<unknown>(`/trips/${id}/notes`, jsonBody("POST", { day, text })),
  draftNote: (id: number, day: string) => request<{ text: string }>(`/trips/${id}/notes/draft?day=${day}`, { method: "POST" }),
  activity: (id: number) => request<{ id: number; actor: string; text: string; created_at: string }[]>(`/trips/${id}/activity`),
  eventsUrl: (id: number) => `${BASE}/trips/${id}/events`,
  publish: (id: number) => request<{ slug: string }>(`/trips/${id}/publish`, { method: "POST" }),
  unpublish: (id: number) => fetch(`${BASE}/trips/${id}/publish`, { method: "DELETE" }),
  publicTrip: (slug: string) => request<PublicTrip>(`/public/trips/${encodeURIComponent(slug)}`),
};
