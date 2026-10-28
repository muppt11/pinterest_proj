/** Typed client for the MoodBoards API. In dev, Vite proxies /api to FastAPI on :8000. */

const BASE = "/api";

export interface Item {
  id: string;
  category: string;
  image_url: string;
  kids: boolean;
  width: number;
  height: number;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
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
